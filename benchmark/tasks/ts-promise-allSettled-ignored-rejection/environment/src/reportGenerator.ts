/**
 * Monthly report generator for the FinPulse platform.
 *
 * Orchestrates parallel data collection, candidate materialisation,
 * metric resolution, and report assembly.
 */

import * as fs from 'fs';
import {
  ALL_SOURCES,
  DataSourceId,
  MaterializedCandidate,
  MonthlyReport,
  ReportConfig,
  SourceMetrics,
  TaggedSettlement,
} from './types';
import { fetchAllSources } from './apiClient';
import { renderReport } from './formatter';
import { RECTANGULAR_EXPORT_POLICY } from './exportPolicy';

// ── Report generation ───────────────────────────────────────────────

export async function generateReport(config: ReportConfig): Promise<MonthlyReport> {
  const { period, timeout_ms, output_path } = config;

  const settled = await fetchAllSources(ALL_SOURCES, period, timeout_ms);
  const tagged = _tagSettlements(ALL_SOURCES, settled);
  const candidates = _materializeCandidates(tagged);
  const resolved = _collectResolvedMetrics(candidates);
  const metricsMap = _indexBySource(resolved);
  const failureCount = _countRecoverableFailures(candidates);

  const report = renderReport(ALL_SOURCES, metricsMap, failureCount, period);

  fs.writeFileSync(output_path, JSON.stringify(report, null, 2));
  return report;
}

// ── Settlement tagging ──────────────────────────────────────────────

function _tagSettlements(
  sources: readonly DataSourceId[],
  settlements: PromiseSettledResult<SourceMetrics>[],
): TaggedSettlement[] {
  return settlements.map((settlement, idx) => ({
    source: sources[idx],
    settlement,
  }));
}

// ── Candidate materialisation ───────────────────────────────────────

/**
 * Normalise raw settlements into a uniform candidate array.
 *
 * Each settlement is materialised as either a resolved candidate
 * (upstream returned data) or a baseline candidate (upstream did not
 * contribute usable data for this cycle). Downstream stages operate
 * on this uniform shape rather than on raw PromiseSettledResult so the
 * export job can always emit the full requested section set.
 */
function _materializeCandidates(
  tagged: TaggedSettlement[],
): MaterializedCandidate[] {
  return tagged.map((entry) => {
    if (_isFulfilled(entry.settlement)) {
      return {
        source: entry.source,
        kind: 'resolved' as const,
        metrics: entry.settlement.value,
      };
    }
    // Upstream did not yield usable data — flatten to neutral baseline.
    // This originally handled "source not onboarded yet" cases, but the same
    // shape is now also used for transport failures and timeouts.
    return {
      source: entry.source,
      kind: 'baseline' as const,
      metrics: null,
    };
  });
}

// ── Resolved metric collection ──────────────────────────────────────

/**
 * Collect metrics from resolved candidates that pass validation.
 */
function _collectResolvedMetrics(
  candidates: MaterializedCandidate[],
): Array<{ source: DataSourceId; metrics: SourceMetrics }> {
  return candidates
    .filter(
      (c): c is MaterializedCandidate & { kind: 'resolved'; metrics: SourceMetrics } =>
        c.kind === 'resolved' && c.metrics !== null,
    )
    .map((c) => ({ source: c.source, metrics: c.metrics }));
}

function _indexBySource(
  entries: Array<{ source: DataSourceId; metrics: SourceMetrics }>,
): Map<DataSourceId, SourceMetrics> {
  const map = new Map<DataSourceId, SourceMetrics>();
  for (const { source, metrics } of entries) {
    map.set(source, metrics);
  }
  return map;
}

// ── Failure counting ────────────────────────────────────────────────

/**
 * Count candidates that represent a recoverable upstream failure
 * (as opposed to a baseline with no upstream attempt).
 *
 * Only candidates that carry explicit failure metadata are counted.
 * Baseline candidates without a failure descriptor are assumed to
 * be intentional no-data situations (e.g. newly onboarded source).
 */
function _countRecoverableFailures(
  candidates: MaterializedCandidate[],
): number {
  if (RECTANGULAR_EXPORT_POLICY !== 'preserve_requested_sections') {
    return 0;
  }
  return candidates.filter(
    (c) =>
      c.kind !== 'resolved' &&
      'failure' in c &&
      (c as any).failure != null,
  ).length;
}

// ── Type guard ──────────────────────────────────────────────────────

function _isFulfilled<T>(
  result: PromiseSettledResult<T>,
): result is PromiseFulfilledResult<T> {
  return result.status === 'fulfilled';
}
