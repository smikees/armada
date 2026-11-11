"""Provider lane selection for one invocation; retries never bypass replay evidence."""
from dataclasses import replace
import datetime as dt
import re
import time
from . import util, run_policy, usage_snapshot
from .engine.base import RunResult


def _refusal_path(provider):
    return util.data_dir() / f'{provider}-plan-refusal.json'


def refusal(result):
    raw = result.raw
    text = result.error or result.output
    # A generic HTTP 429 is not evidence of a subscription limit.
    return (not result.ok and not result.cancelled and not result.timed_out
            and raw.get('api_error_status') == 429
            and bool(re.search(r"(?:you['’]ve hit|you have hit|reached|exceeded).{0,70}(?:session|weekly|usage|subscription|week).{0,20}limit", text, re.I)))


def _reset(text):
    # The observed CLI refusal gives a local clock time and an IANA zone.
    from zoneinfo import ZoneInfo
    match = re.search(r'resets?\s+(\d{1,2}(?::\d{2})?\s*[ap]m)\s*\(([^)]+)\)', text, re.I)
    if match:
        try:
            zone = ZoneInfo(match[2])
            now = dt.datetime.now(zone)
            clock = dt.datetime.strptime(match[1].replace(' ', '').upper(), '%I:%M%p' if ':' in match[1] else '%I%p')
            when = now.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
            if when <= now:
                when += dt.timedelta(days=1)
            return when.timestamp()
        except (ValueError, KeyError):
            pass
    return None  # Never invent a weekly reset from an unrecognised string.


def exhausted(root, provider='claude', model=''):
    now = time.time()
    rows = usage_snapshot.read(root)
    row = rows.get(provider, {})
    windows = [row.get('session'), row.get('weekly')]
    windows += [value for name, value in row.get('model_weekly', {}).items() if name.casefold() in (model or '').casefold()]
    if row.get('available') and now-row.get('at', 0) <= 1800:
        blocked = []
        for window in windows:
            if not isinstance(window, dict) or window.get('pct', 0) < 100:
                continue
            try:
                reset = dt.datetime.fromisoformat(window.get('resets_at', '').replace('Z', '+00:00')).timestamp()
            except ValueError:
                reset = None
            if reset is None or reset > now:
                blocked.append(reset)
        if blocked:
            return 'A current usage reading says the subscription is exhausted.', max((x for x in blocked if x), default=None)
    recorded = util.read_json_state(_refusal_path(provider), default=dict)
    # A fresh non-exhausted reading supersedes a refusal only when it was read later.
    if row.get('available') and row.get('at', 0) > recorded.get('at', 0) and now-row['at'] <= 1800:
        return '', None
    reset = recorded.get('reset_at')
    if recorded and (reset is None or now < reset):
        return recorded.get('reason', 'The subscription refused this limit window.'), reset
    return '', None


def connector_guard(root, agent, request):
    if not request.allow_tools or request.only_tools is not None:
        return []
    from . import capabilities, connector_registry
    # Match the effective grant, including realm and agent overrides.
    missing = []
    usable = capabilities.usable(root, agent)
    for cap in [c for kind in capabilities.MCP_KINDS for c in usable.get(kind, [])]:
        facade = connector_registry.provider_cap(cap, 'claude')
        name = str(facade.get('id') or cap.get('id') or '')
        from .engine.mcp import server_id
        name = server_id(name)
        if name.startswith(('claude_ai_', 'claude_as_')):
            missing.append(str(cap.get('name') or cap.get('id') or name))
    return missing


def replay_safe(result, events, *, root, job, run_id, started):
    from . import job_retries, job_results
    tools = [e for e in events if e.get('kind') == 'tool']
    if not tools:
        return True, ''
    report = job_results.evaluate(result.output, run_id=run_id, job=job or {}, root=root,
                                  started=started, runtime_execution='failed', runtime_error=result.error)
    if not job_retries.retryable({'engine':'claude','result':report}):
        return False, 'The refused attempt used tools without sufficient replay evidence, or delivery was already sent or uncertain.'
    return True, ''


