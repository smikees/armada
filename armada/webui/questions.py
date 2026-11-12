"""Escaped question/answer receipts retained with the original owner turn."""
from ._base import E


def history(requests,*,running=False):
    rows=[]
    for request in requests:
        state=request.get('status')
        if state in ('pending','queued'):
            if running:
                continue
            state='cancelled'
        label={'submitted':'Answer sent','answered':'Your answer','uncertain':'Answer delivery unconfirmed',
            'skipped':'Question skipped','cancelled':'Question closed without an answer'}.get(state,'Question closed')
        blocks=''
        for question in request.get('questions',[]):
            answers=request.get('answers',{}).get(question['id'],[])
            blocks+=f'<p class="mc-question-text">{E(question["question"])}</p>'
            if answers:
                blocks+=f'<p><strong>{E(label)}:</strong> {E(", ".join(answers))}</p>'
        if not request.get('answers'):
            blocks+=f'<p class="mc-hint">{E(label)}</p>'
        rows.append(f'<section class="mc-question-history" aria-label="Agent question">{blocks}</section>')
    return ''.join(rows)
