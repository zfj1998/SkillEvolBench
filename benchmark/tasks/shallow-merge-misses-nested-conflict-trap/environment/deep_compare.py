from __future__ import annotations


def deep_diff(left, right, path=""):
    differences = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else key
            if key not in left:
                differences.append({"path": next_path, "source_a": None, "source_b": right[key]})
            elif key not in right:
                differences.append({"path": next_path, "source_a": left[key], "source_b": None})
            else:
                differences.extend(deep_diff(left[key], right[key], next_path))
        return differences

    if left != right:
        return [{"path": path, "source_a": left, "source_b": right}]

    return []
