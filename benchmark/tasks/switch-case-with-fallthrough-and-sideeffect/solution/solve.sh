#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path

path = Path("src/processEvent.js")
source = path.read_text(encoding="utf-8")

old = '''  switch (eventType) {
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
'''

new = '''  const strategyHandlers = {
    USER_LOGIN() {
      logger?.info(`login:${data.userId}`);
      runActivityLifecycle(context);
    },
    USER_ACTIVITY() {
      runActivityLifecycle(context);
    },
    USER_LOGOUT() {
      emitter?.emit("session_end", { userId: data.userId });
      recordBranch(result, "logout");
      result.processed.push("logout");
    },
    PURCHASE_START() {
      runPurchaseLifecycle(context);
    },
    PURCHASE_COMPLETE() {
      runPurchaseLifecycle(context);
    },
    ERROR() {
      logger?.error(data.message);
      runAlertLifecycle(context);
    },
    WARNING() {
      runAlertLifecycle(context);
    },
  };

  const handler = strategyHandlers[eventType];
  if (handler) {
    handler();
  } else {
    runUnknownLifecycle(context);
  }
'''

if old not in source:
    raise SystemExit("expected switch block not found")

path.write_text(source.replace(old, new), encoding="utf-8")
PY
