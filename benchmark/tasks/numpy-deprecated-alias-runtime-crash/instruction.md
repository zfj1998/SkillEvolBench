# Fix the ML pipeline crash after the dependency update

The pipeline code is in `/root/task/ml_pipeline`. After a dependency update, the pipeline now crashes at runtime. We captured the failure in `/root/task/ml_pipeline/error_log.txt`.

Please fix the real issue in the existing code and keep the pipeline compatible with the current dependency stack. Save your edits under `/root/task/ml_pipeline`.

Expected `run_basic_pipeline()` result schema:
- Top-level object: `{ "checks": <dict>, "scalar_demo": <number>, "feature_shape": [<row_count>, <column_count>] }`.
- `checks` reports the existing basic data-quality results from `run_basic_checks`.
- `scalar_demo` is the numeric output of `advanced_calculate(1.5)`.
- `feature_shape` describes the generated feature matrix dimensions for the feature matrix built by `run_basic_pipeline()`. The smoke path should exercise the modern feature code on five numeric inputs with complex features enabled, so the expected shape is `[5, 2]`.

Do not solve the crash by pinning NumPy back below the version required by the current stack; update the incompatible alias usage in the code.

Start with:
- `/root/task/ml_pipeline/error_log.txt`
- `/root/task/ml_pipeline/requirements.txt`
- `/root/task/ml_pipeline/src/`

If you need packages, use the offline wheels in `/root/task/local_index`.

Deliverable note: no standalone output file is required. The required artifacts are the edited files under `/root/task/ml_pipeline`; the verifier checks the existing `run_basic_pipeline()` dictionary schema documented above.