def execute(engine, request, *, root, agent, job, run_id, on_event, on_proc, invoke):
    provider = getattr(engine, 'name', 'unknown')
    if provider != 'claude':
        return invoke(engine, request, on_event=on_event, on_proc=on_proc)
    config = run_policy.settings(root, agent, job, provider)
    events = []
    reason, reset = exhausted(root, provider, request.model)
    refused = None
    started = time.time()
    def event(value):
        if value.get('kind') in ('tool', 'tool_result'):
            events.append(value)
        on_event(value)
    event.engine_activity = getattr(on_event, 'engine_activity', None)
    if not reason:
        result = invoke(engine, request, on_event=event, on_proc=on_proc)
        result.raw['billing'] = {'lane':'plan'}
        if not refusal(result):
            return result
        refused = {'attempt_id':run_id+'-plan', 'reason':result.error, 'api_error_status':429,
                   'tools_ran':len([e for e in events if e.get('kind') == 'tool'])}
        reason, reset = result.error, _reset(result.error)
        util.write_json_atomic(_refusal_path(provider), {'at':time.time(), 'reason':reason, 'reset_at':reset})
        safe, detail = replay_safe(result, events, root=root, job=job, run_id=run_id, started=started)
        if not safe:
            result.error += '\nAPI fallback held: '+detail
            from . import notify
            notify.emit(root, 'api_credit', 'API fallback needs review', detail, f'/agent/{agent}/threads')
            return result
    config = run_policy.settings(root,agent,job,provider)
    action = config['plan_limit_action']
    if action == 'api':
        missing = connector_guard(root, agent, request)
        if missing:
            reason = '; '.join(f'{name} is a claude.ai connector and is not available on the API key.' for name in missing)
            action = config['connector_limit_action']
    if action == 'wait':
        return _wait(engine, request, root, agent, job, run_id, reason, reset, on_event, on_proc, invoke, started)
    if action != 'api':
        return RunResult(ok=False, error=reason, raw={'billing':{'lane':'plan', 'fallback_reason':reason, 'refused_attempt':refused}})
    from . import provider_keys
    if not provider_keys.configured(provider):
        return RunResult(ok=False, error='Subscription limit reached; no Anthropic API key is configured.')
    from . import worker
    try:
        worker.require()
    except OSError as exc:
        return RunResult(ok=False, error=str(exc))
    # Runtime proof of child-environment isolation is required, not a guessed version check.
    from .engine.claude import credential_scrub_supported
    if not credential_scrub_supported(engine):
        return RunResult(ok=False, error='API fallback is closed: this Claude CLI cannot verify subprocess credential scrubbing. Update Claude Code.')
    try:
        ceiling = run_policy.reserve(provider, run_id, config)
    except ValueError as exc:
        if 'reserve is reached' not in str(exc):
            raise
        run_policy.notify_once(root, 'credit-closed-'+run_policy.cycle(config)[0], str(exc))
        return _wait(engine, request, root, agent, job, run_id, str(exc), reset, on_event, on_proc, invoke, started,
                     wait_for_credit=True, refused=refused)
    credit = run_policy.credit(provider, config)
    publish_credit(root, provider, credit)
    notify_credit(root, provider, credit)
    if config.get('api_model'):
        from .runner import _cli_model
        request = replace(request, model=_cli_model(config['api_model'], root))
    # The CLI receives a one-invocation gateway token, never the real Console key.
    request = replace(request, max_budget_usd=min(request.max_budget_usd or ceiling, ceiling),
        system=request.system+f'\n\nThis run is billed to the API credit: ${credit["spent_usd"]:.2f} of ${credit["cap_usd"]:.2f} used this cycle. '
                              'Only directly registered MCP connectors are available on this lane.')
    if request.timeout is not None:
        remaining = request.timeout - (time.time()-started)
        if remaining <= 0:
            run_policy.settle(provider, run_id, 0)
            return RunResult(ok=False, timed_out=True, error='The owner-chosen time limit expired before API fallback.')
        request = replace(request, timeout=remaining)
    window = str(reset or util.read_json_state(_refusal_path(provider), default=dict).get('at', 'unknown'))
    run_policy.notify_once(root, 'fallback-'+window, 'Subscription limit reached. Eligible work is using the API credit.')
    # If execution crashes without a result, its full reservation remains charged/held.
    from .api_gateway import Gateway
    with Gateway(provider_keys.key(provider), request.max_budget_usd) as gateway:
        api_request = replace(request, env={**request.env, **gateway.env})
        result = invoke(engine, api_request, on_event=on_event, on_proc=on_proc)
        unfinished_requests = gateway.inflight
        metered_cost = gateway.budget.cost()
    # Use the provider's terminal cost, never EngineAdapter's API-equivalent estimate.
    import math
    real_cost = result.raw.get('total_cost_usd')
    if unfinished_requests or metered_cost is None or type(real_cost) not in (int, float) or not math.isfinite(real_cost) or real_cost < 0:
        real_cost = None
    else:
        real_cost = max(real_cost, metered_cost)
    run_policy.settle(provider, run_id, real_cost)
    result.raw['billing'] = {'lane':'api', 'real_cost_usd':real_cost, 'charged_usd':real_cost if real_cost is not None else ceiling,
                             'fallback_reason':reason, 'refused_attempt':refused, 'ceiling_usd':ceiling}
    # An API refusal is final for this logical job series too, not a route back into job retries.
    if not result.ok:
        result.raw['billing']['final_failure'] = True
    credit = run_policy.credit(provider, config)
    notify_credit(root, provider, credit)
    publish_credit(root, provider, credit)
    return result


