"""Claude's documented SDK stdio control protocol, restricted to AskUserQuestion."""
import json
import time
from .process import supervise_rpc
from .questions import QuestionControl,QuestionProcess
from .claude_steering import ClaudeSteering
from .codex_steering import SteeringProcess


def run(engine,launcher,args,prompt,state,accept,emit,on_event,on_proc,timeout,cwd,env):
    questions=QuestionControl(emit)
    steering=ClaudeSteering()
    args=list(args)+['--input-format','stream-json','--replay-user-messages','--permission-prompt-tool','stdio','--permission-prompts','host']
    # No-tool and managed-tool turns may still ask the owner a question, but gain
    # no filesystem, shell, connector or permission-changing tool.
    if '--tools' in args and args[args.index('--tools')+1]=='':
        args[args.index('--tools')+1]='AskUserQuestion'
    initialized=False
    session_phase=None
    background=set()
    result_received=False
    responses=[]
    started=time.monotonic()
    def reply(identity,response):
        return {'type':'control_response','response':{'subtype':'success','request_id':identity,'response':response}}
    def start(send):
        send({'type':'control_request','request_id':'armada-question-init','request':{'subtype':'initialize','hooks':None}})
    def receive(message,send):
        nonlocal initialized,session_phase,result_received
        kind=message.get('type')
        if kind=='control_response':
            response=message.get('response') or {}
            if response.get('request_id')=='armada-question-init' and not initialized:
                if response.get('subtype')!='success':
                    raise ValueError('Claude could not initialize interactive questions. Update Claude Code and try again.')
                initialized=True
                # Human-priority input needs Claude Code 2.1.286+. Earlier CLIs
                # retain questions and ordinary runs without advertising steering.
                version=(response.get('response') or {}).get('claude_code_version', '')
                try:
                    steering.enabled=tuple(int(x) for x in version.split('.')[:3]) >= (2,1,286)
                except (ValueError, AttributeError):
                    steering.enabled=False
                send({'type':'user','session_id':'','message':{'role':'user','content':prompt},'parent_tool_use_id':None})
            return False
        if kind=='control_request':
            request=message.get('request') or {}
            identity=message.get('request_id')
            if not isinstance(identity,str) or not identity:
                raise ValueError('Claude returned an invalid control request.')
            if request.get('subtype')=='can_use_tool' and request.get('tool_name')=='AskUserQuestion':
                original=request.get('input') or {}
                def answer(values,skipped):
                    result={'behavior':'deny','message':'The owner skipped these questions. Do not assume an answer.'} if skipped else {
                        'behavior':'allow','updatedInput':{**original,'answers':{key:', '.join(value) for key,value in values.items()}}}
                    return reply(identity,result)
                try:
                    questions.add(identity,'claude',original.get('questions'),answer)
                except ValueError as exc:
                    send(reply(identity,{'behavior':'deny','message':str(exc)}))
            else:
                send(reply(identity,{'behavior':'deny','message':'Armada does not grant interactive tool approvals. Use the owner-approved tool settings.'}))
            return False
        if kind=='control_cancel_request':
            questions.resolve(message.get('request_id'))
            return False
        steering.observe(message)
        if kind=='user' and message.get('isReplay'):
            return False
        if kind=='system':
            subtype=message.get('subtype')
            task=message.get('task_id')
            if subtype=='session_state_changed':
                session_phase=message.get('state')
                if session_phase=='idle' and result_received and not background and not questions.waiting:
                    # Idle means the native input queue is empty. A hook can
                    # discard a follow-up without ever producing its own result.
                    steering.close()
            elif task and subtype=='task_started' and message.get('task_type') in ('local_agent','local_workflow'):
                background.add(task)
            elif task and (subtype=='task_notification' or subtype=='task_updated' and
                    (message.get('patch') or {}).get('status') in ('completed','failed','stopped','cancelled')):
                background.discard(task)
        # Keep the existing strict parser per turn. SDK lifecycle frames may
        # follow a result, and delegated work can start a continuation turn.
        if not (state.completed and kind=='system'):
            if state.completed and kind in ('assistant','stream_event','user','result','error'):
                state.completed=False
                if steering.requests:
                    state.texts.append('\n\n')
                    emit({'kind':'text','text':'\n\n'})
            accept(json.dumps(message,ensure_ascii=False))
        if kind=='result':
            result_received=True
            if isinstance(message.get('result'),str) and message['result'].strip() and not state.error:
                responses.append(message['result'].strip())
            if steering.waiting and 'interrupt' in state.error.lower():
                # Human input may interrupt the current provider turn and start
                # another in this same session. Do not end the owner run early.
                state.error=''
        # A result ends one turn. The CLI's idle signal ends the whole run,
        # including follow-up turns from delegated work. Older CLIs use the
        # task ledger as the guard; long-running background shells are excluded.
        terminal=kind=='result' or kind=='system' and message.get('subtype')=='session_state_changed' and session_phase=='idle'
        return bool(state.error or terminal and state.completed and result_received and not background and not steering.waiting and
                    session_phase in (None,'idle') and not questions.waiting)
    def tick(send):
        if not initialized and time.monotonic()-started>60:
            raise ValueError('Claude did not initialize interactive input within 60 seconds.')
        questions.drain(send)
        steering.drain(send)
    process=None
    try:
        process=supervise_rpc(launcher+args,start=start,on_message=receive,timeout=timeout,cwd=cwd,
            env={**engine._env(),**(env or {}),'CLAUDE_CODE_SDK_READS_SESSION_STATE':'1'},
            on_proc=lambda p:on_proc(QuestionProcess(SteeringProcess(p,steering),questions)) if on_proc else None,on_tick=tick)
        return process
    finally:
        if steering.requests and responses:
            # Native input can continue in another provider turn. Keep its earlier
            # answer text as well as the latest result in Armada's saved response.
            state.output='\n\n'.join(responses)
        steering.close()
        questions.close(success=bool(process and not process.error and state.completed and not state.error))
