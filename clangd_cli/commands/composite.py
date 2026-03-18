import re
from collections import deque, Counter
from pathlib import Path

from ..uri import uri_to_path, path_to_uri
from ..constants import SYMBOL_KIND_NAMES
from ..formatters import format_hierarchy_item, format_call_sites, format_location, normalize_locations

_CPP_KEYWORDS = frozenset({
    "void", "bool", "char", "short", "int", "long", "float", "double",
    "signed", "unsigned", "auto", "register", "extern", "mutable",
    "static", "const", "volatile", "inline", "explicit", "constexpr",
    "consteval", "constinit", "noexcept", "virtual", "override", "final",
    "class", "struct", "enum", "union", "namespace", "template", "typename",
    "using", "typedef", "decltype", "concept", "requires",
    "public", "private", "protected", "friend",
    "if", "else", "for", "while", "do", "switch", "case", "default",
    "break", "continue", "return", "goto", "throw", "try", "catch",
    "new", "delete", "sizeof", "alignof", "typeid",
    "true", "false", "nullptr", "this",
    "co_await", "co_yield", "co_return",
})

# Symbol kinds: 6=Method, 9=Constructor, 12=Function
_CALLABLE_KINDS = (6, 9, 12)

_IDENT_RE = re.compile(r'\b([A-Za-z_]\w*)\b')
_SCOPE_RE = re.compile(r'(\w+)::(\w+)')


def _find_fallback_columns(file_path, line):
    """Yield candidate column positions on the given line, prioritising ::Name tokens."""
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return
        line_text = lines[line]
    except Exception:
        return

    # Priority 1: tokens immediately after :: (most likely method/function names)
    after_scope = []
    for m in _SCOPE_RE.finditer(line_text):
        col = m.start(2)
        if m.group(2).lower() not in _CPP_KEYWORDS:
            after_scope.append(col)

    # Priority 2: all other identifiers (excluding keywords)
    others = []
    for m in _IDENT_RE.finditer(line_text):
        col = m.start()
        if col not in after_scope and m.group(1).lower() not in _CPP_KEYWORDS:
            others.append(col)

    yield from after_scope
    yield from others


def _prepare_call_hierarchy_with_fallback(session, uri, file_path, line, column, timeout):
    """Try prepareCallHierarchy at the given column, falling back to other tokens on the line."""
    # col 0 typically hits a return type (e.g. 'void') — skip directly to fallback
    if column > 0:
        items = session.client.request("textDocument/prepareCallHierarchy", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        }, timeout=timeout)
        if items:
            if not isinstance(items, list):
                items = [items]
            return items

    for alt_col in _find_fallback_columns(file_path, line):
        if alt_col == column:
            continue
        try:
            items = session.client.request("textDocument/prepareCallHierarchy", {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": alt_col},
            }, timeout=timeout)
        except Exception:
            continue
        if items:
            if not isinstance(items, list):
                items = [items]
            if items[0].get("kind") in _CALLABLE_KINDS:
                return items
    return None


