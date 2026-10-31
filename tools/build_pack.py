#!/usr/bin/env python3
"""
Builds dist/<mod>.pack for every mod folder in mods/ (or only the ones given).

  mods/<mod>/db/<table>/<file>.tsv     -> binary DB table (version + pack path from the TSV '#' line)
  mods/<mod>/text/**/<file>.loc.tsv    -> binary .loc
  everything else under mods/<mod>/    -> copied as is (scripts, images, ...)
  files/folders starting with '_' or '.' and README.md are skipped (generators, notes).

Every table/loc is decoded back and re-encoded; the bytes must match exactly.

Usage: python3 tools/build_pack.py [mod ...] [--out dist]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build(mod_dir, name, schema, out_dir):
    files, db_check, loc_check = {}, {}, {}
    for dirpath, dirnames, names in os.walk(mod_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(("_", "."))]
        for n in sorted(names):
            if n.startswith(("_", ".")) or n.lower() == "readme.md":
                continue
            full = os.path.join(dirpath, n)
            rel = os.path.relpath(full, mod_dir).replace(os.sep, "/")
            if rel.startswith("db/") and n.endswith(".tsv"):
                table, version, pack_path, _, rows = packlib.read_tsv(full)
                if pack_path in files:
                    sys.exit("duplicate pack path " + pack_path)
                files[pack_path] = packlib.encode_db(table, version, rows, schema, guid_seed=name)
                db_check[pack_path] = (table, version)
                print("  DB   %-72s v%-2d %4d rows" % (pack_path, version, len(rows)))
            elif n.endswith(".loc.tsv"):
                table, _, pack_path, _, rows = packlib.read_tsv(full)
                if table != "Loc":
                    sys.exit("%s: expected '#Loc;1;...' header" % rel)
                keys = [r["key"] for r in rows]
                dup = sorted({k for k in keys if keys.count(k) > 1})
                if dup:
                    sys.exit("%s: duplicate loc keys %s" % (rel, dup))
                files[pack_path] = packlib.encode_loc(rows)
                loc_check[pack_path] = rows
                print("  LOC  %-72s     %4d rows" % (pack_path, len(rows)))
            else:
                with open(full, "rb") as f:
                    files[rel] = f.read()
                print("  FILE %s" % rel)

    data = packlib.encode_pack(files, timestamp=int(time.time()))

    pack = packlib.decode_pack(data)
    assert pack["type"] == packlib.PACK_TYPE_MOD
    assert pack["files"] == files, "pack round-trip mismatch"
    for p, (table, version) in db_check.items():
        _, v, rows = packlib.decode_db(pack["files"][p], table, schema)
        assert v == version
        again = packlib.encode_db(table, v, rows, schema, guid_seed=name)
        assert again == files[p], "DB re-encode mismatch in " + p
    for p in loc_check:
        rows = packlib.decode_loc(pack["files"][p])
        again = packlib.encode_loc([{"key": r["key"], "text": r["text"].replace("\n", "\\n").replace("\t", "\\t"),
                                     "tooltip": "true" if r["tooltip"] else "false"} for r in rows])
        assert again == files[p], "LOC re-encode mismatch in " + p

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".pack")
    with open(out, "wb") as f:
        f.write(data)
    print("  OK: %s (%d files, %d bytes), round-trip verified\n" % (out, len(files), len(data)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mods", nargs="*")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = ap.parse_args()
    with open(os.path.join(ROOT, "tools", "schema_wh3.json"), encoding="utf-8") as f:
        schema = json.load(f)
    mods_root = os.path.join(ROOT, "mods")
    names = args.mods or sorted(d for d in os.listdir(mods_root) if os.path.isdir(os.path.join(mods_root, d)))
    for name in names:
        print("== " + name)
        build(os.path.join(mods_root, name), name, schema, args.out)


if __name__ == "__main__":
    main()
