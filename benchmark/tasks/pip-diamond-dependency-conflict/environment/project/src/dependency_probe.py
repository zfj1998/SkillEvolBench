from importlib.metadata import version


def snapshot_runtime_dependencies() -> dict:
    return {
        "package_alpha": version("package-alpha"),
        "package_beta": version("package-beta"),
        "package_core": version("package-core"),
        "package_data": version("package-data"),
    }
