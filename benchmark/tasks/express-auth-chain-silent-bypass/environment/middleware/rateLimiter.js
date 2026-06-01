/**
 * IP-based sliding-window rate limiter.
 *
 * Limits each IP to RATE_LIMIT requests per WINDOW_MS window.
 * Uses an in-memory store — adequate for single-process deployments.
 *
 * Response headers (always set):
 *   X-RateLimit-Limit     – max requests per window
 *   X-RateLimit-Remaining – requests left in current window
 *   X-RateLimit-Reset     – epoch seconds when window resets
 */
'use strict';

const WINDOW_MS  = parseInt(process.env.RATE_WINDOW_MS || '60000', 10);
const RATE_LIMIT = parseInt(process.env.RATE_LIMIT || '100', 10);

const _buckets = new Map();

// Periodic cleanup to prevent memory leak from stale IPs
const _cleanup = setInterval(() => {
  const now = Date.now();
  for (const [ip, b] of _buckets) {
    if (now - b.windowStart > WINDOW_MS * 2) _buckets.delete(ip);
  }
}, 5 * 60 * 1000);
if (_cleanup.unref) _cleanup.unref();

function _getClientIp(req) {
  const fwd = req.headers['x-forwarded-for'];
  if (fwd) return fwd.split(',')[0].trim();
  return req.socket ? req.socket.remoteAddress || '127.0.0.1' : '127.0.0.1';
}

function rateLimiter(req, res, next) {
  const ip  = _getClientIp(req);
  const now = Date.now();

  let bucket = _buckets.get(ip);
  if (!bucket || (now - bucket.windowStart) >= WINDOW_MS) {
    bucket = { count: 0, windowStart: now };
    _buckets.set(ip, bucket);
  }
  bucket.count += 1;

  const remaining  = Math.max(0, RATE_LIMIT - bucket.count);
  const resetEpoch = Math.ceil((bucket.windowStart + WINDOW_MS) / 1000);

  res.setHeader('X-RateLimit-Limit', String(RATE_LIMIT));
  res.setHeader('X-RateLimit-Remaining', String(remaining));
  res.setHeader('X-RateLimit-Reset', String(resetEpoch));

  if (bucket.count > RATE_LIMIT) {
    res.statusCode = 429;
    res.setHeader('Retry-After', String(Math.ceil(WINDOW_MS / 1000)));
    return res.json({ error: 'Too many requests', retryAfter: Math.ceil(WINDOW_MS / 1000) });
  }

  next();
}

function resetRateLimiter() { _buckets.clear(); }

module.exports = { rateLimiter, resetRateLimiter };
