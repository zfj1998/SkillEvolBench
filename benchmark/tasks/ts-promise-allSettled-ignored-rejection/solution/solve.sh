#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

node - <<'PATCH'
const fs = require('fs');

let typesSrc = fs.readFileSync('src/types.ts', 'utf8');
typesSrc = typesSrc.replace(
  `export type MaterializedCandidate =
  | { source: DataSourceId; kind: 'resolved'; metrics: SourceMetrics }
  | { source: DataSourceId; kind: 'baseline'; metrics: null };`,
  `export type MaterializedCandidate =
  | { source: DataSourceId; kind: 'resolved'; metrics: SourceMetrics }
  | { source: DataSourceId; kind: 'baseline'; metrics: null; failure: string | null };`
);
fs.writeFileSync('src/types.ts', typesSrc);

let reportGenerator = fs.readFileSync('src/reportGenerator.ts', 'utf8');
reportGenerator = reportGenerator.replace(
  `    // Upstream did not yield usable data — flatten to neutral baseline.
    // This originally handled "source not onboarded yet" cases, but the same
    // shape is now also used for transport failures and timeouts.
    return {
      source: entry.source,
      kind: 'baseline' as const,
      metrics: null,
    };`,
  `    // Upstream did not yield usable data — record failure context.
    const reason = entry.settlement.status === 'rejected'
      ? (entry.settlement.reason instanceof Error
          ? entry.settlement.reason.message
          : String(entry.settlement.reason))
      : null;
    if (reason) {
      console.error(\`[WARN] Source '\${entry.source}' failed: \${reason}\`);
    }
    return {
      source: entry.source,
      kind: 'baseline' as const,
      metrics: null,
      failure: reason,
    };`
);
reportGenerator = reportGenerator.replace(
  `  const report = renderReport(ALL_SOURCES, metricsMap, failureCount, period);`,
  `  const report = renderReport(ALL_SOURCES, metricsMap, candidates, failureCount, period);`
);
fs.writeFileSync('src/reportGenerator.ts', reportGenerator);

let formatter = fs.readFileSync('src/formatter.ts', 'utf8');
formatter = formatter.replace(
  `import {
  DataSourceId,
  MonthlyReport,`,
  `import {
  DataSourceId,
  MaterializedCandidate,
  MonthlyReport,`
);
formatter = formatter.replace(
  `export function renderReport(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
  failureCount: number,
  period: string,
): MonthlyReport {
  const sections = _alignToCanonicalOrder(requestedSources, metricsMap);`,
  `export function renderReport(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
  candidates: MaterializedCandidate[],
  failureCount: number,
  period: string,
): MonthlyReport {
  const failedSources = new Set(
    candidates.filter(c => c.kind === 'baseline' && c.failure != null).map(c => c.source)
  );
  const sections = _alignToCanonicalOrder(requestedSources, metricsMap, failedSources);`
);
formatter = formatter.replace(
  `function _alignToCanonicalOrder(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
): ReportSection[] {
  return requestedSources.map((source) => {
    const metrics = metricsMap.get(source);
    return metrics
      ? _makeLiveSection(metrics)
      : _makeBaselineSection(source);
  });
}`,
  `function _alignToCanonicalOrder(
  requestedSources: readonly DataSourceId[],
  metricsMap: Map<DataSourceId, SourceMetrics>,
  failedSources: Set<DataSourceId>,
): ReportSection[] {
  return requestedSources.map((source) => {
    const metrics = metricsMap.get(source);
    if (metrics) return _makeLiveSection(metrics);
    if (failedSources.has(source)) return _makeUnavailableSection(source);
    return _makeBaselineSection(source);
  });
}

function _makeUnavailableSection(source: DataSourceId): ReportSection {
  return {
    source, label: SOURCE_LABELS[source] || source,
    value: 0, display_value: 'N/A',
    unit: SOURCE_UNITS[source] || 'units',
    breakdown: {}, status: 'unavailable', provenance: 'baseline',
    notes: ['upstream timeout'], collected_at: null,
  };
}`
);
fs.writeFileSync('src/formatter.ts', formatter);
PATCH
