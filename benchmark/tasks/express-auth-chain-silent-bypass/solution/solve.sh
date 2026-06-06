#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

node - <<'PATCH'
const fs = require('fs');

let tokenValidator = fs.readFileSync('middleware/tokenValidator.js', 'utf8');
const oldValidator = `    if (shouldDeferAuthError(req, err)) {
      req.authWarning = {
        code: err.code,
        message: err.message,
      };

      // Non-critical token issue — continue request processing.
      // Downstream middleware handles route-level access decisions.
      next();
      return;
    }

    res.statusCode = 401;
    return res.json({ error: 'Invalid token', detail: err.message });`;
const newValidator = `    // Token verification failed — reject with 401.
    console.warn("[WARN] Token rejected (" + (err.code || "UNKNOWN") + "): " + err.message);
    res.statusCode = 401;
    return res.json({ error: "Invalid token", code: err.code || "INVALID_TOKEN", detail: err.message });`;
tokenValidator = tokenValidator.replace(oldValidator, newValidator);
fs.writeFileSync('middleware/tokenValidator.js', tokenValidator);

let roleChecker = fs.readFileSync('middleware/roleChecker.js', 'utf8');
const oldRoleChecker = [
  '  // No authenticated user context on this request.',
  '  if (!req.user) {',
  '    return next();',
  '  }',
  '',
  '  const rule = _findRule(req.method, req.path);',
].join('\n');
const newRoleChecker = [
  '  // Check route protection before making access decision.',
  '  const rule = _findRule(req.method, req.path);',
  '',
  '  if (!req.user) {',
  '    if (rule) {',
  '      res.statusCode = 401;',
  '      return res.json({ error: "Authentication required", detail: "Valid token needed for this endpoint" });',
  '    }',
  '    return next();',
  '  }',
].join('\n');
roleChecker = roleChecker.replace(oldRoleChecker, newRoleChecker);
roleChecker = roleChecker.replace(
  `    return res.json({
      error: 'Forbidden',
      detail: "Role '" + req.user.role + "' does not have access to this resource",
      required: rule.minRole,
    });`,
  `    return res.json({
      error: 'Forbidden',
      code: 'FORBIDDEN',
      detail: "Role '" + req.user.role + "' does not have access to this resource",
      required: rule.minRole,
    });`
);
fs.writeFileSync('middleware/roleChecker.js', roleChecker);
PATCH
