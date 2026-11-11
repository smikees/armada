"""Invocation-local Anthropic gateway: real keys stay in the host, requests are bounded.

Only Messages and free token counting are exposed. Unknown model prices, server tools,
premium service tiers and unbounded requests fail closed before paid work is forwarded.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import math
import secrets
import re
import threading
from urllib.parse import urlsplit
import urllib.error
import urllib.request


class Budget:
    def __init__(self, ceiling):
        self.remaining = float(ceiling)
        self.lock = threading.Lock()
        self.charges = 0
        self.completed = 0
        self.actual_cost = 0.0

    def authorise(self, body, input_tokens):
        from .token_cost import estimate
        unsupported = set(body)-{'model','messages','system','tools','tool_choice','thinking','max_tokens','stream','temperature',
                                'top_p','top_k','stop_sequences','metadata','cache_control','output_config','service_tier','speed','context_management'}
        if unsupported:
            raise ValueError('API fallback cannot bound this request feature: '+', '.join(sorted(unsupported))+'. Use the subscription.')
        def immutable_inputs(value):
            if isinstance(value, dict):
                source = value.get('source')
                if source and value.get('type') in ('image','document','audio','video'):
                    raise ValueError('API fallback cannot bound inline media billing. Wait for the subscription reset for this input.')
                if isinstance(source,dict) and source.get('type') in ('url','file'):
                    raise ValueError('API fallback requires inline inputs so token counting and billing see the same content.')
                for item in value.values():
                    immutable_inputs(item)
            elif isinstance(value,list):
                for item in value:
                    immutable_inputs(item)
        immutable_inputs(body)
        if type(input_tokens) is not int or not 0 <= input_tokens <= 1_000_000:
            raise ValueError('API lane closed: input token count is unknown or exceeds the supported context.')
        maximum = body.get('max_tokens')
        if type(maximum) is not int or maximum <= 0:
            raise ValueError('API requests must declare a positive output token ceiling.')
        if body.get('service_tier') not in (None, 'standard_only') or body.get('speed') not in (None, 'standard'):
            raise ValueError('API fallback does not admit premium service tiers.')
        for tool in body.get('tools', []):
            if tool.get('type') not in (None, 'custom'):
                raise ValueError('API fallback cannot bound provider-hosted tool fees. Use the subscription or a directly registered MCP tool.')
        management = body.get('context_management') or {}
        if set(management)-{'edits'} or any(edit.get('type') not in ('clear_thinking_20251015','clear_tool_uses_20250919') for edit in management.get('edits', [])):
            raise ValueError('API fallback cannot bound server-side context compaction. Use the subscription.')
        # Conservative bounds cover long-context pricing and 1-hour cache creation.
        # Do not discount cache hits: counting cannot prove which cache will be used.
        model = str(body.get('model') or '')
        known = re.fullmatch(r'claude-(?:(?:fable|mythos)-(?:5|5-1|5-2)|opus-(?:5|5-5|4-[5-8])|sonnet-(?:5|5-5|4-[56])|haiku-(?:4-5|5-5))(?:-\d{8})?',model)
        if not known:
            raise ValueError('API lane closed: this model has no verified price bound in Armada.')
        # Token counts are estimates. Add generous fixed and proportional headroom.
        # Text tokenization cannot exceed its UTF-8 byte representation. Bound the
        # complete JSON as well as the provider estimate; never depend on a token
        # counting underestimate to enforce the owner's monetary ceiling.
        bounded_input = max(math.ceil(input_tokens*1.1)+1024,
                            len(json.dumps(body,ensure_ascii=False).encode('utf-8'))+2048)
        charge = estimate(model, {'input':bounded_input*4, 'output':maximum*2,
                                            'cache_read':0, 'cache_write':0})
        if model.startswith('claude-haiku-5-5'):
            charge = (bounded_input*4*.5+maximum*2*2.5)/1_000_000
        if charge is None:
            raise ValueError('API lane closed: this model has no verified price bound in Armada.')
        charge = math.ceil(charge*1_000_000)/1_000_000
        with self.lock:
            if charge > self.remaining+1e-9:
                raise ValueError('API request held: its maximum possible cost exceeds the remaining run reservation.')
            self.remaining -= charge
            self.charges += 1
        # Retain the full bound until this request has complete provider usage.
        return charge

    def finish(self, model, reservation, usage):
        """Release unused request capacity only after terminal usage is complete."""
        from .token_cost import estimate
        counts = [usage.get(name,0) for name in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')]
        if any(type(value) is not int or value < 0 for value in counts) or not all(name in usage for name in ('input_tokens','output_tokens')):
            return
        inputs,outputs,reads,writes = counts
        charge = estimate(model, {'input':inputs*2+writes*4,'output':outputs*2,'cache_read':reads*2,'cache_write':0})
        if model.startswith('claude-haiku-5-5'):
            charge = ((inputs*2+writes*4)*.5+outputs*2*2.5+reads*2*.05)/1_000_000
        if charge is None:
            return
        with self.lock:
            self.remaining += max(0,reservation-charge)
            actual = metered_cost(model, usage)
            if actual is not None:
                self.actual_cost += actual
                self.completed += 1

    def cost(self):
        """Independent provider usage prevents a worker from understating CLI totals."""
        with self.lock:
            return self.actual_cost if self.completed == self.charges else None


def metered_cost(model, usage):
    """Verified first-party standard rates, applied to the provider's actual counters.

    November 11, 2026 pricing. Unknown cache duration or a legacy long-context tier
    closes reconciliation; the invocation keeps its full reserved ceiling.
    """
    model = re.sub(r'-\d{8}$','',model)
    models = {
        'claude-fable-5-2':(8,40,.2), 'claude-mythos-5-2':(8,40,.2),
        'claude-fable-5-1':(10,50,.25), 'claude-mythos-5-1':(10,50,.25),
        'claude-fable-5':(10,50,1), 'claude-mythos-5':(10,50,1),
        'claude-opus-5-5':(4,20,.2), 'claude-sonnet-5-5':(2,10,.1),
        'claude-opus-5':(5,25,.5), 'claude-sonnet-5':(2,10,.2),
        'claude-haiku-4-5':(1,5,.1),
        **{f'claude-opus-4-{v}':(5,25,.5) for v in (5,6,7,8)},
        **{f'claude-sonnet-4-{v}':(3,15,.3) for v in (5,6)},
    }
    values = [usage.get(k,0) for k in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')]
    if any(type(v) is not int or v < 0 for v in values):
        return None
    inputs, outputs, reads, writes = values
    context = inputs+reads+writes
    rates = models.get(model)
    if model == 'claude-haiku-5-5':
        rates = (.5,2.5,.05) if context > 100000 else (.1,.5,.01)
    if rates is None or context > 200000 and model in ('claude-opus-4-5','claude-sonnet-4-5'):
        return None
    five = hour = 0
    if writes:
        cache = usage.get('cache_creation') or {}
        five, hour = cache.get('ephemeral_5m_input_tokens'), cache.get('ephemeral_1h_input_tokens')
        if any(type(v) is not int or v < 0 for v in (five,hour)) or five+hour != writes:
            return None
    amount = (inputs*rates[0]+outputs*rates[1]+reads*rates[2]+five*rates[0]*1.25+hour*rates[0]*2)/1_000_000
    return math.ceil(amount*1_000_000_000)/1_000_000_000


class _Usage:
    """Read usage counters without persisting provider text or tool arguments."""
    def __init__(self, streaming):
        self.streaming = streaming
        self.pending = b''
        self.usage = {}
        self.complete = False

    def add(self, chunk):
        self.pending += chunk
        if len(self.pending) > 16*1024*1024:
            raise ValueError('API usage event exceeded the supported size; its full budget remains reserved.')
        if self.streaming:
            while b'\n' in self.pending:
                line,self.pending = self.pending.split(b'\n',1)
                if line.startswith(b'data:'):
                    self.event(json.loads(line[5:]))

    def event(self, value):
        if value.get('type') == 'message_start':
            self.usage.update(value.get('message',{}).get('usage') or {})
        elif value.get('type') == 'message_delta':
            self.usage.update(value.get('usage') or {})
        elif value.get('type') == 'message_stop':
            self.complete = True

    def finish(self):
        if not self.streaming:
            value = json.loads(self.pending)
            self.usage = value.get('usage') or {}
            self.complete = bool(value.get('stop_reason'))
        return self.complete


class Gateway:
    def __init__(self, key, ceiling):
        self._key = key
        self.token = 'armada-run-'+secrets.token_urlsafe(32)
        self.budget = Budget(ceiling)
        self.closed = False
        self.inflight = 0
        self.lock = threading.Lock()
        self.server = self.worker = None

    def _open(self, path, body, headers):
        if self.closed:
            raise OSError('This API invocation has ended.')
        # Fixed origin, fixed paths and disabled redirects: a client cannot exfiltrate
        # the key through an absolute URL, redirect or attacker-supplied Host header.
        request = urllib.request.Request('https://api.anthropic.com'+path,
            data=json.dumps(body).encode('utf-8'), headers={
                'Content-Type':'application/json', 'anthropic-version':headers.get('anthropic-version','2023-06-01'),
                'anthropic-beta':headers.get('anthropic-beta',''), 'x-api-key':self._key})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        return urllib.request.build_opener(NoRedirect).open(request, timeout=60)

    def count(self, body, headers):
        counting = {k:v for k,v in body.items() if k in ('model','messages','system','tools','tool_choice','thinking')}
        with self._open('/v1/messages/count_tokens', counting, headers) as response:
            return json.loads(response.read(65536)).get('input_tokens')

    def __enter__(self):
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'
            def log_message(self, *args):
                pass  # Never log credentials, provider bodies or prompts.
            def error(self, code, message):
                raw = json.dumps({'type':'error','error':{'type':'invalid_request_error','message':message}}).encode()
                self.send_response(code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_POST(self):
                counted = False
                path = urlsplit(self.path).path
                token = self.headers.get('x-api-key') or self.headers.get('Authorization','').removeprefix('Bearer ')
                if gateway.closed or not hmac.compare_digest(token, gateway.token):
                    self.error(403, 'This API invocation is not authorised.')
                    return
                if path not in ('/v1/messages','/v1/messages/count_tokens'):
                    self.error(403, 'This API endpoint is not available to agent runs.')
                    return
                try:
                    with gateway.lock:
                        if gateway.closed:
                            raise ValueError('This API invocation has ended.')
                        gateway.inflight += 1
                        counted = True
                    length = int(self.headers.get('Content-Length',0))
                    if not 0 < length <= 16*1024*1024:
                        raise ValueError('API request exceeds the supported size.')
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError('API request must be an object.')
                    if path == '/v1/messages':
                        # All billing checks precede the first paid request.
                        reservation = gateway.budget.authorise(body, gateway.count(body, self.headers))
                    with gateway._open(path, body, self.headers) as response:
                        usage = _Usage('text/event-stream' in response.headers.get('Content-Type',''))
                        self.send_response(response.status)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                        self.end_headers()
                        while chunk := response.read1(65536):
                            if path == '/v1/messages':
                                usage.add(chunk)
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        if path == '/v1/messages' and usage.finish():
                            gateway.budget.finish(body['model'],reservation,usage.usage)
                except urllib.error.HTTPError as exc:
                    # Provider errors can contain request/credential details. Status alone is enough.
                    self.error(exc.code, f'Anthropic declined the API request (HTTP {exc.code}).')
                except (ValueError, TypeError, KeyError) as exc:
                    self.error(400, str(exc))
                except (OSError, urllib.error.URLError):
                    self.error(502, 'The Anthropic API request could not be completed. Its budget remains reserved.')
                finally:
                    if counted:
                        with gateway.lock:
                            gateway.inflight -= 1
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads = True
        self.worker = threading.Thread(target=self.server.serve_forever,name='api-budget-gateway',daemon=True)
        self.worker.start()
        return self

    @property
    def env(self):
        import os
        no_proxy = os.environ.get('NO_PROXY','')+',127.0.0.1,localhost'
        return {'ANTHROPIC_API_KEY':self.token, 'ANTHROPIC_BASE_URL':f'http://127.0.0.1:{self.server.server_port}',
                'NO_PROXY':no_proxy, 'no_proxy':no_proxy,
                'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB':'1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}

    def __exit__(self, *args):
        self.closed = True
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self._key = ''
