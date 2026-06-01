from __future__ import annotations


def deep_diff(left, right, path=""):
    diffs = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else key
            if key not in left:
                diffs.append({"path": next_path, "hr": None, "finance": right[key]})
                continue
            if key not in right:
                diffs.append({"path": next_path, "hr": left[key], "finance": None})
                continue
            child_diffs = deep_diff(left[key], right[key], next_path)
            if child_diffs:
                # Legacy compaction: keep only the first nested difference per object.
                diffs.append(child_diffs[0])
        return diffs

    if left != right:
        return [{"path": path, "hr": left, "finance": right}]

    return []
