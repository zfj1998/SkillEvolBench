"""
Application configuration management.

Loads settings from environment variables with sensible defaults
for development. Production values are injected via docker-compose
or Kubernetes ConfigMap.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CacheSettings:
    """Controls the in-memory result cache behaviour."""
    max_entries: int = 2048
    ttl_seconds: int = 3600
    eviction_policy: str = "lru"           # lru | fifo
    warm_on_startup: bool = False


@dataclass(frozen=True)
class ProcessingSettings:
    """Tuning knobs for the data-processing pipeline."""
    max_payload_bytes: int = 512_000       # ~500 KB
    enrichment_timeout_ms: int = 5000
    coalesce_window_seconds: int = 10      # identical requests share a pricing window
    pipeline_stages: tuple = ("normalize", "enrich", "aggregate")
    decimal_precision: int = 4
    null_strategy: str = "skip"            # skip | zero | raise


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_file: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    """Root configuration — assembled once at import time."""
    app_name: str = "analytics-processing-service"
    version: str = "1.4.2"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    secret_key: str = "change-me-in-production"

    cache: CacheSettings = field(default_factory=CacheSettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)


def load_config() -> AppConfig:
    """Build config from environment, falling back to dataclass defaults."""
    cache = CacheSettings(
        max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "2048")),
        ttl_seconds=int(os.getenv("CACHE_TTL", "3600")),
    )
    processing = ProcessingSettings(
        max_payload_bytes=int(os.getenv("MAX_PAYLOAD_BYTES", "512000")),
        enrichment_timeout_ms=int(os.getenv("ENRICHMENT_TIMEOUT_MS", "5000")),
        coalesce_window_seconds=int(os.getenv("COALESCE_WINDOW_SECONDS", "10")),
    )
    logging_cfg = LoggingSettings(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE"),
    )
    return AppConfig(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "5000")),
        secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
        cache=cache,
        processing=processing,
        logging=logging_cfg,
    )


# Singleton — imported by other modules
config = load_config()
