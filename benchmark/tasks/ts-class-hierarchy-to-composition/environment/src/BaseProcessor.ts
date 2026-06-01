import { buildLogMessage } from "./processorRuntime";
import type { ProcessResult, ProcessorConfig } from "./types";

export abstract class BaseProcessor<T extends { id: string }> {
  constructor(protected config: ProcessorConfig) {}

  validate(input: T): boolean {
    return Boolean(input.id);
  }

  protected log(message: string): string {
    return buildLogMessage(this.config, message);
  }

  abstract process(input: T): ProcessResult<T>;
}