def _explore_virtual_dispatch(session, root_item, uri, files_opened, timeout):
    """Explore virtual dispatch: find base declarations, dispatch callers, and sibling overrides.

    Recursively walks up the inheritance chain via textDocument/definition to find
    all base virtual declarations, then collects callers and implementations from each.
    Handles multi-level and diamond inheritance by tracking visited positions.
    """
    result = {"base_method": None, "dispatch_callers": [], "sibling_overrides": []}

    # Only applies to methods (kind 6)
    if root_item.get("kind") != 6:
        return result

    root_pos = root_item.get("selectionRange", root_item.get("range", {})).get("start", {})
    root_file = uri_to_path(root_item["uri"])
    root_loc = (root_file, root_pos.get("line", -1), root_pos.get("character", -1))

    def _open_file(file_path):
        if file_path not in files_opened:
            session.open_file(file_path)
            files_opened.add(file_path)

    def _loc_key(loc):
        return (loc["file"], loc["line"], loc["column"])

    def _get_implementations(file_uri, line, character):
        """Get all implementations of a virtual method at the given position."""
        try:
            impls = session.client.request("textDocument/implementation", {
                "textDocument": {"uri": file_uri},
                "position": {"line": line, "character": character},
            }, timeout=timeout)
            return normalize_locations(impls)
        except Exception:
            return []

    def _get_dispatch_callers(file_uri, line, character):
        """Get callers of the base virtual method (potential dispatch sites)."""
        try:
            items = session.client.request("textDocument/prepareCallHierarchy", {
                "textDocument": {"uri": file_uri},
                "position": {"line": line, "character": character},
            }, timeout=timeout)
            if not items:
                return []
            if not isinstance(items, list):
                items = [items]
            incoming = session.client.request("callHierarchy/incomingCalls",
                                              {"item": items[0]}, timeout=timeout) or []
            callers = []
            for call in incoming:
                entry = format_hierarchy_item(call["from"])
                entry["call_sites"] = format_call_sites(call.get("fromRanges", []))
                entry["note"] = "Calls base virtual method (potential dispatch site)"
                callers.append(entry)
            return callers
        except Exception:
            return []

    # Walk up the inheritance chain via textDocument/definition
    visited = {root_loc}
    current_uri = uri
    current_line = root_pos.get("line", 0)
    current_char = root_pos.get("character", 0)
    base_method = None

    while True:
        try:
            defn = session.client.request("textDocument/definition", {
                "textDocument": {"uri": current_uri},
                "position": {"line": current_line, "character": current_char},
            }, timeout=timeout)
            defn_locs = normalize_locations(defn)
        except Exception:
            break

        if not defn_locs:
            break

        defn_formatted = format_location(defn_locs[0])
        defn_key = _loc_key(defn_formatted)

        # If definition points to self or already visited, we've reached the top
        if defn_key in visited:
            break

        visited.add(defn_key)
        base_method = defn_formatted

        # Open the base file
        _open_file(defn_formatted["file"])
        current_uri = path_to_uri(defn_formatted["file"])
        current_line = defn_formatted["line"]
        current_char = defn_formatted["column"]

    # Collect dispatch callers and sibling overrides from the highest base found
    if base_method:
        result["base_method"] = base_method
        base_uri = path_to_uri(base_method["file"])

        # Dispatch callers: who calls the base virtual method
        result["dispatch_callers"] = _get_dispatch_callers(
            base_uri, base_method["line"], base_method["column"])

        # Sibling overrides: all implementations of the base method
        impl_locs = _get_implementations(base_uri, base_method["line"], base_method["column"])
        seen_overrides = set()
        for iloc in impl_locs:
            iloc_fmt = format_location(iloc)
            key = _loc_key(iloc_fmt)
            # Skip root itself, the base declaration, and duplicates
            if key == root_loc or key == _loc_key(base_method) or key in seen_overrides:
                continue
            seen_overrides.add(key)
            result["sibling_overrides"].append(iloc_fmt)
    else:
        # Root might be the base itself — look for implementations below
        impl_locs = _get_implementations(uri, root_pos.get("line", 0), root_pos.get("character", 0))
        seen_overrides = set()
        for iloc in impl_locs:
            iloc_fmt = format_location(iloc)
            key = _loc_key(iloc_fmt)
            if key == root_loc or key in seen_overrides:
                continue
            seen_overrides.add(key)
            result["sibling_overrides"].append(iloc_fmt)

    return result


def _node_key(item):
    """Deduplication key from an LSP CallHierarchyItem."""
    uri = item.get("uri", "")
    start = item.get("selectionRange", item.get("range", {})).get("start", {})
    return (uri, start.get("line", -1), start.get("character", -1))


def _format_caller(item, depth, from_ranges):
    entry = format_hierarchy_item(item)
    entry["depth"] = depth
    entry["call_sites"] = format_call_sites(from_ranges)
    return entry


