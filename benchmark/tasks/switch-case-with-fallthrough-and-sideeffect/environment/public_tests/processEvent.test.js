import assert from "node:assert/strict";
import test from "node:test";
import { createEmitter } from "../src/events.js";
import { createLogger } from "../src/logger.js";
import { processEvent } from "../src/processEvent.js";

test("user login logs and updates activity", () => {
  const logger = createLogger();
  const emitter = createEmitter();
  const updates = [];
  const result = processEvent("USER_LOGIN", { userId: 1 }, { logger, emitter, updates });
  assert.equal(result.processed.includes("activity"), true);
  assert.equal(logger.calls.length, 1);
});

test("logout emits session_end", () => {
  const emitter = createEmitter();
  const result = processEvent("USER_LOGOUT", { userId: 1 }, { emitter });
  assert.equal(result.processed[0], "logout");
  assert.equal(emitter.events[0].name, "session_end");
});

test("purchase complete logs purchase", () => {
  const logger = createLogger();
  const result = processEvent("PURCHASE_COMPLETE", { orderId: 7 }, { logger });
  assert.equal(result.processed[0], "purchase");
});

test("unknown event logs warning", () => {
  const logger = createLogger();
  const result = processEvent("OTHER", { }, { logger });
  assert.equal(result.processed[0], "unknown");
  assert.equal(logger.calls[0].level, "warn");
});
