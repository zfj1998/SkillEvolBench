from __future__ import annotations


def deep_diff(left, right, path=""):
    differences = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else key
            if key not in left:
                differences.append({"field_path": next_path, "source_a_value": None, "source_b_value": right[key]})
            elif key not in right:
                differences.append({"field_path": next_path, "source_a_value": left[key], "source_b_value": None})
            else:
                differences.extend(deep_diff(left[key], right[key], next_path))
        return differences
    if left != right:
        return [{"field_path": path, "source_a_value": left, "source_b_value": right}]
    return []
