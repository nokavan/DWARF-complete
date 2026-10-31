#!/usr/bin/env python3
"""
Builds dist/<name>.pack from the mod/ folder.

  mod/db/<table>/<file>.tsv        -> binary DB table (path taken from the TSV's '#' line)
  mod/text/**/<file>.loc.tsv       -> binary .loc
  everything else under mod/       -> copied as is (scripts, images, ...)

Then re-reads the pack and checks every table/loc round-trips to the TSV data.

Usage: python3 tools/build_pack.py [--name dwf_ancient_lineages] [--out dist]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="dwf_ancient_lineages")
    ap.add_argument("--src", default=os.path.join(ROOT, "mod"))
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = ap.parse_args()

    with open(os.path.join(ROOT, "tools", "schema_wh3_subset.json"), encoding="utf-8") as f:
        schema = json.load(f)

    files = {}
    expected_db = {}
    expected_loc = {}

    for dirpath, _, names in os.walk(args.src):
        for n in sorted(names):
            full = os.path.join(dirpath, n)
            rel = os.path.relpath(full, args.src).replace(os.sep, "/")
            if n.startswith(".") or n.lower() == "readme.md":
                continue
            if rel.startswith("db/") and n.endswith(".tsv"):
                table, version, pack_path, _, rows = packlib.read_tsv(full)
                if table not in schema:
                    sys.exit("No schema for table %s (add it to tools/schema_wh3_subset.json)" % table)
                files[pack_path] = packlib.encode_db(table, version, rows, schema)
                expected_db[pack_path] = (table, rows)
                print("DB   %-70s %3d rows" % (pack_path, len(rows)))
            elif n.endswith(".loc.tsv"):
                table, _, pack_path, _, rows = packlib.read_tsv(full)
                if table != "Loc":
                    sys.exit("%s: expected '#Loc;1;...' header" % rel)
                keys = [r["key"] for r in rows]
                dup = {k for k in keys if keys.count(k) > 1}
                if dup:
                    sys.exit("%s: duplicate loc keys %s" % (rel, sorted(dup)))
                files[pack_path] = packlib.encode_loc(rows)
                expected_loc[pack_path] = rows
                print("LOC  %-70s %3d rows" % (pack_path, len(rows)))
            else:
                with open(full, "rb") as f:
                    files[rel] = f.read()
                print("FILE %s" % rel)

    data = packlib.encode_pack(files, timestamp=int(time.time()))

    # ---- verify by reading everything back
    pack = packlib.decode_pack(data)
    assert pack["type"] == packlib.PACK_TYPE_MOD
    assert set(pack["files"]) == set(files), "file list mismatch"
    for p, (table, rows) in expected_db.items():
        _, _, got = packlib.decode_db(pack["files"][p], table, schema)
        want = [{k: (str(packlib.parse_bool(r[k])).lower() if ft == "Boolean" else (str(int(r[k] or 0)) if ft == "I32" else r[k]))
                 for k, ft in schema[table]["fields"]} for r in rows]
        assert got == want, "round-trip mismatch in %s" % p
    for p, rows in expected_loc.items():
        got = packlib.decode_loc(pack["files"][p])
        assert [g["key"] for g in got] == [r["key"] for r in rows], "loc mismatch in %s" % p

    os.makedirs(args.out, exist_ok=True)
    out = os.path.join(args.out, args.name + ".pack")
    with open(out, "wb") as f:
        f.write(data)
    print("\nOK: %s (%d files, %d bytes), round-trip verified" % (out, len(files), len(data)))


if __name__ == "__main__":
    main()
