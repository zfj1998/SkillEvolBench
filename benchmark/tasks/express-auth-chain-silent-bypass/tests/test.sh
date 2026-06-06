#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"

mkdir -p "$LOG_DIR"
export SCRIPT_DIR PROJECT_ROOT LOG_DIR

node <<'NODE'
'use strict';

const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');

const PROJECT_ROOT = process.env.PROJECT_ROOT || '/root/task';
const LOG_DIR = process.env.LOG_DIR || '/logs/verifier';
const PORT = 3399;

const CRAFTED_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjEsInJvbGUiOiJhZG1pbiJ9.invalid+signature/with=padding';
const MALFORMED_TOKEN = 'not-a-jwt-at-all';
const EMPTY_PAYLOAD_TOKEN = 'eyJhbGciOiJIUzI1NiJ9..fakesig';

fs.mkdirSync(LOG_DIR, { recursive: true });

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function signToken(payloadSource) {
  const tokenModule = require(path.join(PROJECT_ROOT, 'middleware', 'tokenValidator'));
  return tokenModule.signToken(payloadSource);
}

function request(method, route, token) {
  return new Promise((resolve, reject) => {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port: PORT,
        path: route,
        method,
        headers,
        timeout: 5000,
      },
      (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          let parsed = {};
          try { parsed = body ? JSON.parse(body) : {}; } catch (_) { parsed = {}; }
          resolve({ status: res.statusCode, body: parsed });
        });
      },
    );
    req.on('timeout', () => req.destroy(new Error('request timeout')));
    req.on('error', reject);
    req.end();
  });
}

async function waitForServer(proc) {
  for (let i = 0; i < 30; i++) {
    if (proc.exitCode !== null) break;
    try {
      await request('GET', '/api/health');
      return;
    } catch (_) {
      await sleep(200);
    }
  }
  throw new Error('Server failed to start');
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'assertion failed');
}

async function runTest(results, nodeid, fn) {
  try {
    await fn();
    results[nodeid] = { nodeid, outcome: 'passed' };
  } catch (err) {
    results[nodeid] = {
      nodeid,
      outcome: 'failed',
      call: { longrepr: err && err.stack ? err.stack : String(err) },
    };
  }
}

function readSource(relpath) {
  const target = path.join(PROJECT_ROOT, relpath);
  return fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : '';
}

function testReport(results) {
  // Output schema mirrors the Python `_pytest_to_script_report` helper used
  // by Type-C tasks: {public: {total, passed, results}, hidden: {...}}.
  // Hidden iff nodeid contains 'hidden' (case-insensitive) or the leaf
  // function name matches 'test_h<digit>...'; everything else is public.
  // VerifierAdapter._failed_from_script_report / _all_groups_pass read
  // exactly this shape -- without it, outcome_passed/process_passed stay
  // None on this JS task.
  const publicResults = [];
  const hiddenResults = [];
  for (const item of Object.values(results)) {
    const nodeid = String(item.nodeid || '');
    const leaf = nodeid.includes('::') ? nodeid.split('::').pop() : nodeid;
    const lowerNode = nodeid.toLowerCase();
    const lowerLeaf = leaf.toLowerCase();
    const isHidden = (
      lowerNode.includes('hidden')
      || (lowerLeaf.startsWith('test_h')
        && lowerLeaf.length > 6
        && lowerLeaf[6] >= '0' && lowerLeaf[6] <= '9')
    );
    const passed = item.outcome === 'passed';
    const longrepr = (item.call && item.call.longrepr) || '';
    const entry = {
      name: leaf,
      passed,
      error: passed ? '' : String(longrepr).slice(0, 500),
    };
    (isHidden ? hiddenResults : publicResults).push(entry);
  }
  const out = {};
  if (publicResults.length > 0) {
    out.public = {
      total: publicResults.length,
      passed: publicResults.filter((x) => x.passed).length,
      results: publicResults,
    };
  }
  if (hiddenResults.length > 0) {
    out.hidden = {
      total: hiddenResults.length,
      passed: hiddenResults.filter((x) => x.passed).length,
      results: hiddenResults,
    };
  }
  return out;
}

function match(results, patterns) {
  const found = {};
  for (const [nodeid, item] of Object.entries(results)) {
    for (const pattern of patterns) {
      if (nodeid.toLowerCase().includes(pattern.toLowerCase())) {
        found[nodeid] = item.outcome === 'passed';
        break;
      }
    }
  }
  return found;
}

