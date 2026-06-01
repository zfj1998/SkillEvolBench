/**
 * API client for the FinPulse data sources.
 *
 * Each data source is an internal micro-service that returns metrics
 * for a given reporting period.  In production these are HTTP calls;
 * here we simulate them with deterministic data and realistic latency
 * so that integration tests produce stable numbers.
 */

import { DataSourceId, SourceMetrics } from './types';

// ── Simulated latencies (ms) — based on production p95 monitoring ───

const BASE_LATENCY: Record<DataSourceId, number> = {
  user_stats: 40,
  orders:     60,
  inventory: 250,
  reviews:   280,
  traffic:    35,
};

function _effectiveLatency(source: DataSourceId, period: string): number {
  const base = BASE_LATENCY[source];
  if ((source === 'inventory' || source === 'reviews') && period.endsWith('-12')) {
    return base + 200;
  }
  return base;
}

// ── Deterministic mock data ─────────────────────────────────────────

function _generateMetrics(source: DataSourceId, period: string): SourceMetrics {
  const seed = Array.from(source + period).reduce((a, c) => a + c.charCodeAt(0), 0);
  const pr = (n: number) => ((seed * 9301 + 49297) % 233280) / 233280 * n;

  const breakdownKeys: Record<DataSourceId, string[]> = {
    user_stats: ['desktop', 'mobile', 'tablet'],
    orders:     ['online', 'in_store', 'wholesale'],
    inventory:  ['warehouse_a', 'warehouse_b', 'warehouse_c'],
    reviews:    ['5_star', '4_star', '3_star', '2_star', '1_star'],
    traffic:    ['organic', 'paid', 'referral', 'direct'],
  };

  const baseValues: Record<DataSourceId, number> = {
    user_stats: 15000 + pr(5000),
    orders:     420000 + pr(80000),
    inventory:  1850000 + pr(200000),
    reviews:    4.2 + pr(0.6),
    traffic:    890000 + pr(110000),
  };

  const value = Math.round(baseValues[source] * 100) / 100;
  const keys = breakdownKeys[source];
  const breakdown: Record<string, number> = {};
  let remaining = value;
  for (let i = 0; i < keys.length; i++) {
    if (i === keys.length - 1) {
      breakdown[keys[i]] = Math.round(remaining * 100) / 100;
    } else {
      const portion = Math.round(remaining * (0.2 + pr(0.4)) * 100) / 100;
      breakdown[keys[i]] = portion;
      remaining -= portion;
    }
  }

  return {
    source, period, value,
    unit: source === 'reviews' ? 'score' : source === 'user_stats' ? 'users' :
          source === 'traffic' ? 'visits' : 'USD',
    breakdown,
    collected_at: new Date().toISOString(),
  };
}

// ── Public API ──────────────────────────────────────────────────────

export function fetchSource(
  source: DataSourceId, period: string,
): Promise<SourceMetrics> {
  const latency = _effectiveLatency(source, period);
  return new Promise((resolve) => {
    setTimeout(() => resolve(_generateMetrics(source, period)), latency);
  });
}

export async function fetchAllSources(
  sources: readonly DataSourceId[], period: string, timeout: number,
): Promise<PromiseSettledResult<SourceMetrics>[]> {
  const tasks = sources.map((source) => {
    const fetchP = fetchSource(source, period);
    const timeoutP = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(
        `Source '${source}' timed out after ${timeout}ms`
      )), timeout);
    });
    return Promise.race([fetchP, timeoutP]);
  });
  return Promise.allSettled(tasks);
}
