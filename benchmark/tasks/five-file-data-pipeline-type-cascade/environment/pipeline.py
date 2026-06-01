"""ETL Pipeline entry point."""
from extractor import extract_records
from validator import validate_batch
from transformer import transform_batch
from enricher import enrich_batch
from loader import load_records, run_pipeline_report


def run_pipeline():
    """Run the full ETL pipeline."""
    records = extract_records()
    validated = validate_batch(records)
    transformed = transform_batch(validated)
    enriched = enrich_batch(transformed)
    result = load_records(enriched)
    return run_pipeline_report(result)


if __name__ == "__main__":
    run_pipeline()