function computeScore(allResults) {
  const rubric = [
    ['Public tests (P1-P4)', 15.0, ['TestPublic::test_p1_', 'TestPublic::test_p2_', 'TestPublic::test_p3_', 'TestPublic::test_p4_'], 'proportional'],
    ['H1: core bypass', 20.0, ['test_h1_crafted'], 'all_or_nothing'],
    ['H2-H6: security tests', 25.0, ['test_h2_', 'test_h3_', 'test_h4_', 'test_h5_', 'test_h6_'], 'proportional'],
    ['H7-H8: auxiliary', 10.0, ['test_h7_', 'test_h8_'], 'proportional'],
    ['P1+P2: tokenValidator fix', 15.0, ['TestProcessP1P2'], 'all_or_nothing'],
    ['P3: roleChecker defense', 10.0, ['TestProcessP3'], 'all_or_nothing'],
    ['P5: no 200 on rejection', 5.0, ['TestProcessP5'], 'all_or_nothing'],
  ];

  let totalScore = 0;
  const dimensions = [];
  for (const [name, weight, patterns, scoring] of rubric) {
    const matched = match(allResults, patterns);
    const count = Object.keys(matched).length;
    const passed = Object.values(matched).filter(Boolean).length;
    let ratio = 0;
    if (count > 0) {
      ratio = scoring === 'all_or_nothing' ? (passed === count ? 1 : 0) : passed / count;
    }
    const score = weight * ratio;
    totalScore += score;
    dimensions.push({
      name,
      weight,
      matched: count,
      passed,
      scoring,
      ratio: Math.round(ratio * 1000) / 1000,
      score: Math.round(score * 100) / 100,
    });
  }
  return {
    total_score: Math.round(totalScore * 100) / 100,
    max_score: 100.0,
    dimensions,
  };
}

function writeOutputs(outcomeResults, processResults) {
  const outcomePath = path.join(LOG_DIR, 'outcome_report.json');
  const processPath = path.join(LOG_DIR, 'process_report.json');
  fs.writeFileSync(outcomePath, JSON.stringify(testReport(outcomeResults), null, 2) + '\n');
  fs.writeFileSync(processPath, JSON.stringify(testReport(processResults), null, 2) + '\n');

  const combined = Object.assign({}, outcomeResults, processResults);
  const scoreReport = computeScore(combined);
  const normalized = scoreReport.total_score / scoreReport.max_score;
  fs.writeFileSync(path.join(LOG_DIR, 'score_report.json'), JSON.stringify(scoreReport, null, 2) + '\n');
  fs.writeFileSync(path.join(LOG_DIR, 'reward.txt'), `${normalized.toFixed(6)}\n`);
  fs.writeFileSync(
    path.join(LOG_DIR, 'reward.json'),
    JSON.stringify({
      total_score: scoreReport.total_score,
      max_score: scoreReport.max_score,
      normalized_score: normalized,
      outcome_passed: Object.values(outcomeResults).every((item) => item.outcome === 'passed') ? 1.0 : 0.0,
      process_passed: Object.values(processResults).every((item) => item.outcome === 'passed') ? 1.0 : 0.0,
    }, null, 2) + '\n',
  );
  return normalized;
}

