from .dependency_probe import snapshot_runtime_dependencies
from .runtime import RuntimeFacade
from .settings import ENABLE_DEPENDENCY_PROBE

_runtime = RuntimeFacade()
_versions = snapshot_runtime_dependencies() if ENABLE_DEPENDENCY_PROBE else {}


def run_alpha_feature() -> str:
    return _runtime.run_alpha_pipeline("sample")


def run_beta_feature() -> str:
    return _runtime.run_beta_pipeline("sample")


def run_combined() -> str:
    return _runtime.run_combined_pipeline("sample")
