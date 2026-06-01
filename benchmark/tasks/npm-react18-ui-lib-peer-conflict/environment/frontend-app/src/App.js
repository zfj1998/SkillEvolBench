var ui = require('@acme/ui-components');
var forms = require('@acme/forms');
var ReactDOM = require('react-dom');
var props = require('./componentProps');

function renderButton() {
    return ui.Button(props.getPrimaryButtonProps());
}

function renderForm() {
    return forms.FormField(props.getEmailFieldProps());
}

function renderApp() {
    return renderButton() + ' | ' + renderForm();
}

function mountApp(container) {
    var content = renderApp();
    ReactDOM.render(content, container);
    return content;
}

module.exports = {
    renderButton: renderButton,
    renderForm: renderForm,
    renderApp: renderApp,
    mountApp: mountApp
};
