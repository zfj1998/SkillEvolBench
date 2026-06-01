import { DataProcessor } from "./DataProcessor";
import { finalizeSpecializedResult } from "./processorRuntime";
import type { DataRecord, ProcessResult, ProcessorConfig } from "./types";

export class SpecializedProcessor extends DataProcessor {
  constructor(config: ProcessorConfig) {
    super(config);
  }

  process(input: DataRecord): ProcessResult<DataRecord> {
    const base = super.process(input);
    return finalizeSpecializedResult(base, {
      ...base.transformed,
      enriched: true,
    });
  }
}
