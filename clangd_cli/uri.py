from pathlib import Path
from urllib.parse import unquote, urlparse


def path_to_uri(path: str) -> str:
    return Path(path).resolve().as_uri()


def uri_to_path(uri: str) -> str:
    return unquote(urlparse(uri).path)


def get_language_id(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".c":
        return "c"
    if ext in (".m",):
        return "objective-c"
    if ext in (".mm",):
        return "objective-cpp"
    return "cpp"
