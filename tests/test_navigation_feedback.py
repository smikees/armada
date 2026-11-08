"""Navigation feedback must not hijack downloads, actions, new tabs or same-page links."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_navigation_guards_in_javascript():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for JavaScript behavior checks')
    source = Path(__file__).resolve().parents[1] / 'armada/webui/static/js/navigation.js'
    code = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
function fixture(modern){
  const handlers={},native={},touches=[];
  const location=new URL('http://127.0.0.1:8756/jobs?_realm=synthetic');
  const window={addEventListener:(n,f)=>handlers[n]=f};
  if(modern)window.navigation={addEventListener:(n,f)=>native[n]=f};
  const document={querySelector:s=>{touches.push(s);return null;}};
  vm.runInNewContext(source,{window,navigation:window.navigation,document,location,URL,setTimeout,clearTimeout});
  return {handlers,native,touches,window};
}
let f=fixture(true);
function modern(url,extra={}){f.touches.length=0;f.native.navigate({destination:{url,sameDocument:false},
  preventDefault(){throw Error('Navigation was intercepted');},...extra});return f.touches.length;}
assert(modern('/artefacts')>0);
for(const path of ['/api/delete-file','/switch?path=other','/file?path=x','/static/x','/constructor',
  'https://external.example/artefacts','javascript:alert(1)'])assert.equal(modern(path),0,path);
for(const extra of [{defaultPrevented:true},{hashChange:true},{downloadRequest:''},{downloadRequest:'report.pdf'},
  {formData:{}},{destination:{url:'/jobs',sameDocument:true}}])assert.equal(modern('/artefacts',extra),0);
f=fixture(false);
function click(href,extra={},linkExtra={}){f.touches.length=0;
  const link={href,target:'',hasAttribute:()=>false,...linkExtra};
  f.handlers.click({button:0,target:{closest:()=>link},preventDefault(){throw Error('Click was intercepted');},...extra});
  return f.touches.length;}
assert(click('http://127.0.0.1:8756/artefacts?_realm=synthetic')>0);
for(const extra of [{defaultPrevented:true},{button:1},{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true}])
  assert.equal(click('/artefacts',extra),0);
assert.equal(click('/artefacts',{}, {target:'_blank'}),0);
assert.equal(click('/artefacts',{}, {hasAttribute:()=>true}),0);
assert.equal(click('http://127.0.0.1:8756/jobs?_realm=synthetic#details'),0);
assert.equal(click('https://external.example/artefacts'),0);
assert.equal(click('/api/delete-file'),0);
f.touches.length=0;f.window.mcNavigationPending('/section/0');assert(f.touches.length>0);
'''
    subprocess.run([node, '-e', code, str(source)], check=True, capture_output=True, text=True, timeout=15)
