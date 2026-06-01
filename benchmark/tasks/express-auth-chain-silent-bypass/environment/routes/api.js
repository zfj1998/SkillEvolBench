/**
 * API route handlers for the FinGuard platform.
 *
 * Authentication and authorization are enforced by the middleware chain
 * (tokenValidator → roleChecker) before requests reach these handlers.
 * By the time a handler executes, req.user is set and the caller's
 * role has been verified against the endpoint's requirements.
 */
'use strict';

const User = require('../models/user');

function registerRoutes(app) {

  // ── Public endpoints ──────────────────────────────────────────────

  app.get('/api/health', function (_req, res) {
    res.json({ status: 'ok', service: 'finguard-api', timestamp: new Date().toISOString() });
  });

  app.get('/api/version', function (_req, res) {
    res.json({ version: '2.7.1', build: 'a4f8c2e', environment: process.env.NODE_ENV || 'development' });
  });

  // ── User endpoints (viewer+) ──────────────────────────────────────

  app.get('/api/users', function (req, res) {
    var callerRole = req.user ? req.user.role : 'viewer';
    var users = User.findAll().map(function (u) { return User.sanitise(u, callerRole); });
    User.logAccess('/api/users', req.user && req.user.id, callerRole);
    res.json({ users: users, count: users.length, filtered: callerRole !== 'admin' });
  });

  app.get('/api/users/:id', function (req, res) {
    var user = User.findById(req.params.id);
    if (!user) {
      res.statusCode = 404;
      return res.json({ error: 'User not found', id: req.params.id });
    }
    var callerRole = req.user ? req.user.role : 'viewer';
    User.logAccess('/api/users/' + req.params.id, req.user && req.user.id, callerRole);
    res.json({ user: User.sanitise(user, callerRole) });
  });

  // ── Admin endpoints (admin only) ──────────────────────────────────

  /**
   * GET /api/admin/users
   *
   * Full user dump with ALL fields including PII.  This endpoint is
   * restricted to admin role by the roleChecker middleware — by the
   * time we reach this handler, the caller is verified as an admin,
   * so we return the complete dataset without additional checks.
   */
  app.get('/api/admin/users', function (req, res) {
    var users = User.findAll();
    User.logAccess('/api/admin/users', req.user && req.user.id, req.user && req.user.role);
    res.json({
      users: users,
      count: users.length,
      includes_sensitive: true,
      warning: 'This response contains PII — handle according to data policy.',
    });
  });

  app.get('/api/admin/audit-log', function (req, res) {
    var limit = parseInt(req.query.limit || '50', 10);
    res.json({ entries: User.getAccessLog(limit), count: User.getAccessLog(limit).length });
  });

  app.delete('/api/admin/users/:id', function (req, res) {
    var user = User.findById(req.params.id);
    if (!user) {
      res.statusCode = 404;
      return res.json({ error: 'User not found', id: req.params.id });
    }
    User.logAccess('DELETE /api/admin/users/' + req.params.id, req.user && req.user.id, req.user && req.user.role);
    res.json({ deleted: true, id: user.id, username: user.username });
  });
}

module.exports = { registerRoutes };
