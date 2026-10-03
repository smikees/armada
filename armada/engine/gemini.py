"""Google Gemini through the supported Antigravity CLI; cached login, fresh scoped turns."""
from __future__ import annotations
import json, os, re, shutil, subprocess, tempfile, threading, time, uuid
from contextlib import contextmanager
from pathlib import Path
from .base import EngineAdapter, RunResult, Usage
from .contracts import ProviderCapabilities, RunRequest, validate_request
from .process import supervise, safe_emit
_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
_auth_lock = threading.RLock()
_auth_cache = None
_usage_cache = None
_SEED = [{'id':f'gemini-{v}-flash','label':f'Google · Gemini {v} Flash','efforts':['low','medium','high']} for v in ('3.8','3.7','3.6')] + [{'id':'gemini-3.1-pro','label':'Google · Gemini 3.1 Pro','efforts':['low','high']}]
MODEL_OPTIONS = [('gemini:auto','Google · Gemini Auto (latest Flash)')] + [(m['id'],m['label']) for m in _SEED]
_FILE_TOOLS = ['view_file','list_dir','find_by_name','grep_search','write_to_file','replace_file_content','multi_replace_file_content']
_ALIASES = {'Read':'view_file','Write':'write_to_file','Edit':'replace_file_content','Glob':'find_by_name','Grep':'grep_search','WebSearch':'search_web','WebFetch':'read_url_content'}

def invalidate_auth():
    global _auth_cache, _usage_cache
    _auth_cache = None
    _usage_cache = None

def cached_models():
    from .. import appconfig
    rows = appconfig.get('provider_connections',{}).get('gemini',{}).get('models')
    return rows if isinstance(rows,list) and rows else list(_SEED)

def model_options():
    return MODEL_OPTIONS[:1] + [(m['id'],m['label']) for m in cached_models()]

def model_id(value):
    value = str(value or '').strip().lower()
    if value in ('','gemini:auto','gemini:default'):
        return next((m['id'] for m in cached_models() if 'flash' in m['id']),_SEED[0]['id'])
    return re.sub(r'-(low|medium|high|max)$', '', value.removeprefix('gemini:'))

@contextmanager
def scoped_project(roots, servers, network):
    """A fresh project owns each run's grants; never edit the user's global policy."""
    pid = 'armada-' + uuid.uuid4().hex
    path = Path.home()/'.gemini/config/projects'/f'{pid}.json'
    allow = [f'write_file({root.as_posix()})' for root in roots]
    allow += [f'mcp({server}/*)' for server in servers]
    if network: allow.append('read_url(*)')
    deny = ['command(*)', 'unsandboxed(*)', 'execute_url(*)']
    if not network: deny.append('read_url(*)')
    data = {'id':pid, 'name':pid, 'settings':{'allowNonWorkspaceAccess':False},
            'permissionGrants':{'permissionGrants':{'allow':allow,'deny':deny},'v2Migrated':True},
            'projectResources':{}}
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation and a random ID also isolate simultaneous agent runs.
    with path.open('x',encoding='utf-8') as handle: json.dump(data,handle)
    try: yield pid
    finally: path.unlink(missing_ok=True)

def parse_models(text):
    rows = {}
    for line in text.splitlines():
        parts = line.split('\t',1)
        match = re.fullmatch(r'(gemini-[a-z0-9.-]+)-(low|medium|high|max)',parts[0].strip())
        if not match: continue
        mid,effort = match.groups()
        label = re.sub(r'\s*\((Low|Medium|High|Max)\)\s*$','',parts[1] if len(parts)>1 else mid,flags=re.I)
        row = rows.setdefault(mid,{'id':mid,'label':'Google · '+label,'efforts':[]})
        if effort not in row['efforts']: row['efforts'].append(effort)
    return list(rows.values())

