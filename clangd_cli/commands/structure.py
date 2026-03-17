from ..uri import uri_to_path
from ..constants import HIGHLIGHT_KIND_NAMES


def cmd_highlight_symbol(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/documentHighlight", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    highlights = result or []
    if not highlights:
        return {"found": False, "message": "No highlights found"}
    formatted = []
    for hl in highlights:
        entry = {
            "line": hl["range"]["start"]["line"],
            "column": hl["range"]["start"]["character"],
            "endLine": hl["range"]["end"]["line"],
            "endColumn": hl["range"]["end"]["character"],
        }
        if hl.get("kind"):
            entry["kind"] = HIGHLIGHT_KIND_NAMES.get(hl["kind"], f"Unknown({hl['kind']})")
        formatted.append(entry)
    return {"found": True, "count": len(formatted), "highlights": formatted}


def cmd_document_links(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/documentLink", {
        "textDocument": {"uri": uri},
    }, timeout=session.timeout)
    links = result or []
    if not links:
        return {"found": False, "message": "No document links found"}
    formatted = []
    for link in links:
        entry = {
            "line": link["range"]["start"]["line"],
            "column": link["range"]["start"]["character"],
            "endLine": link["range"]["end"]["line"],
            "endColumn": link["range"]["end"]["character"],
        }
        if link.get("target"):
            entry["target"] = uri_to_path(link["target"])
        formatted.append(entry)
    return {"found": True, "count": len(formatted), "links": formatted}
