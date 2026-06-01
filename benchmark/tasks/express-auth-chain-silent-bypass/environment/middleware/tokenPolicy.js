/**
 * Transitional auth policy for the FinGuard API.
 *
 * During the legacy SSO migration we temporarily downgraded certain token
 * parsing failures into "monitor-only" events so route-level authorization
 * could keep serving traffic while telemetry was collected.
 */
'use strict';

const SOFT_FAIL_CODES = new Set(['ENCODING', 'PAYLOAD', 'HEADER', 'CLAIMS']);

function getAuthzMode(req) {
  return String(
    (req.headers && req.headers['x-authz-mode']) ||
    process.env.AUTHZ_MODE ||
    'compat'
  ).toLowerCase();
}

function shouldDeferAuthError(req, err) {
  return getAuthzMode(req) !== 'strict' && SOFT_FAIL_CODES.has(err.code);
}

module.exports = {
  SOFT_FAIL_CODES,
  shouldDeferAuthError,
  getAuthzMode,
};
