# FastAPI release notes excerpt

## 0.95.0
- Works with the Pydantic v1 series.
- Dependency metadata constrains `pydantic` to `<2.0`.

## 0.100.0
- Adds support for the Pydantic v2 series.
- Projects migrating from FastAPI 0.95.x should update Pydantic model code
  from `@validator` / `.dict()` to `@field_validator` / `.model_dump()`.
