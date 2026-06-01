"""Generate fixture for T6: multi-layer-sanity-pipeline.
Composition task with MULTIPLE issues:
1. September/East has 5× duplicate revenue batches (anomaly)
2. department_budget has 3 NULL department entries (null handling)
3. project_departments is M:N (cross-query sum mismatch potential)
4. international_offices.csv has unicode city names"""
print("T6: fixture pre-generated")
