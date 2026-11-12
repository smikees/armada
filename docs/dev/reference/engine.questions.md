# `armada/engine/questions.py`

Bounded owner questions; only the supervising protocol thread writes answers.

### `normalize(rows, provider)`

—

### `validate_answers(questions, answers, cancelled=False)`

—

### class `QuestionControl`

—

- `QuestionControl.__init__(self, emit)` — —
- `QuestionControl.snapshot(self)` — —
- `QuestionControl.waiting(self)` — —
- `QuestionControl.add(self, native_id, provider, questions, reply)` — —
- `QuestionControl.answer(self, identity, answers, cancelled=False, persist=None)` — —
- `QuestionControl.drain(self, send)` — —
- `QuestionControl.resolve(self, native_id)` — —
- `QuestionControl.close(self, success=False)` — —

### class `QuestionProcess`

—

- `QuestionProcess.__init__(self, process, questions)` — —
- `QuestionProcess.__getattr__(self, name)` — —
- `QuestionProcess.kill(self)` — —
