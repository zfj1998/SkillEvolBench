var ReactDOM = require('react-dom');

function mountWithReact18(container, content) {
    var root = ReactDOM.createRoot(container);
    root.render(content);
    return content;
}

module.exports = {
    mountWithReact18: mountWithReact18
};
