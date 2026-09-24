// Exercises navkeys.js in node against a minimal DOM stub. The guards are the whole feature —
// grepping the source wouldn't tell us whether they actually fire.
const fs = require('fs');
const path = require('path');

let handler = null;
let backCalls = 0;
let selectionCollapsed = true;
let openModal = null;

function el(props) {
  return Object.assign({
    nodeType: 1,
    tagName: 'DIV',
    isContentEditable: false,
    getAttribute() { return null; },
    closest() { return null; },
    style: {},
  }, props);
}

const body = el({ tagName: 'BODY' });

global.document = {
  addEventListener(type, fn) { if (type === 'keydown') handler = fn; },
  querySelector(sel) {
    if (openModal === 'overlay' && sel === '.mc-confirm-ov') return el({});
    if (openModal === 'dialog' && sel === 'dialog[open]') return el({});
    return null;
  },
  getElementById(id) {
    return (openModal === id) ? el({ style: { display: 'flex' } }) : null;
  },
  activeElement: body,
};
global.window = { getSelection: () => ({ isCollapsed: selectionCollapsed }) };
global.history = { get length() { return 5; }, back() { backCalls++; } };

require(path.resolve(__dirname, '..', 'armada', 'webui', 'static', 'js', 'navkeys.js'));

function press(opts) {
  backCalls = 0;
  let prevented = false;
  const ev = Object.assign({
    key: 'Backspace', ctrlKey: false, altKey: false, metaKey: false, shiftKey: false,
    defaultPrevented: false, target: body,
    preventDefault() { prevented = true; },
  }, opts);
  handler(ev);
  return { navigated: backCalls > 0, prevented };
}

const failures = [];
function check(name, cond) { if (!cond) failures.push(name); }

// --- it works in the ordinary case -----------------------------------------------------------
document.activeElement = body;
check('plain backspace navigates', press({}).navigated);
check('plain backspace prevents default', press({}).prevented);

// --- never while typing ------------------------------------------------------------------------
for (const tag of ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']) {
  check('ignores ' + tag, !press({ target: el({ tagName: tag }) }).navigated);
}
check('ignores contenteditable (the chat composer)',
  !press({ target: el({ isContentEditable: true }) }).navigated);
check('ignores role=textbox',
  !press({ target: el({ getAttribute: (a) => (a === 'role' ? 'textbox' : null) }) }).navigated);
check('ignores a field nested inside the event target',
  !press({ target: el({ closest: (s) => (s.includes('input') ? el({}) : null) }) }).navigated);

// focus elsewhere than the event target — the caret is what matters
document.activeElement = el({ tagName: 'TEXTAREA' });
check('ignores when focus is in a field even if the event target is not', !press({}).navigated);
document.activeElement = body;

// --- never when it would mean something else ---------------------------------------------------
for (const mod of ['ctrlKey', 'altKey', 'metaKey', 'shiftKey']) {
  const o = {}; o[mod] = true;
  check('ignores ' + mod, !press(o).navigated);
}
check('ignores other keys', !press({ key: 'a' }).navigated);
check('ignores an already-handled event', !press({ defaultPrevented: true }).navigated);

selectionCollapsed = false;
check('ignores while text is selected', !press({}).navigated);
selectionCollapsed = true;

// --- never behind a dialog ---------------------------------------------------------------------
openModal = 'overlay';
check('ignores while the shared confirm dialog is open', !press({}).navigated);
openModal = 'dialog';
check('ignores while a native dialog is open', !press({}).navigated);
openModal = 'mc-caphelp';
check('ignores while a page modal is open', !press({}).navigated);
openModal = null;
check('works again once the dialog closes', press({}).navigated);

if (failures.length) {
  console.error('FAILED:\n  ' + failures.join('\n  '));
  process.exit(1);
}
console.log('navkeys: all guards ok');
