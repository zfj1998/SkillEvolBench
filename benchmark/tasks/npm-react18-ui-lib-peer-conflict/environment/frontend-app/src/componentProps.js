function getPrimaryButtonProps() {
    return { label: 'Submit' };
}

function getEmailFieldProps() {
    return { name: 'email' };
}

module.exports = {
    getPrimaryButtonProps: getPrimaryButtonProps,
    getEmailFieldProps: getEmailFieldProps
};
