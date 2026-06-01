/**
 * User data model for the FinGuard platform.
 *
 * In production this queries PostgreSQL via pg-pool.  For the internal
 * staging environment we use an in-memory dataset seeded from the
 * anonymised QA dump.
 */
'use strict';

const USERS = [
  { id: 1, username: 'alice.chen',   email: 'alice.chen@finguard.io',   phone: '+1-555-0101', role: 'admin',   department: 'Engineering', ssn_last4: '4821', account_balance: 284750.43, created_at: '2023-01-15T08:00:00Z' },
  { id: 2, username: 'bob.martinez', email: 'bob.martinez@finguard.io', phone: '+1-555-0102', role: 'analyst', department: 'Finance',     ssn_last4: '9173', account_balance: 12430.00,  created_at: '2023-03-22T14:30:00Z' },
  { id: 3, username: 'carol.nguyen', email: 'carol.nguyen@finguard.io', phone: '+1-555-0103', role: 'viewer',  department: 'Marketing',   ssn_last4: '6502', account_balance: 8915.75,   created_at: '2023-06-10T09:15:00Z' },
  { id: 4, username: 'dave.wilson',  email: 'dave.wilson@finguard.io',  phone: '+1-555-0104', role: 'analyst', department: 'Compliance',  ssn_last4: '3347', account_balance: 53200.10,  created_at: '2023-08-01T11:45:00Z' },
  { id: 5, username: 'eve.jackson',  email: 'eve.jackson@finguard.io',  phone: '+1-555-0105', role: 'viewer',  department: 'Support',     ssn_last4: '7789', account_balance: 3100.50,   created_at: '2024-01-20T16:00:00Z' },
];

const SENSITIVE_FIELDS = ['email', 'phone', 'ssn_last4', 'account_balance'];
const PUBLIC_FIELDS    = ['id', 'username', 'role', 'department', 'created_at'];

function findById(id)        { return USERS.find(u => u.id === parseInt(id, 10)) || null; }
function findByUsername(name) { return USERS.find(u => u.username === name) || null; }
function findAll()           { return USERS.map(u => ({ ...u })); }

/**
 * Return a copy of the record filtered by the caller's role:
 *   admin   → all fields including PII
 *   analyst → public + email
 *   viewer  → public fields only
 */
function sanitise(user, role) {
  if (!user) return null;
  const copy = {};
  for (const k of PUBLIC_FIELDS) copy[k] = user[k];
  if (role === 'admin') {
    for (const k of SENSITIVE_FIELDS) copy[k] = user[k];
  } else if (role === 'analyst') {
    copy.email = user.email;
  }
  return copy;
}

// ── Compliance access log ─────────────────────────────────────────────

const _accessLog = [];

function logAccess(endpoint, accessorId, accessorRole) {
  _accessLog.push({
    timestamp: new Date().toISOString(),
    endpoint,
    accessorId: accessorId || 'anonymous',
    accessorRole: accessorRole || 'none',
  });
  if (_accessLog.length > 500) _accessLog.splice(0, _accessLog.length - 500);
}

function getAccessLog(limit) {
  return _accessLog.slice(-(limit || 50));
}

module.exports = {
  findById, findByUsername, findAll, sanitise,
  logAccess, getAccessLog,
  SENSITIVE_FIELDS, PUBLIC_FIELDS,
};
