"""Application that loads and uses config."""
import yaml
import json


def load_config(path="config.yaml"):
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_db_config():
    """Get database configuration."""
    config = load_config()
    return config.get("database", {})


def get_ssl_config():
    """Get SSL configuration from database section."""
    config = load_config()
    db = config.get("database", {})
    return db.get("ssl", {})


def validate_config(config, schema_path="config_schema.json"):
    """Validate config against JSON schema."""
    with open(schema_path) as f:
        schema = json.load(f)

    # Simple validation (without jsonschema library)
    errors = []
    if "database" not in config:
        errors.append("Missing 'database' section")
    else:
        db = config["database"]
        if "pool_size" not in db:
            errors.append("Missing database.pool_size")
        elif not isinstance(db["pool_size"], int):
            errors.append("database.pool_size must be integer")

    return {"valid": len(errors) == 0, "errors": errors}


if __name__ == "__main__":
    config = load_config()
    print(f"Pool size: {config['database']['pool_size']}")
    ssl = config['database'].get('ssl', {})
    if ssl.get('enabled'):
        print(f"SSL enabled, cert: {ssl['cert_path']}")
    else:
        print("SSL disabled")
