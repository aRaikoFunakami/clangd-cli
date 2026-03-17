from ..uri import uri_to_path
from ..constants import INLAY_HINT_KIND_NAMES


def cmd_hover(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/hover", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    if not result:
        return {"found": False, "message": "No hover information available"}
    contents = result.get("contents", {})
    kind = None
    if isinstance(contents, dict):
        text = contents.get("value", "")
        kind = contents.get("kind")
    elif isinstance(contents, str):
        text = contents
    elif isinstance(contents, list):
        text = "\n".join(
            c.get("value", c) if isinstance(c, dict) else str(c)
            for c in contents
        )
    else:
        text = str(contents)
    response = {"found": True, "content": text}
    if kind:
        response["contentKind"] = kind
    if result.get("range"):
        r = result["range"]
        response["range"] = {
            "start": {"line": r["start"]["line"], "column": r["start"]["character"]},
            "end": {"line": r["end"]["line"], "column": r["end"]["character"]},
        }
    return response


def cmd_diagnostics(session, args):
    uri = session.open_file(args.file)
    raw_diagnostics = session.diagnostics.get(uri, timeout=5.0)

    severity_names = {1: "Error", 2: "Warning", 3: "Information", 4: "Hint"}
    formatted = []
    for diag in raw_diagnostics:
        entry = {
            "severity": severity_names.get(diag.get("severity", 1), "Unknown"),
            "line": diag["range"]["start"]["line"],
            "column": diag["range"]["start"]["character"],
            "endLine": diag["range"]["end"]["line"],
            "endColumn": diag["range"]["end"]["character"],
            "message": diag.get("message", ""),
        }
        if diag.get("code"):
            entry["code"] = diag["code"]
        if diag.get("source"):
            entry["source"] = diag["source"]
        if diag.get("relatedInformation"):
            entry["relatedInformation"] = [
                {
                    "location": {
                        "file": uri_to_path(info["location"]["uri"]),
                        "line": info["location"]["range"]["start"]["line"],
                        "column": info["location"]["range"]["start"]["character"],
                    },
                    "message": info.get("message", ""),
                }
                for info in diag["relatedInformation"]
            ]
        formatted.append(entry)

    if not formatted:
        return {"found": False, "message": "No diagnostics found"}
    return {"found": True, "count": len(formatted), "diagnostics": formatted}


def _parse_range(range_str, default_start=0, default_end=99999):
    """Parse 'START:END' range string into (start_line, end_line)."""
    if not range_str:
        return default_start, default_end
    parts = range_str.split(":")
    start = int(parts[0]) if parts[0] else default_start
    end = int(parts[1]) if len(parts) > 1 and parts[1] else default_end
    return start, end


def cmd_inlay_hints(session, args):
    uri = session.open_file(args.file)
    start, end = _parse_range(getattr(args, "range", None))
    result = session.client.request("textDocument/inlayHint", {
        "textDocument": {"uri": uri},
        "range": {
            "start": {"line": start, "character": 0},
            "end": {"line": end, "character": 0},
        },
    }, timeout=session.timeout)
    hints = result or []
    if not hints:
        return {"found": False, "message": "No inlay hints found"}
    formatted = []
    for hint in hints:
        label = hint.get("label", "")
        if isinstance(label, list):
            label = "".join(part.get("value", "") for part in label)
        entry = {
            "line": hint["position"]["line"],
            "column": hint["position"]["character"],
            "label": label,
        }
        if hint.get("kind"):
            entry["kind"] = INLAY_HINT_KIND_NAMES.get(hint["kind"], f"Unknown({hint['kind']})")
        if hint.get("paddingLeft"):
            entry["paddingLeft"] = True
        if hint.get("paddingRight"):
            entry["paddingRight"] = True
        formatted.append(entry)
    return {"found": True, "count": len(formatted), "hints": formatted}


def cmd_semantic_tokens(session, args):
    uri = session.open_file(args.file)
    range_str = getattr(args, "range", None)
    filter_start, filter_end = _parse_range(range_str) if range_str else (None, None)

    # Always use full — semanticTokens/range not supported by all clangd versions
    result = session.client.request("textDocument/semanticTokens/full",
                                    {"textDocument": {"uri": uri}},
                                    timeout=session.timeout)
    if not result or not result.get("data"):
        return {"found": False, "message": "No semantic tokens found"}

    data = result["data"]
    tokens = []
    line, col = 0, 0
    for i in range(0, len(data), 5):
        delta_line = data[i]
        delta_start = data[i + 1]
        length = data[i + 2]
        token_type = data[i + 3]
        token_modifiers = data[i + 4]
        if delta_line > 0:
            line += delta_line
            col = delta_start
        else:
            col += delta_start
        if filter_start is not None and (line < filter_start or line > filter_end):
            continue
        tokens.append({
            "line": line, "column": col, "length": length,
            "type": token_type, "modifiers": token_modifiers,
        })
    return {"found": True, "count": len(tokens), "tokens": tokens}


def cmd_ast(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/ast", {
        "textDocument": {"uri": uri},
        "range": {
            "start": {"line": args.line, "character": args.column},
            "end": {"line": args.line, "character": args.column},
        },
    }, timeout=session.timeout)
    if not result:
        return {"found": False, "message": "No AST node found at this position"}
    depth = getattr(args, "depth", None)
    return {"found": True, "node": _format_ast_node(result, depth, 0)}


def _format_ast_node(node, max_depth, current_depth):
    result = {}
    if node.get("role"):
        result["role"] = node["role"]
    if node.get("kind"):
        result["kind"] = node["kind"]
    if node.get("detail"):
        result["detail"] = node["detail"]
    if node.get("arcana"):
        result["arcana"] = node["arcana"]
    if node.get("range"):
        r = node["range"]
        result["range"] = {
            "start": {"line": r["start"]["line"], "column": r["start"]["character"]},
            "end": {"line": r["end"]["line"], "column": r["end"]["character"]},
        }
    if node.get("children"):
        if max_depth is not None and current_depth >= max_depth:
            result["children_count"] = len(node["children"])
        else:
            result["children"] = [
                _format_ast_node(c, max_depth, current_depth + 1)
                for c in node["children"]
            ]
    return result
