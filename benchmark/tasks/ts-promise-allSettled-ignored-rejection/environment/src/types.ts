/**
 * Shared type definitions for the FinPulse reporting platform.
 */

export type DataSourceId =
  | 'user_stats'
  | 'orders'
  | 'inventory'
  | 'reviews'
  | 'traffic';

export const ALL_SOURCES: readonly DataSourceId[] = [
  'user_stats',
  'orders',
  'inventory',
  'reviews',
  'traffic',
] as const;

export interface SourceMetrics {
  source: DataSourceId;
  period: string;
  value: number;
  unit: string;
  breakdown: Record<string, number>;
  collected_at: string;
}

export interface TaggedSettlement {
  source: DataSourceId;
  settlement: PromiseSettledResult<SourceMetrics>;
}

export type MaterializedCandidate =
  | { source: DataSourceId; kind: 'resolved'; metrics: SourceMetrics }
  | { source: DataSourceId; kind: 'baseline'; metrics: null };

export interface ReportSection {
  source: DataSourceId;
  label: string;
  value: number;
  display_value: string;
  unit: string;
  breakdown: Record<string, number>;
  status: 'ok' | 'unavailable' | 'error';
  provenance: 'live' | 'baseline';
  notes: string[];
  collected_at: string | null;
}

export interface ReportMeta {
  generated_at: string;
  period: string;
  total_primary_value: number;
  sources_requested: number;
  sources_completed: number;
  recoverable_failures: number;
  failure_log: string[];
}

export interface MonthlyReport {
  title: string;
  sections: ReportSection[];
  meta: ReportMeta;
}

export interface ReportConfig {
  period: string;
  timeout_ms: number;
  output_path: string;
}

export const SOURCE_LABELS: Record<DataSourceId, string> = {
  user_stats: 'Active Users',
  orders: 'Order Revenue',
  inventory: 'Inventory Value',
  reviews: 'Customer Satisfaction',
  traffic: 'Site Traffic',
};

export const SOURCE_UNITS: Record<DataSourceId, string> = {
  user_stats: 'users',
  orders: 'USD',
  inventory: 'USD',
  reviews: 'score',
  traffic: 'visits',
};
