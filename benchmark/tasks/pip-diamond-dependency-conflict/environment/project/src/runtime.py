from package_alpha import run_alpha
from package_beta import run_beta


class RuntimeFacade:
    """Thin runtime wrapper used by the app entry points."""

    def run_alpha_pipeline(self, payload: str) -> str:
        return run_alpha(payload)

    def run_beta_pipeline(self, payload: str) -> str:
        return run_beta(payload)

    def run_combined_pipeline(self, payload: str) -> str:
        return f"{self.run_alpha_pipeline(payload)} | {self.run_beta_pipeline(payload)}"
