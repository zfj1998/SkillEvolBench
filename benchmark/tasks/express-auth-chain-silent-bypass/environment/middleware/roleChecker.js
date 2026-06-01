/**
 * Role-based access control middleware.
 *
 * Enforces endpoint-level permissions after the token validator has
 * had a chance to populate req.user.  The permission matrix is defined
 * inline — in production this would come from a policy engine.
 */
'use strict';

const ROLE_HIERARCHY = { viewer: 1, analyst: 2, admin: 3 };

const PROTECTED_ROUTES = [
  { method: 'GET',    path: '/api/users',           minRole: 'viewer'  },
  { method: 'GET',    pattern: '/api/users/:id',    minRole: 'viewer'  },
  { method: 'GET',    path: '/api/admin/users',     minRole: 'admin'   },
  { method: 'GET',    path: '/api/admin/audit-log', minRole: 'admin'   },
  { method: 'DELETE', pattern: '/api/admin/users/:id', minRole: 'admin' },
];

/**
 * Check whether a concrete request path matches a route pattern.
 * Supports :param wildcard segments.
 */
function _pathMatches(pattern, pathname) {
  const pp = pattern.split('/');
  const rp = pathname.split('/');
  if (pp.length !== rp.length) return false;
  for (let i = 0; i < pp.length; i++) {
    if (pp[i].startsWith(':')) continue;
    if (pp[i] !== rp[i]) return false;
  }
  return true;
}

/**
 * Find the permission rule that applies to the given request.
 * Returns null if the endpoint is not protected.
 */
function _findRule(method, pathname) {
  for (const rule of PROTECTED_ROUTES) {
    if (rule.method !== method) continue;
    const target = rule.path || rule.pattern;
    if (_pathMatches(target, pathname)) return rule;
  }
  return null;
}

// ─── Middleware ────────────────────────────────────────────────────────

function roleChecker(req, res, next) {
  // No authenticated user context on this request.
  if (!req.user) {
    return next();
  }

  const rule = _findRule(req.method, req.path);

  // No explicit rule → endpoint is considered public
  if (!rule) {
    return next();
  }

  // Compare caller's role level against the minimum required
  const userLevel     = ROLE_HIERARCHY[req.user.role] || 0;
  const requiredLevel = ROLE_HIERARCHY[rule.minRole]  || 0;

  if (userLevel < requiredLevel) {
    res.statusCode = 403;
    return res.json({
      error: 'Forbidden',
      detail: "Role '" + req.user.role + "' does not have access to this resource",
      required: rule.minRole,
    });
  }

  next();
}

module.exports = { roleChecker, PROTECTED_ROUTES, ROLE_HIERARCHY };