def cmd_impact_analysis(session, args):
    max_depth = getattr(args, "max_depth", 5) or 5
    max_nodes = getattr(args, "max_nodes", 100) or 100
    no_virtual = getattr(args, "no_virtual", False)

    # Phase 1: Prepare root (with column fallback)
    uri = session.open_file(args.file)
    root_items = _prepare_call_hierarchy_with_fallback(
        session, uri, args.file, args.line, args.column, session.timeout)
    if not root_items:
        return {"found": False, "message": "No call hierarchy available at this position"}
    root_item = root_items[0]
    root_formatted = format_hierarchy_item(root_item)

    # Use resolved position (may differ from args if fallback was used)
    root_pos = root_item.get("selectionRange", root_item.get("range", {})).get("start", {})
    resolved_line = root_pos.get("line", args.line)
    resolved_col = root_pos.get("character", args.column)

    # Phase 1b: Callees from root
    callees = []
    if not getattr(args, "no_callees", False):
        try:
            outgoing = session.client.request("callHierarchy/outgoingCalls",
                                              {"item": root_item}, timeout=session.timeout) or []
            for call in outgoing:
                callees.append(format_hierarchy_item(call["to"]))
        except Exception:
            pass

    # Early virtual override detection (before Phases 2-4)
    # When root is a virtual override, clangd's incomingCalls returns callers for
    # ALL overrides in the hierarchy, producing unfilterable noise.
    # Detect this early so we can skip Phases 2-4 and rely on Phase 5's
    # dispatch_callers instead.
    files_opened = {args.file}
    is_virtual_override = False
    virtual_dispatch = {"base_method": None, "dispatch_callers": [], "sibling_overrides": []}
    if not no_virtual:
        try:
            virtual_dispatch = _explore_virtual_dispatch(
                session, root_item, uri, files_opened, session.timeout)
            is_virtual_override = virtual_dispatch.get("base_method") is not None
        except Exception:
            pass

    # Phase 2: find-references for lambda detection (use resolved position)
    # Skip for virtual overrides — references include all overrides' refs (same noise)
    all_refs = []
    ref_locations = set()
    if not is_virtual_override:
        refs_result = session.client.request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": resolved_line, "character": resolved_col},
            "context": {"includeDeclaration": True},
        }, timeout=session.timeout)
        all_refs = normalize_locations(refs_result)
        for ref in all_refs:
            loc = format_location(ref)
            ref_locations.add((loc["file"], loc["line"], loc["column"]))

    # Phase 3: BFS caller traversal
    # Skip for virtual overrides — incomingCalls returns callers across the entire
    # inheritance hierarchy, not just this override. Use dispatch_callers instead.
    visited = {_node_key(root_item)}
    callers = []
    call_hierarchy_locations = set()
    depth_reached = 0
    truncated = False

    if not is_virtual_override:
        frontier = deque()
        frontier.append((root_item, 1))

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
    # Skip for virtual overrides — Phase 2 refs were skipped, nothing to compare
    uncovered = []
    if not is_virtual_override:
        # Root's own definition/declaration are not "uncovered"
        root_file = uri_to_path(root_item["uri"])
        root_line = root_item.get("selectionRange", root_item.get("range", {})).get("start", {}).get("line", -1)

        for file, line, col in ref_locations:
            # Skip the root's own position
            if file == root_file and line == root_line:
                continue
            # Skip if covered by call-hierarchy
            if (file, line, col) in call_hierarchy_locations:
                continue
            uncovered.append({
                "file": file, "line": line, "column": col,
                "note": "Reference not found in call hierarchy (possible lambda/macro)"
            })

    # Phase 5: Virtual dispatch
    # Already computed during early detection — no duplicate work needed.

    result = {
        "found": True,
        "root": root_formatted,
        "callees": callees,
        "callers": callers,
        "uncovered_references": uncovered,
        "virtual_dispatch": virtual_dispatch,
        "stats": {
            "depth_reached": depth_reached,
            "total_callers": len(callers),
            "total_callees": len(callees),
            "total_references": len(all_refs),
            "truncated": truncated,
            "files_opened": len(files_opened),
        }
    }

    if is_virtual_override:
        result["is_virtual_override"] = True

    return result


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
            items = _prepare_call_hierarchy_with_fallback(
                session, uri, args.file, args.line, args.column, session.timeout)
            if items:
                item = items[0]
                result["symbol"] = format_hierarchy_item(item)

                incoming = session.client.request("callHierarchy/incomingCalls",
                                                  {"item": item}, timeout=session.timeout) or []
                callers = []
                for call in incoming:
                    entry = format_hierarchy_item(call["from"])
                    entry["call_sites"] = format_call_sites(call.get("fromRanges", []))
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
