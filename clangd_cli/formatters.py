from .uri import uri_to_path
from .constants import SYMBOL_KIND_NAMES


def format_location(loc: dict) -> dict:
    if "targetUri" in loc:
        uri = loc["targetUri"]
        sel = loc.get("targetSelectionRange") or loc["targetRange"]
        return {
            "file": uri_to_path(uri),
            "line": sel["start"]["line"],
            "column": sel["start"]["character"],
        }
    return {
        "file": uri_to_path(loc["uri"]),
        "line": loc["range"]["start"]["line"],
        "column": loc["range"]["start"]["character"],
    }


def normalize_locations(result) -> list:
    if not result:
        return []
    if isinstance(result, list):
        return result
    return [result]


def format_hierarchy_item(item: dict) -> dict:
    kind = SYMBOL_KIND_NAMES.get(item.get("kind", 0), f"Unknown({item.get('kind')})")
    result = {
        "name": item["name"], "kind": kind,
        "location": {
            "file": uri_to_path(item["uri"]),
            "line": item["selectionRange"]["start"]["line"],
            "column": item["selectionRange"]["start"]["character"],
        },
    }
    if item.get("detail"):
        result["detail"] = item["detail"]
    return result


def format_document_symbol(sym: dict) -> dict:
    result = {
        "name": sym["name"],
        "kind": SYMBOL_KIND_NAMES.get(sym.get("kind", 0), f"Unknown({sym.get('kind')})"),
        "line": sym["range"]["start"]["line"],
        "column": sym["range"]["start"]["character"],
        "endLine": sym["range"]["end"]["line"],
        "endColumn": sym["range"]["end"]["character"],
    }
    if sym.get("detail"):
        result["detail"] = sym["detail"]
    if sym.get("selectionRange"):
        sr = sym["selectionRange"]
        result["selectionRange"] = {
            "start": {"line": sr["start"]["line"], "column": sr["start"]["character"]},
            "end": {"line": sr["end"]["line"], "column": sr["end"]["character"]},
        }
    if sym.get("children"):
        result["children"] = [format_document_symbol(c) for c in sym["children"]]
    return result


def format_call_sites(ranges: list) -> list:
    return [{"line": r["start"]["line"], "column": r["start"]["character"]}
            for r in ranges]


def count_symbols(symbols: list) -> int:
    count = len(symbols)
    for sym in symbols:
        if sym.get("children"):
            count += count_symbols(sym["children"])
    return count
