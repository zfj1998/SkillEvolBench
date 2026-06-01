import type { ProcessResult, ProcessorConfig } from "./types";

export function buildLogMessage(config: ProcessorConfig, message: string): string {
  return `[${config.label}] ${message}`;
}

export function finalizeSpecializedResult<T>(
  base: ProcessResult<T>,
  transformed: Record<string, unknown>,
): ProcessResult<T> {
  return {
    ...base,
    transformed,
    notes: [...base.notes, "specialized"],
  };
}
