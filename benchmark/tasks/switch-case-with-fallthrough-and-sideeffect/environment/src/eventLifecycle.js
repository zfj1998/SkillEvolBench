import { appendActivityUpdate, resolveAlertLevel } from "./sideEffectPlan.js";
import { markProcessed, recordBranch } from "./eventContext.js";

export function runActivityLifecycle(context) {
  appendActivityUpdate(context.updates, context.data.userId);
  recordBranch(context.result, "activity");
  markProcessed(context.result, "activity");
}

export function runPurchaseLifecycle(context) {
  context.logger?.info(`purchase:${context.data.orderId}`);
  recordBranch(context.result, "purchase");
  markProcessed(context.result, "purchase");
}

export function runAlertLifecycle(context) {
  context.result.level = resolveAlertLevel(context.result.originalType);
  recordBranch(context.result, "alert");
  markProcessed(context.result, "alert");
}

export function runUnknownLifecycle(context) {
  context.logger?.warn(`unknown:${context.result.originalType}`);
  recordBranch(context.result, "unknown");
  markProcessed(context.result, "unknown");
}
