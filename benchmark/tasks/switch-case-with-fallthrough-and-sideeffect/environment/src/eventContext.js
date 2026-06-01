import { SAMPLE_CATALOG } from "./sampleEventCatalog.js";

export function createEventContext(eventType, data, deps = {}) {
  return {
    data,
    logger: deps.logger,
    emitter: deps.emitter,
    updates: deps.updates || [],
    catalogEntry: SAMPLE_CATALOG[eventType] ?? null,
    result: { originalType: eventType, processed: [], branchTrail: [] },
  };
}

export function markProcessed(result, step) {
  result.processed.push(step);
}

export function recordBranch(result, branchName) {
  result.branchTrail.push(branchName);
}
