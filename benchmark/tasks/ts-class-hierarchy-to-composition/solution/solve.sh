#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
src = root / "src"

(src / "BaseProcessor.ts").write_text('''import type { DataRecord, ProcessResult, ProcessorConfig, RecordEnricher, RecordTransformer, RecordValidator } from "./types";

export function defaultValidator(input: DataRecord): boolean {
  return Boolean(input.id);
}

export function createLogMessage(config: ProcessorConfig, message: string): string {
  return `[${config.label}] ${message}`;
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
''', encoding="utf-8")

(src / "DataProcessor.ts").write_text('''import { createDataTransformer, createLogMessage, defaultValidator } from "./BaseProcessor";
import type { DataRecord, ProcessResult, ProcessorConfig, RecordTransformer, RecordValidator } from "./types";

export class DataProcessor {
  constructor(
    private readonly config: ProcessorConfig,
    private readonly validator: RecordValidator<DataRecord> = defaultValidator,
    private readonly transformer: RecordTransformer<DataRecord> = createDataTransformer(config),
  ) {}

  process(input: DataRecord): ProcessResult<DataRecord> {
    const valid = this.validator(input);
    return {
      input,
      valid,
      transformed: this.transformer(input),
      notes: [createLogMessage(this.config, "validated")],
    };
  }
}
''', encoding="utf-8")

(src / "SpecializedProcessor.ts").write_text('''import { createDataTransformer, createEnricher, defaultValidator } from "./BaseProcessor";
import { DataProcessor } from "./DataProcessor";
import type { DataRecord, ProcessResult, ProcessorConfig, RecordEnricher, RecordTransformer, RecordValidator } from "./types";

export class SpecializedProcessor {
  private readonly processor: DataProcessor;

  constructor(
    private readonly config: ProcessorConfig,
    validator: RecordValidator<DataRecord> = defaultValidator,
    transformer: RecordTransformer<DataRecord> = createDataTransformer(config),
    private readonly enricher: RecordEnricher<DataRecord> = createEnricher(),
  ) {
    this.processor = new DataProcessor(config, validator, transformer);
  }

  process(input: DataRecord): ProcessResult<DataRecord> {
    const base = this.processor.process(input);
    return {
      ...base,
      transformed: this.enricher(base),
      notes: [...base.notes, "specialized"],
    };
  }
}
''', encoding="utf-8")

tests = root / "public_tests"
tests.mkdir(exist_ok=True)
(tests / "processor.test.ts").write_text('''function assertEqual(actual: unknown, expected: unknown): void {
  if (actual !== expected) {
    throw new Error(`expected ${String(expected)}, got ${String(actual)}`);
  }
}

import { createUserValidator } from "../src/componentFactories";
import { SpecializedProcessor } from "../src/SpecializedProcessor";
import type { ProcessResult, RecordTransformer, UserRecord } from "../src/types";

const processor = new SpecializedProcessor({ label: "main", multiplier: 2 });
const result = processor.process({ id: "a", value: 4, tags: ["x"] });

assertEqual(result.valid, true);
assertEqual(result.notes.includes("specialized"), true);
assertEqual(result.transformed.enriched, true);

const user: UserRecord = { id: "u1", score: 10, active: true };
const userValidator = createUserValidator();
const userTransformer: RecordTransformer<UserRecord> = (input) => ({
  id: input.id,
  score: input.score + 1,
  active: input.active,
});
const userResult: ProcessResult<UserRecord> = {
  input: user,
  valid: userValidator(user),
  transformed: userTransformer(user),
  notes: ["user"],
};

assertEqual(userResult.valid, true);
assertEqual(userResult.transformed.score, 11);
''', encoding="utf-8")
PY
