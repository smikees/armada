"""Bounded owner questions; only the supervising protocol thread writes answers."""
import copy
import json
import threading
import uuid


def normalize(rows,provider):
    if not isinstance(rows,list) or not 1<=len(rows)<=8:
        raise ValueError('The agent returned an invalid question set.')
    result=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or row.get('isSecret'):
            raise ValueError('Credentials must be entered in Settings, never in thread questions.')
        text=row.get('question')
        if not isinstance(text,str) or not text.strip() or len(text)>8000 or '\0' in text:
            raise ValueError('The agent returned an invalid question.')
        options=row.get('options') or []
        if not isinstance(options,list) or len(options)>20:
            raise ValueError('The agent returned invalid question options.')
        choices=[]
        for option in options:
            if not isinstance(option,dict) or not isinstance(option.get('label'),str) or not option['label'].strip() or len(option['label'])>1000:
                raise ValueError('The agent returned an invalid question option.')
            choices.append({'label':option['label'],'description':str(option.get('description') or '')[:4000]})
        identity=str(row.get('id') or index) if provider=='codex' else text
        if len(identity)>8000 or '\0' in identity or any(q['id']==identity for q in result):
            raise ValueError('The agent returned duplicate question IDs.')
        result.append({'id':identity,'question':text,'header':str(row.get('header') or '')[:80],
            'options':choices,'multi_select':bool(row.get('multiSelect')),
            'allow_other':provider=='claude' or bool(row.get('isOther')) or not choices})
    if len(json.dumps(result,ensure_ascii=False).encode('utf-8'))>65536:
        raise ValueError('The question set exceeds the 64 KiB limit.')
    return result


def validate_answers(questions,answers,cancelled=False):
    if cancelled:
        if answers:
            raise ValueError('A skipped question cannot also contain answers.')
        return {}
    if not isinstance(answers,dict) or set(answers)!={q['id'] for q in questions}:
        raise ValueError('Answer each question before sending.')
    result={}
    for q in questions:
        values=answers[q['id']]
        if not isinstance(values,list) or not values or len(values)>20 or (not q['multi_select'] and len(values)!=1):
            raise ValueError('Choose an answer for each question.')
        if any(not isinstance(v,str) or not v.strip() or len(v)>16000 or '\0' in v for v in values):
            raise ValueError('Answers must contain 1–16,000 characters.')
        if len(set(values))!=len(values):
            raise ValueError('An answer cannot be selected twice.')
        if not q['allow_other'] and any(v not in {o['label'] for o in q['options']} for v in values):
            raise ValueError('Choose one of the offered answers.')
        result[q['id']]=list(values)
    if sum(len(v) for values in result.values() for v in values)>32000:
        raise ValueError('These answers exceed the 32,000-character limit.')
    return result


class QuestionControl:
    def __init__(self,emit):
        self.emit=emit
        self.lock=threading.RLock()
        self.rows={}
        self.closed=False

    def snapshot(self):
        with self.lock:
            return [copy.deepcopy(row['public']) for row in self.rows.values()]

    @property
    def waiting(self):
        with self.lock:
            return any(row['public']['status']=='pending' for row in self.rows.values())

    def add(self,native_id,provider,questions,reply):
        if isinstance(native_id,bool) or not isinstance(native_id,(str,int)):
            raise ValueError('The engine returned an invalid question ID.')
        normalized=normalize(questions,provider)
        with self.lock:
            if self.closed or len(self.rows)>=32:
                raise ValueError('This run cannot accept more questions.')
            for row in self.rows.values():
                if row['native_id']==native_id:
                    if row['public']['questions']!=normalized:
                        raise ValueError('The engine reused a question ID.')
                    return
            public={'id':uuid.uuid4().hex,'provider':provider,'questions':normalized,'status':'pending','answers':{},'skipped':False}
            self.rows[public['id']]={'native_id':native_id,'public':public,'reply':reply}
        self.emit({'kind':'question','request':copy.deepcopy(public)})

    def answer(self,identity,answers,cancelled=False,persist=None):
        with self.lock:
            row=self.rows.get(identity)
            if row is None or self.closed:
                raise ValueError('This question is no longer waiting for an answer.')
            public=row['public']
            values=validate_answers(public['questions'],answers,cancelled)
            if public['status']!='pending':
                if public['answers']==values and public['skipped']==cancelled:
                    return copy.deepcopy(public)
                raise ValueError('This question was already answered in another view.')
            change={**public,'status':'queued','answers':values,'skipped':cancelled}
            if persist:
                persist(copy.deepcopy(change))
            public.update(change)
            return copy.deepcopy(public)

    def drain(self,send):
        with self.lock:
            queued=[row for row in self.rows.values() if row['public']['status']=='queued']
            for row in queued:
                row['public']['status']='skipped' if row['public']['skipped'] else 'submitted'
        for row in queued:
            send(row['reply'](row['public']['answers'],row['public']['skipped']))
            self.emit({'kind':'question','request':copy.deepcopy(row['public'])})

    def resolve(self,native_id):
        events=[]
        with self.lock:
            for row in self.rows.values():
                public=row['public']
                if row['native_id']==native_id and public['status'] in ('pending','queued','submitted'):
                    public['status']='answered' if public['status']=='submitted' else 'cancelled'
                    events.append(copy.deepcopy(public))
        for public in events:
            self.emit({'kind':'question','request':public})

    def close(self,success=False):
        events=[]
        with self.lock:
            if self.closed:
                return
            self.closed=True
            for row in self.rows.values():
                public=row['public']
                if public['status'] in ('pending','queued','submitted'):
                    public['status']=('answered' if success else 'uncertain') if public['status']=='submitted' else 'cancelled'
                    events.append(copy.deepcopy(public))
        for public in events:
            self.emit({'kind':'question','request':public})


class QuestionProcess:
    def __init__(self,process,questions):
        self.process,self.questions=process,questions

    def __getattr__(self,name):
        return getattr(self.process,name)

    def kill(self):
        self.process.kill()
        self.questions.close()
