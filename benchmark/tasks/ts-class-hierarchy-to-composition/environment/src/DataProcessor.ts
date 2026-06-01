import { BaseProcessor } from "./BaseProcessor";
import type { DataRecord, ProcessResult, ProcessorConfig } from "./types";

export class DataProcessor extends BaseProcessor<DataRecord> {
  constructor(config: ProcessorConfig) {
    super(config);
  }

  protected transform(input: DataRecord) {
    return {
      id: input.id,
      value: input.value * this.config.multiplier,
      tags: input.tags ?? [],
    };
  }

  process(input: DataRecord): ProcessResult<DataRecord> {
    const valid = super.validate(input);
    return {
      input,
      valid,
      transformed: this.transform(input),
      notes: [this.log("validated")]
    };
  }
}
