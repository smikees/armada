"""Real elapsed-time scheduled/Inbox deadline check with a synthetic streaming CLI.

Runs concurrently without paid requests. --seconds 2700 checks both 45-minute paths;
the third job must still stop at the explicit --ceiling (normally 600 seconds).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--controller',required=True)
    parser.add_argument('--data',required=True)
    parser.add_argument('--fixture',required=True)
    parser.add_argument('--seconds',type=float,default=2700)
    parser.add_argument('--ceiling',type=float,default=600)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    sys.path.insert(0,args.controller)
    os.environ['ARMADA_DATA_DIR']=args.data
    os.environ['ARMADA_NO_EXTERNAL_NOTIFY']='1'
    from armada import runner,util,run_policy
    from armada.engine.claude import ClaudeEngine
    root=Path(args.fixture).resolve();root.mkdir(parents=True,exist_ok=True)
    cli=root/'synthetic_cli.py'
    cli.write_text('import sys,time,json\nsys.stdin.read()\nend=time.monotonic()+'+repr(args.seconds)+'\n'
        'while time.monotonic()<end:\n print(json.dumps({"type":"system","subtype":"status","status":"working"}),flush=True)\n time.sleep(min(10,max(0,end-time.monotonic())))\n'
        'print(json.dumps({"type":"result","subtype":"success","is_error":False,"result":"Healthy synthetic run finished.","total_cost_usd":0,"usage":{"input_tokens":1,"output_tokens":1}}),flush=True)\n',encoding='utf-8')
    util.write_json_atomic(root/'realm.json',{'name':'Synthetic elapsed-time probe','default_model':'claude-sonnet-5'})
    for agent in ('scheduled','inbox','ceiling'):
        util.write_json_atomic(root/'agents'/agent/'agent.json',{'id':agent,'allow_tools':False,'model':'claude-sonnet-5'})
        job={'id':'work','kind':'agent','prompt':'Wait for the synthetic completion.','allow_tools':False,'enabled':True}
        if agent=='ceiling':job['timeout']=args.ceiling
        util.write_json_atomic(root/'agents'/agent/'jobs/work.json',job)
        run_policy.seal_job(root,agent,job)
    class Synthetic(ClaudeEngine):
        def __init__(self):
            super().__init__()
            self.measurements={}
        def _launcher(self):return [sys._base_executable,str(cli)]
        def run_stream(self,**kwargs):
            started=time.monotonic()
            self.measurements['timeout']=kwargs.get('timeout')
            try:return super().run_stream(**kwargs)
            finally:self.measurements['active_elapsed']=time.monotonic()-started
    def run(agent):
        start=time.monotonic()
        engine=Synthetic()
        report=(runner.run_job_prompt(root,agent,'Wait for the synthetic completion.',engine=engine,allow_tools=False)
                if agent=='inbox' else runner.run_job(root,agent,'work',engine=engine))
        return {'elapsed':time.monotonic()-start,'status':report.get('status'),'error':report.get('error',''),
                'detail':report.get('summary',''),**engine.measurements}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={name:pool.submit(run,name) for name in ('scheduled','inbox','ceiling')}
        results={name:future.result() for name,future in futures.items()}
    passed=(all(results[name]['status']=='ok' and results[name].get('timeout') is None and results[name].get('active_elapsed',0)>=args.seconds for name in ('scheduled','inbox'))
            and results['ceiling']['status']!='ok' and args.ceiling<=results['ceiling'].get('active_elapsed',0)<args.ceiling+15)
    result={'passed':passed,'seconds':args.seconds,'ceiling':args.ceiling,'runs':results}
    util.write_json_atomic(Path(args.output),result)
    print(json.dumps(result,indent=2))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
