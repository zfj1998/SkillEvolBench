# Fixture Plan: E1-LS3-T2

Role: `enriched`
Gap focus: `Gap 1: preserving hidden edge behavior during refactoring.`

Scenario:
A JavaScript event processor has a long switch statement. Product wants a strategy mapping, but the switch relies on intentional fallthrough and several side effects that cannot be dropped.

Intended fixture files:
- `src/processEvent.js`
- `src/logger.js`
- `src/events.js`
- `public_tests/processEvent.test.js`

Key design notes:
The switch should include USER_LOGIN -> USER_ACTIVITY fallthrough, PURCHASE_START -> PURCHASE_COMPLETE fallthrough, and ERROR -> WARNING fallthrough. Logging, emitEvent, and alert-level behavior must be observable through mocks.

Public checks:
- Basic USER_LOGIN, USER_LOGOUT, PURCHASE_COMPLETE, and default behavior still work.
- The refactor removes the original monolithic switch or clearly replaces it.

Hidden checks:
- USER_LOGIN still triggers USER_ACTIVITY behavior.
- PURCHASE_START still runs purchase completion logic.
- ERROR still inherits WARNING behavior while keeping high severity.
- Logger and emitEvent side effects fire exactly where they used to.
- Default behavior still logs a warning and preserves the original event type.

Process checks:
- The replacement design explicitly preserves fallthrough semantics.
- Side effects remain testable and are not lost in a pure lookup-table rewrite.
- The switch has been structurally refactored rather than wrapped untouched.
