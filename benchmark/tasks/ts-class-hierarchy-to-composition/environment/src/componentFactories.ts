import type {
  DataRecord,
  ProcessResult,
  ProcessorConfig,
  RecordEnricher,
  RecordTransformer,
  RecordValidator,
} from "./types";

export function defaultValidator(input: DataRecord): boolean {
  return Boolean(input.id);
}

export function createDataTransformer(config: ProcessorConfig): RecordTransformer<DataRecord> {
  return (input) => ({
    id: input.id,
    value: input.value * config.multiplier,
    tags: input.tags ?? [],
  });
}

export function createEnricher(): RecordEnricher<DataRecord> {
  return (result: ProcessResult<DataRecord>) => ({
    ...result.transformed,
    enriched: true,
  });
}

export function createUserValidator(): RecordValidator<{ id: string; score: number; active: boolean }> {
  return (input) => Boolean(input.id) && typeof input.active === "boolean";
}