class GeminiEngine(EngineAdapter):
    name = 'gemini'
    # The CLI injects an internal task tool, so strict sealed review turns are rejected.
    capabilities = ProviderCapabilities(streaming=True,cancellation=True,tool_denials=True)
    def __init__(self,binary='agy'):
        self.binary = binary
        self.allowed_mcp_ids = frozenset()
        self.native_filesystem_ids = frozenset()
        self.writable_roots = ()
        self.network_access = False
    def _launcher(self):
        if self.binary == 'agy':
            from .. import appconfig
            configured = appconfig.get('provider_connections', {}).get('gemini', {}).get('executable_path')
            if configured and Path(configured).suffix.lower() == '.exe' and Path(configured).is_file():
                return [str(configured)]
        exe = shutil.which(self.binary)
        if exe and not str(exe).lower().endswith(('.cmd','.ps1','.bat')): return [exe]
        if os.name == 'nt' and self.binary == 'agy':
            # Explorer and already-running desktop hosts can retain an older PATH.
            # Resolve the per-user install directly, including when LOCALAPPDATA
            # is absent/stale. Never replace an explicitly requested custom binary.
            roots = [Path.home()/'AppData/Local']
            local = os.environ.get('LOCALAPPDATA')
            if local: roots.insert(0, Path(local))
            for root in roots:
                path = root/'agy/bin/agy.exe'
                if path.is_file(): return [str(path)]
        return None
    def _probe(self,args):
        launcher = self._launcher()
        if not launcher: raise FileNotFoundError("Install Gemini's Antigravity CLI in Settings → App.")
        return subprocess.run(launcher+args,stdin=subprocess.DEVNULL,capture_output=True,text=True,
            encoding='utf-8',errors='replace',timeout=25,creationflags=_NO_WINDOW)
    def auth_status(self,force=False):
        global _auth_cache
        with _auth_lock:
            if not force and _auth_cache and time.monotonic()-_auth_cache[0]<60: return dict(_auth_cache[1])
            if not self._launcher(): return {'ok':True,'logged_in':False,'reason':'cli-missing','method':''}
            try:
                result = self._probe(['models']); rows = parse_models(result.stdout)
                logged = result.returncode==0 and bool(rows)
                missing = any(t in (result.stderr+result.stdout).lower() for t in ('please sign in','not logged','authentication required'))
                state = {'ok':logged or missing,'logged_in':logged,'reason':'' if logged else 'signed-out' if missing else 'probe-failed','method':'Google account','models':rows}
            except (OSError,subprocess.SubprocessError):
                state = {'ok':False,'logged_in':False,'reason':'probe-failed','method':''}
            _auth_cache = (time.monotonic(),dict(state)); return state
    def doctor(self):
        state = self.auth_status()
        return bool(state.get('logged_in')),'Gemini · Antigravity CLI' if state.get('logged_in') else state.get('reason','')
    def usage_limits(self):
        from datetime import datetime,timezone
        global _usage_cache
        if _usage_cache and time.monotonic()-_usage_cache[0]<60: return dict(_usage_cache[1])
        if not self.auth_status().get('logged_in'): return {'available':False,'message':'Gemini is signed out.'}
        try:
            result = self._probe(['--print','/usage'])
            for line in result.stdout.splitlines():
                fields = line.split('\t')
                if len(fields)>=4 and fields[0].strip()=='Gemini Models' and fields[1].strip()=='Weekly Limit Remaining':
                    remaining = float(fields[2].strip().removesuffix('%'))
                    reset = datetime.fromisoformat(fields[3].strip().replace('Z','+00:00'))
                    hours = max(0,int((reset-datetime.now(timezone.utc)).total_seconds()/3600))
                    value = {'available':True,'weekly':{'pct':round(100-max(0,min(100,remaining)),1),'resets_in':f'{hours//24}d {hours%24}h','resets_at':reset.isoformat()}}
                    _usage_cache = (time.monotonic(),value)
                    return value
        except (OSError,ValueError,subprocess.SubprocessError): pass
        return {'available':False,'message':'Gemini quota could not be read. Recheck the connection in App settings.'}
    def _connectors(self,denied):
        # Only provider-local configurations. Never transfer Claude/Codex credentials.
        try: inventory = json.loads((Path.home()/'.gemini/config/mcp_config.json').read_text(encoding='utf-8-sig')).get('mcpServers',{})
        except (OSError,ValueError): inventory = {}
        selected = []
        for sid in sorted(self.allowed_mcp_ids):
            if any(t in (f'mcp__{sid}',f'mcp__{sid}__*') for t in denied): continue
            # The recognized filesystem extension is fulfilled by native tools,
            # under this run's approved roots, not its legacy MCP command/paths.
            if sid in self.native_filesystem_ids: continue
            entry = inventory.get(sid)
            if not isinstance(entry,dict) or entry.get('disabled'):
                raise ValueError(f'Connector {sid} is not configured for Gemini. Connect it in Antigravity CLI before using it with this provider.')
            selected.append({**entry,'name':sid})
        return selected
    def _agent(self,system,allow_tools,denied):
        selected = list(_FILE_TOOLS) if allow_tools else []
        # Native file tools implement the filesystem capability, so enforce its
        # grants here rather than relying on catalogue-derived MCP deny patterns.
        if self.native_filesystem_ids - self.allowed_mcp_ids:
            selected = []
        if allow_tools and self.network_access: selected += ['search_web','read_url_content']
        for tool in denied:
            if tool.startswith('mcp__'):
                if not re.fullmatch(r'mcp__[A-Za-z0-9_-]+(?:__\*)?',tool) or '__' in tool.removeprefix('mcp__').removesuffix('__*'):
                    raise ValueError('Gemini supports MCP server grants, not individual MCP tool denials.')
                sid = tool.removeprefix('mcp__').removesuffix('__*')
                if sid in self.native_filesystem_ids:
                    selected = [t for t in selected if t not in _FILE_TOOLS]
            else:
                name = _ALIASES.get(tool,tool)
                if name not in _FILE_TOOLS+['search_web','read_url_content']:
                    raise ValueError(f'Gemini cannot enforce tool denial {tool}.')
                selected = [t for t in selected if t!=name]
        config = {'name':'armada-turn','description':'Current Armada request with explicit tool and memory boundaries.',
            'mainAgent':True,'subagent':False,'inheritMcp':False,'inheritCustomizations':False,
            'excludeDefaultComponents':True,'commandExecutionPolicy':'off','tools':selected,
            'mcpServers':self._connectors(denied) if allow_tools else []}
        # JSON is valid YAML and prevents instructions from becoming frontmatter directives.
        if allow_tools and self.allowed_mcp_ids & self.native_filesystem_ids:
            system += ('\n\n[Filesystem capability for this Gemini turn]\n'
                       'Use the native file tools for your assigned filesystem capability. '
                       'They are restricted to this run\'s approved folders. '
                       'No separate filesystem connector login is needed.\n')
        return '---\n'+json.dumps(config,ensure_ascii=False)+'\n---\n# System Prompt\n'+system+'\n'
    def run(self,system,prompt,**kwargs): return self.run_stream(system,prompt,**kwargs)
    def run_stream(self,system,prompt,model=None,cwd=None,allow_tools=False,timeout=300,effort=None,
            fallback_model=None,max_budget_usd=None,disallowed_tools=None,only_tools=None,
            verbosity=None,on_event=None,on_proc=None):
        validate_request(self.name,self.capabilities,RunRequest(system,prompt,model=model,fallback_model=fallback_model,
            max_budget_usd=max_budget_usd,disallowed_tools=tuple(disallowed_tools or ()),only_tools=None if only_tools is None else tuple(only_tools)))
        if not self._launcher(): return RunResult(ok=False,error="Gemini's Antigravity CLI is not installed. Install it in Settings → App.")
        if not self.auth_status().get('logged_in'): return RunResult(ok=False,error='Gemini is signed out. Sign in in Settings → App.')
        mid = model_id(model); row = next((m for m in cached_models() if m['id']==mid),None)
        level = effort or 'medium'
        if level in ('xhigh','max'): level = 'high'
        if level=='auto': level = 'medium'
        if level not in ('low','medium','high'): raise ValueError('Gemini thinking must be low, medium or high.')
        if row and level not in row['efforts']: level = 'high'
        actual = mid+'-'+level
        terminal = None; chunks = []; started = set(); finished = set()
        def line(raw):
            nonlocal terminal
            if not raw.strip(): return
            item = json.loads(raw)
            if not isinstance(item,dict): raise ValueError('Malformed Gemini stream event')
            kind = item.get('event')
            if kind=='init': safe_emit(on_event,{'kind':'start'})
            elif kind=='step_update':
                step = item.get('step_update') or {}; text = step.get('text_delta')
                if step.get('step_type')=='agent_response' and text:
                    chunks.append(text); safe_emit(on_event,{'kind':'text','text':text})
                elif step.get('step_type')=='tool':
                    tid = str(step.get('step_index')); info = step.get('tool_info') or {}; name = step.get('tool_name') or info.get('name') or 'tool'
                    if tid not in started:
                        params = info.get('parameters') or {}
                        canonical = next((alias for alias, original in _ALIASES.items() if original == name), name)
                        if name == 'multi_replace_file_content': canonical = 'MultiEdit'
                        target = params.get('TargetFile') or params.get('AbsolutePath')
                        if target: params = {**params, 'file_path':target}
                        started.add(tid); safe_emit(on_event,{'kind':'tool','name':canonical,'id':tid,'input':params})
                    if step.get('state')=='DONE' and tid not in finished:
                        finished.add(tid); safe_emit(on_event,{'kind':'tool_result','id':tid,'content':info.get('output') or str(info.get('error') or ''),'is_error':bool(info.get('error'))})
            elif kind=='result':
                if terminal is not None: raise ValueError('Duplicate Gemini final result')
                terminal = item.get('result')
                if not isinstance(terminal,dict): raise ValueError('Malformed Gemini final result')
        if verbosity:
            from ..verbosity import prompt_block
            system += '\n\n' + prompt_block(verbosity)
        agent = self._agent(system,allow_tools,disallowed_tools or [])
        selected_tools = json.loads(agent.split('---',2)[1])['tools']
        file_access = bool(set(selected_tools) & set(_FILE_TOOLS))
        with tempfile.TemporaryDirectory(prefix='armada-gemini-') as folder:
            path = Path(folder)/'.agents/agents/armada-turn.md'; path.parent.mkdir(parents=True)
            path.write_text(agent,encoding='utf-8')
            args = self._launcher()+['--agent','armada-turn','--model',actual,'--disable-slash-commands',
                '--input-format','stream-json','--output-format','stream-json','--print-timeout','0']
            work = Path(cwd or os.getcwd()).resolve()
            roots = [work]+[Path(p).resolve() for p in self.writable_roots if Path(p).is_dir() and not work.is_relative_to(Path(p).resolve())]
            if file_access:
                for root in dict.fromkeys(roots): args += ['--add-dir',str(root)]
            body = json.dumps({'event':'user','message':{'content':prompt}},ensure_ascii=False)
            servers = [entry['name'] for entry in self._connectors(disallowed_tools or [])] if allow_tools else []
            with scoped_project(list(dict.fromkeys(roots)) if file_access else [],servers,allow_tools and self.network_access) as project:
                result = supervise(args+['--project',project],prompt=body,on_line=line,timeout=timeout,cwd=folder,on_proc=on_proc)
        stats = (terminal or {}).get('usage') or {}; cached = stats.get('cache_read_tokens') or 0; incoming = stats.get('input_tokens')
        # CLI input includes cached tokens; Armada's total adds cache reads separately.
        usage = Usage(input=max(0,incoming-cached) if isinstance(incoming,int) else None,output=stats.get('output_tokens'),cache_read=cached)
        error = result.error or ('Gemini CLI failed: '+result.stderr[-1500:] if result.returncode else '')
        status = (terminal or {}).get('status')
        if not terminal: error = error or 'Gemini ended without a final result.'
        elif status!='SUCCESS': error = error or str(terminal.get('error') or 'Gemini ended with status '+str(status))
        answer = (terminal or {}).get('response'); output = answer if isinstance(answer,str) and answer else ''.join(chunks)
        if result.cancelled: error = error or 'Gemini run was stopped.'
        if result.timed_out: error = error or 'Gemini run timed out.'
        if not output.strip():
            reason = next((line for line in result.stderr.splitlines() if 'no output produced' in line), '')
            error = error or reason.split('Add an allow-rule')[0].strip() or 'Gemini returned an empty response.'
        return RunResult(ok=not error,output=output,model=actual,usage=usage,error=error,
            cancelled=result.cancelled or status in ('CANCELED','INTERRUPTED'),timed_out=result.timed_out,
            raw={'result':terminal or {},'diagnostics':result.stderr})
