from ..formatters import format_location, normalize_locations


def cmd_goto_definition(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/definition", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    locations = normalize_locations(result)
    if not locations:
        return {"found": False, "message": "No definition found"}
    return {
        "found": True, "count": len(locations),
        "locations": [format_location(loc) for loc in locations],
    }


def cmd_goto_declaration(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/declaration", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    locations = normalize_locations(result)
    if not locations:
        return {"found": False, "message": "No declaration found"}
    return {
        "found": True, "count": len(locations),
        "locations": [format_location(loc) for loc in locations],
    }


def cmd_goto_implementation(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/implementation", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    locations = normalize_locations(result)
    if not locations:
        return {"found": False, "message": "No implementations found"}
    return {
        "found": True, "count": len(locations),
        "locations": [format_location(loc) for loc in locations],
    }


def cmd_goto_type_definition(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/typeDefinition", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
    }, timeout=session.timeout)
    locations = normalize_locations(result)
    if not locations:
        return {"found": False, "message": "No type definition found"}
    return {
        "found": True, "count": len(locations),
        "locations": [format_location(loc) for loc in locations],
    }


def cmd_find_references(session, args):
    uri = session.open_file(args.file)
    include_decl = not getattr(args, "no_declaration", False)
    result = session.client.request("textDocument/references", {
        "textDocument": {"uri": uri},
        "position": {"line": args.line, "character": args.column},
        "context": {"includeDeclaration": include_decl},
    }, timeout=session.timeout)
    locations = result or []
    if not locations:
        return {"found": False, "message": "No references found"}
    return {
        "found": True, "count": len(locations),
        "locations": [format_location(loc) for loc in locations],
    }


def cmd_switch_header_source(session, args):
    uri = session.open_file(args.file)
    result = session.client.request("textDocument/switchSourceHeader", {
        "uri": uri,
    }, timeout=session.timeout)
    if not result:
        return {"found": False, "message": "No corresponding header/source found"}
    from ..uri import uri_to_path
    return {"found": True, "file": uri_to_path(result)}