def notify_credit(root, provider, credit):
    for threshold in (50, 80, 100):
        if credit['spent_usd']+credit['reserved_usd'] >= credit['cap_usd']*threshold/100:
            run_policy.notify_once(root, f'{provider}-{credit["resets_at"]}-{threshold}',
                f'API credit is {threshold}% used or reserved: ${credit["spent_usd"]:.2f} spent of ${credit["cap_usd"]:.2f}.'+
                (' The API lane is closed.' if threshold == 100 else ''))


def publish_credit(root, provider, credit):
    path = root / 'usage-last.json'
    with util.file_lock(path):
        state = util.read_json_state(path, default=dict)
        state.setdefault('api', {})[provider] = credit
        util.write_json_atomic(path, state)


def _wait(engine, request, root, agent, job, run_id, reason, reset, on_event, on_proc, invoke, started=None,
          *, wait_for_credit=False, refused=None):
    from . import execution_admission as admission, provider_limits
    from .engine.process import safe_emit
    safe_emit(on_event, {'kind':'status','waiting_for_plan':True,'activity':'Waiting for the subscription reset. '+reason})
    run_policy.notify_once(root, 'waiting-'+run_id, 'A run is waiting for the subscription reset. '+reason)
    deadline = (started or time.time())+request.timeout if request.timeout is not None else None
    while True:
        if admission.cancelled():
            return RunResult(ok=False, cancelled=True, error='Run stopped while waiting for the subscription reset.')
        if deadline is not None and time.time() >= deadline:
            return RunResult(ok=False, timed_out=True, error='The owner-chosen time limit expired while waiting for the subscription reset.')
        admission.defer_current(min(reset or time.time()+60, time.time()+60, deadline or float('inf')))
        provider_limits.read('claude', root)
        blocked, reset = exhausted(root, 'claude', request.model)
        if blocked and wait_for_credit:
            current = run_policy.settings(root,agent,job)
            credit = run_policy.credit(config=current)
            floor = 0 if current.get('critical') else current['monthly_cap_usd']*current['reserve_percent']/100
            if credit['open'] and credit['remaining_usd'] > floor:
                resumed = replace(request,timeout=max(0,deadline-time.time())) if deadline is not None else request
                if resumed.timeout == 0:
                    return RunResult(ok=False,timed_out=True,error='The owner-chosen time limit expired while waiting for API credit.')
                result = execute(engine,resumed,root=root,agent=agent,job=job,run_id=run_id,on_event=on_event,on_proc=on_proc,invoke=invoke)
                if refused and not result.raw.get('billing',{}).get('refused_attempt'):
                    result.raw.setdefault('billing',{})['refused_attempt'] = refused
                return result
        if not blocked:
            if deadline is not None:
                remaining = deadline-time.time()
                if remaining <= 0:
                    return RunResult(ok=False, timed_out=True, error='The owner-chosen time limit expired while waiting for the subscription reset.')
                request = replace(request, timeout=remaining)
            # Plan only here: no recursion that could grant a second API attempt.
            result = invoke(engine, request, on_event=on_event, on_proc=on_proc)
            result.raw['billing'] = {'lane':'plan','wait_reason':reason}
            return result
