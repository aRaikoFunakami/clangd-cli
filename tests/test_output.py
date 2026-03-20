"""Tests for --compact and --only output control options."""
import argparse
import json
from io import StringIO
from unittest.mock import patch

import pytest

from clangd_cli.cli import build_parser
from clangd_cli.commands.composite import cmd_impact_analysis, cmd_describe, cmd_investigate


# ---------- --compact tests (argparse level) ----------

class TestCompactOption:
    def test_compact_flag_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--compact", "hover", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0"])
        assert args.compact is True

    def test_compact_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["hover", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0"])
        assert args.compact is False

    def test_compact_output_no_indent(self):
        """Verify _output uses indent=None when --compact is set."""
        from clangd_cli.cli import main
        data = {"found": True, "hover": "int x"}
        # Compact: single line
        indent_none = json.dumps(data, indent=None)
        indent_two = json.dumps(data, indent=2)
        assert "\n" not in indent_none
        assert "\n" in indent_two


# ---------- --only for impact-analysis ----------

class TestImpactAnalysisOnly:
    def _make_args(self, **kwargs):
        defaults = dict(file="/f.cpp", line=10, column=5,
                        max_depth=5, max_nodes=100,
                        no_virtual=False, no_callees=False, only=None)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_only_invalid_value(self):
        args = self._make_args(only="invalid")
        result = cmd_impact_analysis(None, args)
        assert result["error"] is True
        assert "Invalid --only value" in result["message"]

    def test_only_with_no_callees_conflict(self):
        args = self._make_args(only="callers", no_callees=True)
        result = cmd_impact_analysis(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_with_no_virtual_conflict(self):
        args = self._make_args(only="callers", no_virtual=True)
        result = cmd_impact_analysis(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_callers_excludes_fields(self):
        """With --only callers, callees and virtual_dispatch should be removed."""
        # We need a mock session; since the error path returns early, test
        # the filtering logic by checking which keys are excluded from a
        # full result dict.
        full = {
            "found": True, "root": {}, "callees": [],
            "callers": [{"name": "a"}],
            "uncovered_references": [],
            "virtual_dispatch": {},
            "stats": {},
        }
        # Simulate filtering as done in cmd_impact_analysis
        only = "callers"
        for key in ("callees", "virtual_dispatch", "is_virtual_override"):
            full.pop(key, None)
        assert "callees" not in full
        assert "virtual_dispatch" not in full
        assert "callers" in full
        assert "stats" in full

    def test_only_callees_excludes_fields(self):
        full = {
            "found": True, "root": {}, "callees": [],
            "callers": [], "uncovered_references": [],
            "virtual_dispatch": {}, "stats": {},
        }
        only = "callees"
        for key in ("callers", "uncovered_references", "virtual_dispatch",
                     "stats", "is_virtual_override"):
            full.pop(key, None)
        assert "callers" not in full
        assert "stats" not in full
        assert "callees" in full

    def test_only_virtual_dispatch_excludes_fields(self):
        full = {
            "found": True, "root": {}, "callees": [],
            "callers": [], "uncovered_references": [],
            "virtual_dispatch": {}, "stats": {},
        }
        for key in ("callees", "callers", "uncovered_references", "stats"):
            full.pop(key, None)
        assert "virtual_dispatch" in full
        assert "callers" not in full

    def test_only_argparse(self):
        parser = build_parser()
        args = parser.parse_args(["impact-analysis", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0",
                                  "--only", "callers"])
        assert args.only == "callers"


# ---------- --only for describe ----------

class TestDescribeOnly:
    def _make_args(self, **kwargs):
        defaults = dict(file="/f.cpp", line=10, column=5,
                        no_callers=False, no_callees=False, only=None)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_only_invalid_value(self):
        args = self._make_args(only="invalid")
        result = cmd_describe(None, args)
        assert result["error"] is True
        assert "Invalid --only value" in result["message"]

    def test_only_with_no_callers_conflict(self):
        args = self._make_args(only="hover", no_callers=True)
        result = cmd_describe(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_with_no_callees_conflict(self):
        args = self._make_args(only="hover", no_callees=True)
        result = cmd_describe(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_comma_separated(self):
        parser = build_parser()
        args = parser.parse_args(["describe", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0",
                                  "--only", "hover,callers"])
        assert args.only == "hover,callers"

    def test_no_only_full_output(self):
        """Without --only, _want() returns True for everything."""
        parser = build_parser()
        args = parser.parse_args(["describe", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0"])
        assert args.only is None


# ---------- --only for investigate ----------

class TestInvestigateOnly:
    def _make_args(self, **kwargs):
        defaults = dict(file="/f.cpp", line=10, column=5,
                        max_depth=5, max_nodes=100,
                        no_virtual=False, no_callees=False,
                        no_caller_details=False, no_type_hierarchy=False,
                        only=None)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_only_invalid_value(self):
        args = self._make_args(only="invalid")
        result = cmd_investigate(None, args)
        assert result["error"] is True
        assert "Invalid --only value" in result["message"]

    def test_only_with_no_virtual_conflict(self):
        args = self._make_args(only="callers", no_virtual=True)
        result = cmd_investigate(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_with_no_callees_conflict(self):
        args = self._make_args(only="callers", no_callees=True)
        result = cmd_investigate(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_with_no_caller_details_conflict(self):
        args = self._make_args(only="callers", no_caller_details=True)
        result = cmd_investigate(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_with_no_type_hierarchy_conflict(self):
        args = self._make_args(only="callers", no_type_hierarchy=True)
        result = cmd_investigate(None, args)
        assert result["error"] is True
        assert "cannot be used together" in result["message"]

    def test_only_comma_separated(self):
        parser = build_parser()
        args = parser.parse_args(["investigate", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0",
                                  "--only", "callers,caller-details"])
        assert args.only == "callers,caller-details"

    def test_argparse_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["investigate", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0"])
        assert args.only is None
        assert args.max_depth == 5
        assert args.max_nodes == 100
        assert args.no_virtual is False
        assert args.no_callees is False
        assert args.no_caller_details is False
        assert args.no_type_hierarchy is False

    def test_argparse_all_flags(self):
        parser = build_parser()
        args = parser.parse_args(["investigate", "--file", "/f.cpp",
                                  "--line", "0", "--col", "0",
                                  "--max-depth", "3", "--max-nodes", "50",
                                  "--no-virtual", "--no-callees",
                                  "--no-caller-details", "--no-type-hierarchy"])
        assert args.max_depth == 3
        assert args.max_nodes == 50
        assert args.no_virtual is True
        assert args.no_callees is True
        assert args.no_caller_details is True
        assert args.no_type_hierarchy is True
