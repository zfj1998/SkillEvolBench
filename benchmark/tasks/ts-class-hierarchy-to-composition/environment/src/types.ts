export type DataRecord = {
  id: string;
  value: number;
  tags?: string[];
};

export type UserRecord = {
  id: string;
  score: number;
  active: boolean;
};

export type ProcessorConfig = {
  label: string;
  multiplier: number;
};

export type ProcessResult<T> = {
  input: T;
  valid: boolean;
  transformed: Record<string, unknown>;
  notes: string[];
};

export type RecordValidator<T> = (input: T) => boolean;
export type RecordTransformer<T> = (input: T) => Record<string, unknown>;
export type RecordEnricher<T> = (result: ProcessResult<T>) => Record<string, unknown>;
