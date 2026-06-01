import pytest
<<<<<<< HEAD
from utils import process_data
=======
from utils import helper_func
>>>>>>> feature/add-mode-param


class TestProcessing:
<<<<<<< HEAD
    def test_basic(self):
        result = process_data(["hello", "world"])
        assert result == ["HELLO", "WORLD"]

    def test_empty(self):
        result = process_data([])
        assert result == []

    def test_whitespace(self):
        result = process_data(["  hello  ", " world "])
        assert result == ["HELLO", "WORLD"]
=======
    def test_basic(self):
        result = helper_func(["hello", "world"])
        assert result == ["HELLO", "WORLD"]

    def test_empty(self):
        result = helper_func([])
        assert result == []

    def test_strict_mode(self):
        result = helper_func(["hi", "hello", "yo"], mode="strict")
        assert result == ["HELLO"]

    def test_lenient_mode(self):
        result = helper_func(["", "hello"], mode="lenient")
        assert result == ["N/A", "HELLO"]

    def test_default_mode(self):
        result = helper_func(["hello", "world"], mode="default")
        assert result == ["HELLO", "WORLD"]
>>>>>>> feature/add-mode-param
