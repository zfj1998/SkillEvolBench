/**
 * FinGuard API Gateway
 *
 * Internal API serving user account data and admin endpoints.
 *
 * Built on a lightweight request router (no Express dependency) so
 * the Docker image stays small for CI.
 *
 * Environment:
 *   TOKEN_SECRET – HMAC-SHA256 signing key (default: dev key)
 *   PORT         – listen port (default: 3000)
 *   RATE_LIMIT   – max requests per IP per window (default: 100)
 */
'use strict';

const http = require('http');
const { URL } = require('url');

const { registerRoutes } = require('./routes/api');

// ─── Micro-framework ────────────────────────────────────────────────

function createApp() {
  var middlewares = [];
  var routes = [];

  function app(req, res) {
    var parsed = new URL(req.url, 'http://' + (req.headers.host || 'localhost'));
    req.path   = parsed.pathname;
    req.query  = Object.fromEntries(parsed.searchParams.entries());
    req.params = {};

    var chunks = [];
    req.on('data', function (c) { chunks.push(c); });
    req.on('end', function () {
      var raw = Buffer.concat(chunks).toString();
      req.body = {};
      if (raw && (req.headers['content-type'] || '').indexOf('application/json') !== -1) {
        try { req.body = JSON.parse(raw); } catch (_) { /* skip */ }
      }

      var matched = _matchRoute(req.method, req.path);
      var chain = middlewares.slice();
      if (matched) {
        req.params = matched.params;
        chain = chain.concat(matched.handlers);
      } else {
        chain.push(function (_r, _s) {
          _s.statusCode = 404;
          _sendJson(_s, { error: 'Not found', path: req.path });
        });
      }

      var idx = 0;
      function next(err) {
        if (err) return _handleError(err, req, res);
        var fn = chain[idx++];
        if (!fn) return;
        try { fn(req, res, next); } catch (e) { _handleError(e, req, res); }
      }
      next();
    });
  }

  app.use = function (fn) { middlewares.push(fn); };

  ['get', 'post', 'put', 'delete', 'patch'].forEach(function (m) {
    app[m] = function (path) {
      var handlers = Array.prototype.slice.call(arguments, 1);
      routes.push({ method: m.toUpperCase(), path: path, handlers: handlers });
    };
  });

  function _matchRoute(method, pathname) {
    for (var i = 0; i < routes.length; i++) {
      var r = routes[i];
      if (r.method !== method) continue;
      var p = _extractParams(r.path, pathname);
      if (p !== null) return { handlers: r.handlers, params: p };
    }
    return null;
  }

  function _extractParams(pattern, pathname) {
    var pp = pattern.split('/'), rp = pathname.split('/');
    if (pp.length !== rp.length) return null;
    var params = {};
    for (var i = 0; i < pp.length; i++) {
      if (pp[i].charAt(0) === ':') params[pp[i].slice(1)] = decodeURIComponent(rp[i]);
      else if (pp[i] !== rp[i]) return null;
    }
    return params;
  }

  function _handleError(err, req, res) {
    var status = err.statusCode || 500;
    console.error('[ERROR] ' + req.method + ' ' + req.path + ': ' + err.message);
    res.statusCode = status;
    _sendJson(res, { error: err.message || 'Internal server error' });
  }

  app.listen = function (port, cb) {
    var srv = http.createServer(function (req, res) {
      res.status = function (code) { res.statusCode = code; return res; };
      res.json   = function (data) { _sendJson(res, data); };
      app(req, res);
    });
    srv.listen(port, cb);
    return srv;
  };

  return app;
}

function _sendJson(res, data) {
  if (res.writableEnded) return;
  var body = JSON.stringify(data);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(body);
}

// ─── Boot ─────────────────────────────────────────────────────────────

function _initMiddleware(app) {
  var mw = [
    require('./middleware/rateLimiter').rateLimiter,
    require('./middleware/tokenValidator').tokenValidator,
    require('./middleware/roleChecker').roleChecker,
  ];
  for (var i = 0; i < mw.length; i++) app.use(mw[i]);
}

var app = createApp();
_initMiddleware(app);
registerRoutes(app);

var PORT = parseInt(process.env.PORT || '3000', 10);

if (require.main === module) {
  app.listen(PORT, function () {
    console.log('[INFO] FinGuard API listening on port ' + PORT);
  });
}

module.exports = { app: app, startServer: function (port) { return app.listen(port || PORT); } };
