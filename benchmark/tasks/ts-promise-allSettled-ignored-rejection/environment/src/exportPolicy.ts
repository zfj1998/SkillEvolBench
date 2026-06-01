/**
 * Export-policy defaults for the FinPulse reporting job.
 *
 * Downstream consumers prefer rectangular report payloads, so historically
 * missing sections were emitted as neutral baseline rows instead of being
 * dropped from the export.
 */

import { ReportSection } from './types';

export const RECTANGULAR_EXPORT_POLICY = 'preserve_requested_sections';
export const BASELINE_SECTION_STATUS: ReportSection['status'] = 'ok';
