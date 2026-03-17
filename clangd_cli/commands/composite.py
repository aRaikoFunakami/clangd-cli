from collections import deque, Counter

from ..uri import uri_to_path
from ..constants import SYMBOL_KIND_NAMES
from ..formatters import format_hierarchy_item, format_location, normalize_locations


def _node_key(item):
    """Deduplication key from an LSP CallHierarchyItem."""
    uri = item.get("uri", "")
    start = item.get("selectionRange", item.get("range", {})).get("start", {})
    return (uri, start.get("line", -1), start.get("character", -1))


def _format_caller(item, depth, from_ranges):
    entry = format_hierarchy_item(item)
    entry["depth"] = depth
    entry["call_sites"] = [
        {"line": r["start"]["line"], "column": r["start"]["character"]}
        for r in from_ranges
    ]
    return entry


def cmd_impact_analysis(session, args):
    max_depth = getattr(args, "max_depth", 5) or 5
    max_nodes = getattr(args, "max_nodes", 100) or 100
    include_virtual = getattr(args, "include_virtual", False)

    # Phase 1: Prepare root
    uri = session.open_file(args.file)
    root_items = session.client.request("textDocument/prepareCallHierarchy", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    if not root_items:
        return {"found": False, "message": "No call hierarchy available at this position"}
    if not isinstance(root_items, list):
        root_items = [root_items]
    root_item = root_items[0]
    root_formatted = format_hierarchy_item(root_item)

    # Phase 2: find-references for lambda detection
    refs_result = session.client.request("textDocument/references", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
        "context": {"includeDeclaration": True},
    }, timeout=session.timeout)
    all_refs = normalize_locations(refs_result)
    ref_locations = set()
    for ref in all_refs:
        loc = format_location(ref)
        ref_locations.add((loc["file"], loc["line"], loc["column"]))

    # Phase 3: BFS
    visited = {_node_key(root_item)}
    frontier = deque()
    frontier.append((root_item, 1))
    callers = []
    call_hierarchy_locations = set()
    files_opened = {args.file}
    depth_reached = 0
    truncated = False

    while frontier and len(callers) < max_nodes:
        current_item, depth = frontier.popleft()
        if depth > max_depth:
            truncated = True
            continue
        depth_reached = max(depth_reached, depth)

        # Open file for this node if needed
        node_file = uri_to_path(current_item["uri"])
        if node_file not in files_opened:
            session.open_file(node_file)
            files_opened.add(node_file)

        # Get incoming calls
        try:
            # Prepare at this node's position
            node_pos = current_item.get("selectionRange", current_item.get("range", {})).get("start", {})
            prepare_items = session.client.request("textDocument/prepareCallHierarchy", {
                "textDocument": {"uri": current_item["uri"]},
                "position": {"line": node_pos.get("line", 0), "character": node_pos.get("character", 0)},
            }, timeout=session.timeout)
            if not prepare_items:
                continue
            if not isinstance(prepare_items, list):
                prepare_items = [prepare_items]
            prepared = prepare_items[0]

            incoming = session.client.request("callHierarchy/incomingCalls",
                                              {"item": prepared}, timeout=session.timeout) or []
        except Exception:
            continue

        for call in incoming:
            caller_item = call["from"]
            key = _node_key(caller_item)
            from_ranges = call.get("fromRanges", [])

            # Record call sites as covered by call-hierarchy
            caller_file = uri_to_path(caller_item["uri"])
            for r in from_ranges:
                call_hierarchy_locations.add(
                    (caller_file, r["start"]["line"], r["start"]["character"])
                )

            if key in visited:
                continue
            visited.add(key)

            entry = _format_caller(caller_item, depth, from_ranges)
            callers.append(entry)

            if len(callers) >= max_nodes:
                truncated = True
                break

            if depth < max_depth:
                frontier.append((caller_item, depth + 1))

    # Phase 4: Detect uncovered references (lambda, macro, etc.)
    # Root's own definition/declaration are not "uncovered"
    root_file = uri_to_path(root_item["uri"])
    root_line = root_item.get("selectionRange", root_item.get("range", {})).get("start", {}).get("line", -1)

    uncovered = []
    for file, line, col in ref_locations:
        # Skip the root's own position
        if file == root_file and line == root_line:
            continue
        # Skip if covered by call-hierarchy
        if (file, line, col) in call_hierarchy_locations:
            continue
        # Skip declaration in header (same name, line matches declaration)
        uncovered.append({
            "file": file, "line": line, "column": col,
            "note": "Reference not found in call hierarchy (possible lambda/macro)"
        })

    # Phase 5: Virtual dispatch (optional)
    virtual_implementations = []
    if include_virtual:
        try:
            type_items = session.client.request("textDocument/prepareTypeHierarchy", {
                "textDocument": {"uri": uri},
                "position": {"line": args.line, "character": args.column},
            }, timeout=session.timeout)
            if type_items:
                if not isinstance(type_items, list):
                    type_items = [type_items]
                subtypes = session.client.request("typeHierarchy/subtypes",
                                                  {"item": type_items[0]},
                                                  timeout=session.timeout) or []
                virtual_implementations = [format_hierarchy_item(s) for s in subtypes]
        except Exception:
            pass

    return {
        "found": True,
        "root": root_formatted,
        "callers": callers,
        "uncovered_references": uncovered,
        "virtual_implementations": virtual_implementations,
        "stats": {
            "depth_reached": depth_reached,
            "total_callers": len(callers),
            "total_references": len(all_refs),
            "truncated": truncated,
            "files_opened": len(files_opened),
        }
    }


