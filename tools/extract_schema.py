#!/usr/bin/env python3
"""
Extracts table definitions (ALL versions) from RPFM's schema_wh3.ron into tools/schema_wh3.json.

  curl -sSLO https://raw.githubusercontent.com/Frodo45127/rpfm-schemas/master/schema_wh3.ron
  python3 tools/extract_schema.py schema_wh3.ron

Only tables used by mods under mods/ (found from their db/<table>/ folders) plus EXTRA are kept.
Note: a higher version number is NOT necessarily the current one for the live game; each TSV
states the version it was written for (taken from real, working packs where possible).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA = []


def used_tables():
    out = set(EXTRA)
    mods = os.path.join(ROOT, "mods")
    for m in os.listdir(mods):
        db = os.path.join(mods, m, "db")
        if os.path.isdir(db):
            out.update(os.listdir(db))
    return out


def main():
    s = open(sys.argv[1], encoding="utf-8").read()
    want = used_tables()
    result = {}
    for m in re.finditer(r'\n        "([a-z0-9_]+_tables)": \[', s):
        t = m.group(1)
        if t not in want or t in result:
            continue
        j = m.end() - 1
        depth = 0
        for k in range(j, len(s)):
            if s[k] == "[":
                depth += 1
            elif s[k] == "]":
                depth -= 1
                if depth == 0:
                    break
        defs = {}
        for dm in re.finditer(r"\(\s*version:\s*(\d+),\s*fields:\s*\[(.*?)\],\s*localised_fields", s[j:k], re.S):
            fields = re.findall(r'\(\s*name:\s*"([^"]+)",\s*field_type:\s*(\w+)', dm.group(2))
            defs.setdefault(dm.group(1), fields)
        result[t] = defs
    missing = want - set(result)
    if missing:
        sys.exit("tables not found in schema: %s" % sorted(missing))
    with open(os.path.join(ROOT, "tools", "schema_wh3.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=0, sort_keys=True)
    print("wrote %d tables" % len(result))


if __name__ == "__main__":
    main()
