from __future__ import annotations
from pathlib import Path
import importlib.util
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()

def load_topic_filter():
    spec = importlib.util.spec_from_file_location("topic_filter", ROOT / "topic_filter.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

class TestProcess:
    def test_has_filter(self):
        assert "is_relevant" in (ROOT / "topic_filter.py").read_text()

    def test_filter_rejects_noise_and_keeps_renewables(self):
        topic_filter = load_topic_filter()
        assert topic_filter.is_relevant({"tags": ["renewables", "solar", "wind"]})
        assert not topic_filter.is_relevant({"tags": ["semiconductors", "ai chips"]})
        assert not topic_filter.is_relevant({"tags": ["ai", "investment"]})
