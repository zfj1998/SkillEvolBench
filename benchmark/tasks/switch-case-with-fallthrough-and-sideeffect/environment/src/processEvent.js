import { deriveCatalogHint, shouldTrackCatalogNoise } from "./catalogPolicy.js";
import { createEventContext, recordBranch } from "./eventContext.js";
import {
  runActivityLifecycle,
  runAlertLifecycle,
  runPurchaseLifecycle,
  runUnknownLifecycle,
} from "./eventLifecycle.js";

export function processEvent(eventType, data, deps = {}) {
  const context = createEventContext(eventType, data, deps);
  const logger = context.logger;
  const emitter = context.emitter;
  const result = context.result;
  const catalogHint = deriveCatalogHint(context.catalogEntry);
  if (shouldTrackCatalogNoise(context.catalogEntry)) {
    recordBranch(result, `catalog:${catalogHint}`);
  }

  switch (eventType) {
    case "USER_LOGIN":
      logger?.info(`login:${data.userId}`);
    case "USER_ACTIVITY":
      runActivityLifecycle(context);
      break;
    case "USER_LOGOUT":
      emitter?.emit("session_end", { userId: data.userId });
      recordBranch(result, "logout");
      result.processed.push("logout");
      break;
    case "PURCHASE_START":
    case "PURCHASE_COMPLETE":
      runPurchaseLifecycle(context);
      break;
    case "ERROR":
      logger?.error(data.message);
    case "WARNING":
      runAlertLifecycle(context);
      break;
    default:
      runUnknownLifecycle(context);
      break;
  }

  return result;
}