def cmd_describe(session, args):
    uri = session.open_file(args.file)
    no_callers = getattr(args, "no_callers", False)
    no_callees = getattr(args, "no_callees", False)
    result = {}

    # Hover
    try:
        hover = session.client.request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": args.line, "character": args.column},
        }, timeout=session.timeout)
        if hover and hover.get("contents"):
            contents = hover["contents"]
            if isinstance(contents, dict):
                result["hover"] = contents.get("value", str(contents))
            elif isinstance(contents, str):
                result["hover"] = contents
            elif isinstance(contents, list):
                result["hover"] = "\n".join(
                    c.get("value", str(c)) if isinstance(c, dict) else str(c)
                    for c in contents
                )
    except Exception:
        pass

    # Definition
    try:
        defn = session.client.request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": args.line, "character": args.column},
        }, timeout=session.timeout)
        locs = normalize_locations(defn)
        if locs:
            result["definition"] = format_location(locs[0])
    except Exception:
        pass

    # References
    try:
        refs = session.client.request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": args.line, "character": args.column},
            "context": {"includeDeclaration": True},
        }, timeout=session.timeout)
        ref_locs = normalize_locations(refs)
        if ref_locs:
            by_file = Counter()
            for ref in ref_locs:
                loc = format_location(ref)
                by_file[loc["file"]] += 1
            result["references"] = {
                "total": len(ref_locs),
                "by_file": dict(by_file),
            }
    except Exception:
        pass

    # Call hierarchy - callers (1 level)
    if not no_callers:
        try:
            items = session.client.request("textDocument/prepareCallHierarchy", {
                "textDocument": {"uri": uri},
                "position": {"line": args.line, "character": args.column},
            }, timeout=session.timeout)
            if items:
                if not isinstance(items, list):
                    items = [items]
                item = items[0]
                result["symbol"] = format_hierarchy_item(item)

                incoming = session.client.request("callHierarchy/incomingCalls",
                                                  {"item": item}, timeout=session.timeout) or []
                callers = []
                for call in incoming:
                    entry = format_hierarchy_item(call["from"])
                    entry["call_sites"] = [
                        {"line": r["start"]["line"], "column": r["start"]["character"]}
                        for r in call.get("fromRanges", [])
                    ]
                    callers.append(entry)
                result["callers"] = callers

                # Callees (1 level)
                if not no_callees:
                    outgoing = session.client.request("callHierarchy/outgoingCalls",
                                                      {"item": item}, timeout=session.timeout) or []
                    callees = []
                    for call in outgoing:
                        entry = format_hierarchy_item(call["to"])
                        callees.append(entry)
                    result["callees"] = callees
        except Exception:
            pass

    if not result:
        return {"found": False, "message": "No information available at this position"}

    result["found"] = True
    return result
