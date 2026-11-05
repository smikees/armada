"""Owner repair UI, kept separate from ordinary configuration forms."""
import hashlib
from html import escape

from .. import records


def panel(root, agent, job, problem):
    path = records.target(root, agent, job)
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig", errors="replace")
    except OSError:
        return ('<section style="padding:24px"><h1>Record needs repair</h1><p>' +
                escape(problem) + '</p><p>Restore this missing or inaccessible file from a verified backup. '
                'ARMADA has not changed it.</p></section>')
    return f'''<section style="padding:24px;max-width:900px">
<h1>Record needs repair</h1><p role="alert">{escape(problem)}</p>
<p>Work for this record is held. Healthy agents remain available. Nothing has been reset.</p>
<p>Review the complete replacement JSON, including all permissions. Applying it preserves the
original bytes and an owner repair receipt in <code>.armada/record-repairs/</code>.</p>
<form id="record-repair" data-agent="{escape(agent, quote=True)}" data-job="{escape(job, quote=True)}"
 data-digest="{digest}">
<label for="replacement">Replacement JSON — restore from a trusted backup where possible</label>
<textarea id="replacement" style="display:block;width:100%;min-height:320px;font-family:monospace"
 spellcheck="false">{escape(text)}</textarea>
<p><label><input id="repair-reviewed" type="checkbox" required> I have reviewed the replacement and its permissions.</label></p>
<button type="submit">Preserve original and apply repair</button>
<p id="repair-result" role="status"></p></form></section>
<script>
document.getElementById('record-repair').addEventListener('submit',async function(event){{
 event.preventDefault(); const button=this.querySelector('button'); button.disabled=true;
 const result=document.getElementById('repair-result');
 try{{const response=await fetch('/api/repair-record',{{method:'POST',headers:{{'Content-Type':'application/json'}},
 body:JSON.stringify({{agent:this.dataset.agent,job:this.dataset.job,expected_sha256:this.dataset.digest,
 replacement:document.getElementById('replacement').value,reviewed:document.getElementById('repair-reviewed').checked}})}});
 const data=await response.json(); if(!data.ok) throw new Error(data.error||'Repair failed');
 result.textContent='Repair saved. Original preserved at '+data.backup+'. Reload this page to continue.';
 }}catch(error){{result.textContent=error.message;button.disabled=false;}}
}});
</script>'''
