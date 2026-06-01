/**
 * Report rendering and canonical section alignment for the
 * FinPulse platform.
 *
 * Produces the final report shape expected by downstream consumers.
 * Guarantees a stable section set in canonical source order.
 */

import {
  DataSourceId,
  MonthlyReport,
  ReportMeta,
  ReportSection,
  SOURCE_LABELS,
  SOURCE_UNITS,
  SourceMetrics,
} from './types';
import { BASELINE_SECTION_STATUS } from './exportPolicy';

// ── Report rendering ────────────────────────────────────────────────

export function renderReport(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
  failureCount: number,
  period: string,
): MonthlyReport {
  const sections = _alignToCanonicalOrder(requestedSources, metricsMap);
  const meta = _deriveMeta(requestedSources, metricsMap, sections, failureCount, period);

  return {
    title: `FinPulse Monthly Report — ${period}`,
    sections,
    meta,
  };
}

// ── Section alignment ───────────────────────────────────────────────

// Ensure downstream consumers always receive a complete canonical section set.
function _alignToCanonicalOrder(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
): ReportSection[] {
  return requestedSources.map((source) => {
    const metrics = metricsMap.get(source);
    return metrics
      ? _makeLiveSection(metrics)
      : _makeBaselineSection(source);
  });
}

function _makeLiveSection(metrics: SourceMetrics): ReportSection {
  return {
    source: metrics.source,
    label: SOURCE_LABELS[metrics.source] || metrics.source,
    value: metrics.value,
    display_value: _fmtValue(metrics.value, metrics.unit),
    unit: metrics.unit,
    breakdown: metrics.breakdown,
    status: 'ok',
    provenance: 'live',
    notes: [],
    collected_at: metrics.collected_at,
  };
}

function _makeBaselineSection(source: DataSourceId): ReportSection {
  return {
    source,
    label: SOURCE_LABELS[source] || source,
    value: 0,
    display_value: _fmtValue(0, SOURCE_UNITS[source]),
    unit: SOURCE_UNITS[source] || 'units',
    breakdown: {},
    // Historically this baseline section represented "source not onboarded
    // yet", so it was treated as healthy. Reusing it for runtime failures is
    // what makes the report misleading.
    status: BASELINE_SECTION_STATUS,
    provenance: 'baseline',
    notes: [],
    collected_at: null,
  };
}

// ── Metadata derivation ─────────────────────────────────────────────

function _deriveMeta(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
  sections: ReportSection[],
  failureCount: number,
  period: string,
): ReportMeta {
  const totalPrimary = sections.reduce((sum, s) => sum + s.value, 0);
  const nonOk = sections.filter((s) => s.status !== 'ok');

  return {
    generated_at: new Date().toISOString(),
    period,
    total_primary_value: Math.round(totalPrimary * 100) / 100,
    sources_requested: requestedSources.length,
    sources_completed: metricsMap.size,
    recoverable_failures: failureCount,
    failure_log: nonOk.map((s) => `${s.source}: section status ${s.status}`),
  };
}

// ── Value formatting ────────────────────────────────────────────────

function _fmtValue(value: number, unit: string): string {
  switch (unit) {
    case 'USD':   return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    case 'users':
    case 'visits': return value.toLocaleString('en-US');
    case 'score':  return `${value.toFixed(1)}/5.0`;
    default:       return String(value);
  }
}
