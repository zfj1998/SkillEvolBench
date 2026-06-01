/**
 * JWT-style token validation middleware.
 *
 * Token format (compatible with our auth-service):
 *   base64url(header) . base64url(payload) . base64url(hmac-sha256)
 *
 * On success: sets req.user with decoded claims, calls next().
 */
'use strict';

const crypto = require('crypto');
const { shouldDeferAuthError } = require('./tokenPolicy');

const TOKEN_SECRET = process.env.TOKEN_SECRET || 'finguard-dev-secret-do-not-use-in-prod';

// Endpoints that never require authentication
const PUBLIC_PATHS = ['/api/health', '/api/version'];

// ─── Custom error for token issues ────────────────────────────────────

class TokenValidationError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'TokenValidationError';
    this.code = code || 'INVALID_TOKEN';
  }
}

// ─── Token verification ───────────────────────────────────────────────

/**
 * Verify and decode a signed token.
 *
 * @param {string} token – raw token string from the Authorization header
 * @returns {object} decoded payload claims
 * @throws {TokenValidationError}
 */
function _verifyToken(token) {
  if (typeof token !== 'string' || token.length === 0) {
    throw new TokenValidationError('Empty token', 'EMPTY');
  }

  const segments = token.split('.');
  if (segments.length !== 3) {
    throw new TokenValidationError('Token must have 3 dot-separated segments', 'MALFORMED');
  }

  const [headerB64, payloadB64, signatureB64] = segments;

  // Validate that each segment uses the base64url alphabet (RFC 4648 §5).
  // Standard base64 characters (+, /, =) are NOT permitted — tokens from
  // external systems that use standard encoding must be re-encoded first.
  const b64urlPattern = /^[A-Za-z0-9_-]+$/;
  for (const seg of [headerB64, payloadB64, signatureB64]) {
    if (!b64urlPattern.test(seg)) {
      throw new TokenValidationError(
        'Token segment contains invalid base64url characters',
        'ENCODING',
      );
    }
  }

  // Verify HMAC-SHA256 signature
  const signedContent = headerB64 + '.' + payloadB64;
  const expectedSig = crypto
    .createHmac('sha256', TOKEN_SECRET)
    .update(signedContent)
    .digest('base64url');

  const sigBuf = Buffer.from(signatureB64, 'utf8');
  const expBuf = Buffer.from(expectedSig, 'utf8');
  if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
    throw new TokenValidationError('Signature verification failed', 'SIGNATURE');
  }

  // Decode header
  let header;
  try {
    header = JSON.parse(Buffer.from(headerB64, 'base64url').toString('utf8'));
  } catch (_) {
    throw new TokenValidationError('Invalid header JSON', 'HEADER');
  }
  if (header.alg !== 'HS256') {
    throw new TokenValidationError('Unsupported algorithm: ' + header.alg, 'ALGORITHM');
  }

  // Decode payload
  let payload;
  try {
    payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
  } catch (_) {
    throw new TokenValidationError('Invalid payload JSON', 'PAYLOAD');
  }

  if (!payload.sub) throw new TokenValidationError('Missing "sub" claim', 'CLAIMS');
  if (!payload.role) throw new TokenValidationError('Missing "role" claim', 'CLAIMS');

  // Check expiration
  if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
    throw new TokenValidationError('Token has expired', 'EXPIRED');
  }

  return payload;
}

// ─── Middleware ────────────────────────────────────────────────────────

function tokenValidator(req, res, next) {
  // Public endpoints — skip authentication entirely
  if (PUBLIC_PATHS.includes(req.path)) {
    return next();
  }

  const authHeader = req.headers['authorization'] || '';

  // No Authorization header → clear rejection
  if (!authHeader) {
    res.statusCode = 401;
    return res.json({
      error: 'Authentication required',
      detail: 'Provide a Bearer token in the Authorization header',
    });
  }

  // Wrong scheme
  if (!authHeader.startsWith('Bearer ')) {
    res.statusCode = 401;
    return res.json({
      error: 'Invalid authentication scheme',
      detail: 'Authorization header must use Bearer scheme',
    });
  }

  const token = authHeader.slice(7).trim();

  try {
    const claims = _verifyToken(token);

    // Attach decoded identity to the request
    req.user = {
      id:       claims.sub,
      role:     claims.role,
      username: claims.username || null,
    };

    next();
  } catch (err) {
    // Handle well-known token rejection reasons explicitly
    if (err.code === 'EXPIRED') {
      res.statusCode = 401;
      return res.json({ error: 'Token expired', detail: err.message });
    }
    if (err.code === 'SIGNATURE') {
      res.statusCode = 401;
      return res.json({ error: 'Invalid token', detail: 'Signature verification failed' });
    }
    if (err.code === 'EMPTY') {
      res.statusCode = 401;
      return res.json({ error: 'Invalid token', detail: 'Token is empty' });
    }

    if (shouldDeferAuthError(req, err)) {
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
    return res.json({ error: 'Invalid token', detail: err.message });
  }
}

// ─── Token generation (used by auth-service & test harness) ───────────

function signToken(payload, opts) {
  opts = opts || {};
  const header = { alg: 'HS256', typ: 'JWT' };
  const now = Math.floor(Date.now() / 1000);
  const claims = Object.assign({}, payload, {
    iat: now,
    exp: payload.exp || (now + (opts.expiresIn || 3600)),
  });

  const headerB64  = Buffer.from(JSON.stringify(header)).toString('base64url');
  const payloadB64 = Buffer.from(JSON.stringify(claims)).toString('base64url');
  const signature  = crypto
    .createHmac('sha256', TOKEN_SECRET)
    .update(headerB64 + '.' + payloadB64)
    .digest('base64url');

  return headerB64 + '.' + payloadB64 + '.' + signature;
}

module.exports = { tokenValidator, signToken, _verifyToken, TOKEN_SECRET };
