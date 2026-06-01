# Fix the runtime dependency issue in this Python project

The project is in `/root/task/project`. `pip install` succeeds, but the app still crashes at runtime with a `TypeError`. The traceback we captured is in `/root/task/traceback.txt`.

Please fix the real dependency problem in place and keep the existing behavior working. Save your edits under `/root/task/project`.

The final dependency set must be reproducible: update the project dependency declarations and generate `/root/task/project/requirements.lock` with the exact installed versions that make the runtime behavior pass. Do not solve this by skipping dependency resolution or by using install flags such as `--no-deps` or `--force-reinstall`.

Good places to start:
- `/root/task/traceback.txt`
- `/root/task/project/requirements.txt`
- `/root/task/package_build/`

If you need packages, use the offline wheels in `/root/task/local_index`.

Expected runtime behavior after the dependency fix: `run_alpha_feature()` must return the alpha feature string, `run_beta_feature()` must return the beta feature string, and `run_combined()` must combine both feature outputs without raising the captured `TypeError`.
