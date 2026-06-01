from pipeline import run_pipeline


def test_run_pipeline_json_string():
    result = run_pipeline('{"name": "alice"}')
    assert '"_transformed": true' in result


def test_run_pipeline_dict():
    result = run_pipeline({"name": "bob"})
    assert '"name": "bob"' in result


def test_run_pipeline_empty_string():
    result = run_pipeline("")
    assert result == '{"_default": true}'


def test_run_pipeline_contains_transformed_marker():
    result = run_pipeline({"hello": "world"})
    assert '"_transformed": true' in result
