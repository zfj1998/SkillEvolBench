from __future__ import annotations


def fetch_backup_record(session, product_id: int, logger):
    response = session.get(f"http://localhost:5050/api/products/backup/{product_id}", timeout=10)
    response.raise_for_status()
    payload = response.json()
    record = payload.get("data")
    logger.info("fetched backup for id=%s", product_id)
    return record
