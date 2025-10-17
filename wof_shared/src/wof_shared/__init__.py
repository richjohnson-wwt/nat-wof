from importlib import resources as _resources

__all__ = [
    "data_path",
]

def data_path(filename: str) -> str:
    """Return a filesystem path to a packaged asset (e.g., assets/wheel.txt).

    Use for compatibility where APIs want a file path; for direct reads prefer
    importlib.resources.files(...).joinpath(...).read_text().
    """
    f = _resources.files("wof_shared.assets").joinpath(filename)
    return str(f)
