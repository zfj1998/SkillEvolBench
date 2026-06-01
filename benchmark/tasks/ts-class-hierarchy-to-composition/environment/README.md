# Fixture Plan: E1-LS3-T3

Role: `variant`
Gap focus: `Gap 2: TypeScript strict typing, generics, and `super()` chains.`

Scenario:
A three-level TypeScript inheritance chain makes extension painful. Architecture wants injectable components, but the existing code depends on a two-level `super()` chain and generic types.

Intended fixture files:
- `src/BaseProcessor.ts`
- `src/DataProcessor.ts`
- `src/SpecializedProcessor.ts`
- `src/types.ts`
- `public_tests/processor.test.ts`
- `tsconfig.json`

Key design notes:
The fixture should force the implementation to preserve call order: validate -> transform -> enrich. `tsc --strict --noEmit` must pass. Generic parameter flow should be visible through at least one alternate record type.

Public checks:
- Existing processor behavior still passes tests.
- `tsc --strict --noEmit` succeeds after the refactor.
- The composed processor still produces the expected output for the default record type.

Hidden checks:
- Behavior matches the old inheritance version for the same input.
- Injected validators and transformers are actually used.
- Execution order remains validate -> transform -> enrich.
- An alternate generic type instantiates and runs correctly.

Process checks:
- Interfaces or injectable components replace `extends`-based specialization.
- The old `super()` chain is replaced by explicit delegation.
- Strict typing is preserved instead of weakened with `any`.
