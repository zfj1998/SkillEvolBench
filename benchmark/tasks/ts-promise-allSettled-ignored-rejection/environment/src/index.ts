/**
 * FinPulse Report Generator — CLI entry point
 *
 * Usage:
 *   npx ts-node --transpile-only src/index.ts [--period 2025-05] [--timeout 200] [--output report.json]
 */

import { generateReport } from './reportGenerator';
import { ReportConfig } from './types';

function parseArgs(): ReportConfig {
  const args = process.argv.slice(2);
  const config: ReportConfig = {
    period: '2025-05',
    timeout_ms: 200,
    output_path: 'report.json',
  };
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--period':  config.period = args[++i]; break;
      case '--timeout': config.timeout_ms = parseInt(args[++i], 10); break;
      case '--output':  config.output_path = args[++i]; break;
    }
  }
  return config;
}

async function main(): Promise<void> {
  const config = parseArgs();
  console.log(`Generating report for ${config.period}...`);
  const report = await generateReport(config);
  console.log(`Done. ${report.sections.length} sections written.`);
}

main().catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
