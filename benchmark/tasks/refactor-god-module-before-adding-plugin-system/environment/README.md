# Fixture Plan: E1-LS3-T4

Role: `context_shift`
Gap focus: `The refactor is an implicit prerequisite rather than the explicit task surface.`

Scenario:
The user request sounds like a feature task, but the real obstacle is a 500-line `processor.py` that mixes parsing, transforming, output, and error handling. A plugin system is not maintainable until the module is split.

Intended fixture files:
- `processor.py`
- `plugins/__init__.py`
- `public_tests/test_processor.py`
- `public_tests/test_plugin_system.py`

Key design notes:
The single module should contain at least four responsibilities and several global variables. The fixture must make it possible to hack in plugins badly, while the process verifier rewards the cleaner split.

Public checks:
- All legacy tests still pass.
- Users can register a custom transform function.
- Plugins can be loaded from the `plugins/` directory.

Hidden checks:
- Plugins execute during the transform stage.
- Plugin ordering is controllable.
- A broken plugin does not crash the whole processor.
- The old global state no longer couples modules together.

Process checks:
- `processor.py` is split into at least four focused modules or equivalent units.
- Global state is removed or encapsulated.
- Plugins use an explicit registration or loading mechanism.
