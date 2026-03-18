from ..uri import uri_to_path
from ..constants import SYMBOL_KIND_NAMES
from ..formatters import format_hierarchy_item, format_document_symbol, count_symbols


def cmd_file_symbols(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/documentSymbol", {
        "textDocument": {"uri": uri},
    }, timeout=session.timeout)
    symbols = result or []
    if not symbols:
        return {"found": False, "message": "No symbols found in document"}
    return {
        "found": True, "count": count_symbols(symbols),
        "symbols": [format_document_symbol(s) for s in symbols],
    }


def cmd_workspace_symbols(session, args):
    limit = getattr(args, "limit", 100) or 100
    result = session.client.request("workspace/symbol", {
        "query": args.query,
    }, timeout=session.timeout)
    symbols = result or []
    if not symbols:
        return {"found": False, "message": f"No symbols found matching '{args.query}'"}
    limited = symbols[:limit]
    formatted = []
    for sym in limited:
        formatted.append({
            "name": sym["name"],
            "kind": SYMBOL_KIND_NAMES.get(sym.get("kind", 0), f"Unknown({sym.get('kind')})"),
            "file": uri_to_path(sym["location"]["uri"]),
            "line": sym["location"]["range"]["start"]["line"],
            "column": sym["location"]["range"]["start"]["character"],
            "container": sym.get("containerName"),
        })
    return {
        "found": True, "count": len(symbols),
        "returned": len(formatted), "truncated": len(symbols) > limit,
        "symbols": formatted,
    }


def _prepare_hierarchy(session, args, method: str):
    uri = session.open_file(args.file)
    items = session.client.request(method, {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    if not items:
        return None, None
    if not isinstance(items, list):
        items = [items]
    all_items = [format_hierarchy_item(i) for i in items] if len(items) > 1 else None
    return items[0], all_items


def _prepare_call_hierarchy(session, args):
    return _prepare_hierarchy(session, args, "textDocument/prepareCallHierarchy")


def cmd_call_hierarchy_in(session, args):
    item, all_symbols = _prepare_call_hierarchy(session, args)
    if item is None:
        return {"found": False, "message": "No call hierarchy available at this position"}

    incoming = session.client.request("callHierarchy/incomingCalls",
                                      {"item": item}, timeout=session.timeout) or []
    fmt_in = []
    for call in incoming:
        entry = format_hierarchy_item(call["from"])
        entry["caller"] = entry.pop("name")
        entry["call_sites"] = [
            {"line": r["start"]["line"], "column": r["start"]["character"]}
            for r in call.get("fromRanges", [])
        ]
        fmt_in.append(entry)

    result = {
        "found": True, "symbol": format_hierarchy_item(item),
        "incoming_calls": fmt_in, "incoming_count": len(fmt_in),
    }
    if all_symbols:
        result["all_symbols"] = all_symbols
    return result


def cmd_call_hierarchy_out(session, args):
    item, all_symbols = _prepare_call_hierarchy(session, args)
    if item is None:
        return {"found": False, "message": "No call hierarchy available at this position"}

    outgoing = session.client.request("callHierarchy/outgoingCalls",
                                      {"item": item}, timeout=session.timeout) or []
    fmt_out = []
    for call in outgoing:
        entry = format_hierarchy_item(call["to"])
        entry["callee"] = entry.pop("name")
        entry["call_sites"] = [
            {"line": r["start"]["line"], "column": r["start"]["character"]}
            for r in call.get("fromRanges", [])
        ]
        fmt_out.append(entry)

    result = {
        "found": True, "symbol": format_hierarchy_item(item),
        "outgoing_calls": fmt_out, "outgoing_count": len(fmt_out),
    }
    if all_symbols:
        result["all_symbols"] = all_symbols
    return result


def _prepare_type_hierarchy(session, args):
    return _prepare_hierarchy(session, args, "textDocument/prepareTypeHierarchy")


def cmd_type_hierarchy_super(session, args):
    item, all_types = _prepare_type_hierarchy(session, args)
    if item is None:
        return {"found": False, "message": "No type hierarchy available at this position"}

    supertypes = session.client.request("typeHierarchy/supertypes",
                                        {"item": item}, timeout=session.timeout) or []
    result = {
        "found": True, "type": format_hierarchy_item(item),
        "supertypes": [format_hierarchy_item(s) for s in supertypes],
        "supertypes_count": len(supertypes),
    }
    if all_types:
        result["all_types"] = all_types
    return result


def cmd_type_hierarchy_sub(session, args):
    item, all_types = _prepare_type_hierarchy(session, args)
    if item is None:
        return {"found": False, "message": "No type hierarchy available at this position"}

    subtypes = session.client.request("typeHierarchy/subtypes",
                                      {"item": item}, timeout=session.timeout) or []
    result = {
        "found": True, "type": format_hierarchy_item(item),
        "subtypes": [format_hierarchy_item(s) for s in subtypes],
        "subtypes_count": len(subtypes),
    }
    if all_types:
        result["all_types"] = all_types
    return result
