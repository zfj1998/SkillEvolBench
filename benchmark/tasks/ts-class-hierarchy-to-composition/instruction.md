# Refactor the processor hierarchy into composition without breaking TypeScript constraints

The TypeScript project is in `/root/task`. The current `BaseProcessor -> DataProcessor -> SpecializedProcessor` chain is getting in the way of extension, and we want injectable validation / transform / enrich steps instead of adding more subclasses.

Please refactor the existing code in place so the design is composition-based, while keeping behavior stable and keeping TypeScript happy:
- preserve the current processing order
- keep the runtime output equivalent
- keep strict TypeScript compilation passing
- do not weaken the types with `any`

Start here:
- `/root/task/README.md`
- `/root/task/docs/migration-notes.md`
- `/root/task/package.json`
- `/root/task/tsconfig.json`
- `/root/task/src/BaseProcessor.ts`
- `/root/task/src/DataProcessor.ts`
- `/root/task/src/SpecializedProcessor.ts`
- `/root/task/src/LegacyReporter.ts`

Make your edits under `/root/task`. Keep the project in place and do not replace the implementation with a simplified stub.

Deliverable note: this is a TypeScript refactoring task, not a structured-output task. Do not create a separate report file; the required artifacts are the edited TypeScript source files under `/root/task/src` and any needed config updates, with the existing runtime output and strict compile contract preserved.
