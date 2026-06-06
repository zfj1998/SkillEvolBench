var App = require('../src/App');
var React = require('react');
var ReactDOM = require('react-dom');

var failures = 0;
function assert(cond, msg) {
    if (!cond) { console.error('FAIL: ' + msg); failures++; }
    else { console.log('PASS: ' + msg); }
}

assert(App.renderButton() === 'Button:Submit', 'Button renders with correct text');
assert(App.renderForm() === 'FormField:email:valid', 'FormField renders with name');
assert(App.renderApp() === 'Button:Submit | FormField:email:valid', 'App renders both');
assert(React.version === '18.2.0', 'React version is 18.2.0');
assert(typeof ReactDOM.createRoot === 'function', 'createRoot API exists');
assert(typeof ReactDOM.render === 'undefined', 'legacy render API removed');

// Test mountApp — must use createRoot path
try {
    var result = App.mountApp({ id: 'root' });
    assert(result === 'Button:Submit | FormField:email:valid', 'mountApp returns correct content');
} catch (e) {
    assert(false, 'mountApp threw: ' + e.message);
}

if (failures > 0) { console.error('\n' + failures + ' test(s) failed'); process.exit(1); }
else { console.log('\nAll tests passed.'); }