async function main() {
  const env = Object.assign({}, process.env, { PORT: String(PORT) });
  const proc = spawn('node', ['app.js'], { cwd: PROJECT_ROOT, env });
  let stderrText = '';
  proc.stderr.on('data', (chunk) => { stderrText += chunk.toString('utf8'); });
  proc.stdout.on('data', () => {});

  const outcomeResults = {};
  const processResults = {};
  let serverStarted = false;

  try {
    await waitForServer(proc);
    serverStarted = true;

    const adminToken = signToken({ sub: 1, role: 'admin', username: 'alice.chen' });
    const viewerToken = signToken({ sub: 3, role: 'viewer', username: 'carol' });
    const analystToken = signToken({ sub: 2, role: 'analyst', username: 'bob' });
    const expiredToken = signToken({ sub: 1, role: 'admin', exp: 1000000 });

    await runTest(outcomeResults, 'test_outcome.py::TestPublic::test_p1_valid_admin_token_returns_200', async () => {
      const { status, body } = await request('GET', '/api/admin/users', adminToken);
      assert(status === 200, `expected 200, got ${status}`);
      assert(body.count === 5, `expected count 5, got ${body.count}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestPublic::test_p2_no_token_returns_401', async () => {
      const { status, body } = await request('GET', '/api/admin/users');
      assert(status === 401, `expected 401, got ${status}`);
      assert(Object.prototype.hasOwnProperty.call(body, 'error'), 'missing error body');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestPublic::test_p3_expired_token_returns_401', async () => {
      const { status } = await request('GET', '/api/admin/users', expiredToken);
      assert(status === 401, `expected 401, got ${status}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestPublic::test_p4_wrong_signature_returns_401', async () => {
      let badSig = signToken({ sub: 1, role: 'admin' });
      badSig = badSig.slice(0, -4) + 'XXXX';
      const { status } = await request('GET', '/api/admin/users', badSig);
      assert(status === 401, `expected 401, got ${status}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenBypass::test_h1_crafted_padding_token_rejected', async () => {
      const { status, body } = await request('GET', '/api/admin/users', CRAFTED_TOKEN);
      assert(status !== 200, `crafted token returned ${status} with ${body.count || '?'} records`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenBypass::test_h2_malformed_token_rejected', async () => {
      const { status } = await request('GET', '/api/admin/users', MALFORMED_TOKEN);
      assert(status !== 200, `malformed token returned ${status}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenBypass::test_h3_empty_payload_token_rejected', async () => {
      const { status } = await request('GET', '/api/admin/users', EMPTY_PAYLOAD_TOKEN);
      assert(status !== 200, `empty payload token returned ${status}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenRoleEnforcement::test_h4_viewer_cannot_access_admin', async () => {
      const { status, body } = await request('GET', '/api/admin/users', viewerToken);
      assert(status === 403, `expected 403, got ${status}`);
      assert('error' in body && 'code' in body, 'missing error/code');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenRoleEnforcement::test_h5_viewer_response_has_no_pii', async () => {
      const { status, body } = await request('GET', '/api/users', viewerToken);
      assert(status === 200, `expected 200, got ${status}`);
      assert(body.filtered === true, 'viewer response should be filtered');
      const user = body.users[0];
      assert(!('ssn_last4' in user), 'viewer can see SSN');
      assert(!('phone' in user), 'viewer can see phone');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenRoleEnforcement::test_h6_rejected_request_returns_error_not_data', async () => {
      const { body } = await request('GET', '/api/admin/users', CRAFTED_TOKEN);
      assert(!('users' in body), 'rejected response contains user data');
      assert('error' in body && 'code' in body, 'missing error/code');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenRoleEnforcement::test_h6b_analyst_gets_email_but_not_admin', async () => {
      let response = await request('GET', '/api/users', analystToken);
      assert(response.status === 200, `expected 200, got ${response.status}`);
      assert(response.body.filtered === true, 'analyst response should be filtered');
      assert('email' in response.body.users[0], 'analyst should see email');
      assert(!('phone' in response.body.users[0]), 'analyst should not see phone');

      response = await request('GET', '/api/admin/users', analystToken);
      assert(response.status === 403, `expected 403, got ${response.status}`);
      assert('error' in response.body && 'code' in response.body, 'missing error/code');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenAuxiliary::test_h7_invalid_token_produces_warning_log', async () => {
      const start = stderrText.length;
      await request('GET', '/api/admin/users', CRAFTED_TOKEN);
      await sleep(300);
      const logText = stderrText.slice(start).toLowerCase();
      assert(
        logText.includes('warn') || logText.includes('rejected') || logText.includes('invalid token'),
        `expected warning log, got: ${logText.slice(0, 200)}`,
      );
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenAuxiliary::test_h8_rate_limiter_still_works', async () => {
      const response = await request('GET', '/api/admin/users', adminToken);
      assert(response.status === 200, `expected 200, got ${response.status}`);
      assert(response.body.includes_sensitive === true, 'admin response should include sensitive fields');
      const health = await request('GET', '/api/health');
      assert(health.status === 200, `health expected 200, got ${health.status}`);
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenAuxiliary::test_h9_version_endpoint_is_public_json', async () => {
      const { status, body } = await request('GET', '/api/version');
      assert(status === 200, `expected 200, got ${status}`);
      assert('version' in body && 'build' in body && 'environment' in body, 'missing version fields');
    });

    await runTest(outcomeResults, 'test_outcome.py::TestHiddenAuxiliary::test_h10_missing_claim_token_rejected', async () => {
      const missingRole = signToken({ sub: 1, username: 'alice.chen' });
      const { status, body } = await request('GET', '/api/admin/users', missingRole);
      assert(status === 401, `expected 401, got ${status}`);
      assert('error' in body && 'code' in body, 'missing error/code');
      assert(!('users' in body) && !('user' in body), 'rejected response leaked user data');
    });
  } catch (err) {
    outcomeResults['test_outcome.py::server_startup'] = {
      nodeid: 'test_outcome.py::server_startup',
      outcome: 'failed',
      call: { longrepr: err && err.stack ? err.stack : String(err) },
    };
  } finally {
    if (serverStarted) {
      proc.kill('SIGTERM');
      await new Promise((resolve) => proc.once('exit', resolve));
    } else {
      proc.kill('SIGKILL');
    }
  }

  const originalTvFallthrough = 'Non-critical token issue';
  const originalRcPassthrough = 'No authenticated user context on this request';

  await runTest(processResults, 'test_process.py::TestProcessP1P2TokenValidator::test_p1_token_validator_modified', async () => {
    const src = readSource('middleware/tokenValidator.js');
    assert(!src.includes(originalTvFallthrough), 'tokenValidator.js still contains original catch fallthrough');
  });

  await runTest(processResults, 'test_process.py::TestProcessP1P2TokenValidator::test_p2_catch_sends_rejection', async () => {
    const src = readSource('middleware/tokenValidator.js');
    const has401 = /401/.test(src) && (/res\.statusCode\s*=\s*401/.test(src) || /res\.status\(\s*401\s*\)/.test(src));
    const fallthroughGone = !src.includes(originalTvFallthrough);
    assert(has401 && fallthroughGone, `has 401: ${has401}, fallthrough removed: ${fallthroughGone}`);
  });

  await runTest(processResults, 'test_process.py::TestProcessP3RoleChecker::test_p3_role_checker_rejects_unauthenticated', async () => {
    const src = readSource('middleware/roleChecker.js');
    const passthroughGone = !src.includes(originalRcPassthrough);
    const hasAuthCheck = /!req\.user/.test(src) && (/40[13]/.test(src) || /Authentication required/i.test(src));
    assert(passthroughGone || hasAuthCheck, 'roleChecker.js should reject unauthenticated protected requests');
  });

  await runTest(processResults, 'test_process.py::TestProcessP4DownstreamOnly::test_p4_not_downstream_only_fix', async () => {
    const tvSrc = readSource('middleware/tokenValidator.js');
    const rcSrc = readSource('middleware/roleChecker.js');
    const tvModified = !tvSrc.includes(originalTvFallthrough);
    const rcModified = !rcSrc.includes(originalRcPassthrough);
    assert(!(rcModified && !tvModified), 'Only roleChecker.js was modified; tokenValidator root cause remains');
  });

  await runTest(processResults, 'test_process.py::TestProcessP5StatusCode::test_p5_rejection_not_200', async () => {
    const src = readSource('middleware/tokenValidator.js');
    const catchIdx = src.indexOf('catch');
    const afterCatch = catchIdx > 0 ? src.slice(catchIdx) : '';
    const sends200 = /res\.status\(\s*200\s*\)/.test(afterCatch) || /statusCode\s*=\s*200/.test(afterCatch);
    assert(!sends200, 'catch block sends 200 with an error body');
  });

  const normalized = writeOutputs(outcomeResults, processResults);
  console.log(`normalized reward: ${normalized.toFixed(6)}`);
  process.exit(normalized === 1 ? 0 : 1);
}

main().catch((err) => {
  fs.writeFileSync(path.join(LOG_DIR, 'reward.txt'), '0.000000\n');
  fs.writeFileSync(path.join(LOG_DIR, 'reward.json'), JSON.stringify({
    total_score: 0,
    max_score: 100,
    normalized_score: 0,
    error: err && err.stack ? err.stack : String(err),
  }, null, 2) + '\n');
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
NODE
