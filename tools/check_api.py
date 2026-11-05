#!/usr/bin/env python3
"""
Checks that every game function, event and method used by mods/*/script/**/*.lua is documented in
CA's official scripting docs (names in tools/wh3_api_names.json, built by extract_api.py).
Runs in CI without any game files. Exit code 1 on unknown names.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# script-library globals and our own helpers that are not engine API
ALLOW_METHODS = {"add_choice_payload", "add_effect", "set_duration", "effect_bundle_to_faction",
                 "faction_pooled_resource_transaction", "gmatch", "concat", "insert", "remove", "format"}


def main():
    api = json.load(open(os.path.join(ROOT, "tools", "wh3_api_names.json"), encoding="utf-8"))
    cm, core, events = set(api["cm"]), set(api["core"]), set(api["events"])
    methods, ui = set(api["methods"]) | set(api.get("lib_methods", [])), set(api["ui_methods"])
    errors = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "mods", "*", "script", "**", "*.lua"), recursive=True)):
        src = open(f, encoding="utf-8").read()
        src = re.sub(r"--\[\[.*?\]\]", "", src, flags=re.S)
        src = re.sub(r"--[^\n]*", "", src)
        src = re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: m.group(0) if re.fullmatch(r'"[A-Za-z]+"', m.group(0)) else '""', src)
        rel = os.path.relpath(f, ROOT)
        own = set(re.findall(r"function\s+[\w.]+[:.](\w+)\s*\(", src)) | set(re.findall(r"local function (\w+)", src))
        def bad(kind, name):
            nonlocal errors
            errors += 1
            print("ERROR %s: %s '%s' is not in CA's scripting documentation" % (rel, kind, name))
        for n in set(re.findall(r"\bcm:([A-Za-z_][A-Za-z0-9_]*)\(", src)) - cm:
            bad("cm function", n)
        for n in set(re.findall(r"\bcore:([A-Za-z_][A-Za-z0-9_]*)\(", src)) - core:
            bad("core function", n)
        for n in set(re.findall(r'add_listener\(\s*[^,]+,\s*"([A-Za-z]+)"', src)) - events:
            bad("event", n)
        objs = set(re.findall(r"[\w\)\]]:([a-z_][A-Za-z0-9_]*)\(", src)) - set(re.findall(r"\b(?:cm|core):([A-Za-z_][A-Za-z0-9_]*)\(", src))
        for n in objs - methods - ALLOW_METHODS - own:
            bad("method", n)
        for n in set(re.findall(r"[\w\)\]]:([A-Z][A-Za-z]+)\(", src)) - ui:
            bad("UI component method", n)
    print("api check: %d errors" % errors)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
