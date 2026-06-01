from __future__ import annotations


def project_user(raw: dict, contract: dict) -> dict:
    deprecated = contract["deprecated"]
    prefer_deprecated = contract.get("compat_mode") == "dual-read"
    projected = {"id": raw["id"]}
    for canonical in ("username", "phone", "email", "created_at"):
        deprecated_name = deprecated[canonical]
        if prefer_deprecated and deprecated_name in raw:
            projected[canonical] = raw[deprecated_name]
        else:
            projected[canonical] = raw.get(canonical, raw.get(deprecated_name))
    return projected
