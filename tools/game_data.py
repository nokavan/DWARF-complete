#!/usr/bin/env python3
"""
Work with original game packs uploaded to the private release "game-data".

  python3 tools/game_data.py download --cache DIR
        downloads every asset of the "game-data" release into DIR (skips files already there)
  python3 tools/game_data.py list   PACK [--prefix db/]
        lists files inside a pack
  python3 tools/game_data.py dump   PACK --schema schema_wh3.ron --out DIR TABLE [TABLE ...]
        writes RPFM-style TSVs (all files of each table) into DIR
  python3 tools/game_data.py find   PACK --schema schema_wh3.ron TEXT [--tables PREFIX]
        prints every DB row that contains TEXT (e.g. a faction key)
  python3 tools/game_data.py loc    PACK TEXT
        prints loc entries whose key or text contains TEXT

Packs are read lazily (index + seek), so multi-GB packs are fine.
Game files are copyrighted: keep them in the PRIVATE release only, never commit them.
"""
import argparse
import json
import os
import pickle
import re
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packlib  # noqa: E402

REPO = "nokavan/dwarf-complete"
TAG = "game-data"


# ------------------------------------------------------------------ pack index (all PFH4/5 flags)
class Pack:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        h = self.f.read(28)
        self.preamble = h[:4]
        if self.preamble not in (b"PFH4", b"PFH5", b"PFH6"):
            raise ValueError("%s: unsupported pack %r" % (path, self.preamble))
        flags, dep_count, dep_len, file_count, index_len = struct.unpack_from("<5I", h, 4)
        self.flags = flags
        pos = 28
        if flags & 0x100:
            pos += 20
        if self.preamble == b"PFH6":
            pos += 284
        self.f.seek(pos)
        dep_idx = self.f.read(dep_len)
        idx = self.f.read(index_len)
        if flags & 0x80:
            raise ValueError("encrypted index is not supported")
        p = 0
        self.entries = []
        for _ in range(file_count):
            size = struct.unpack_from("<I", idx, p)[0]
            p += 4
            if flags & 0x40:
                p += 4
            compressed = False
            if self.preamble in (b"PFH5", b"PFH6"):
                compressed = idx[p] == 1
                p += 1
            end = idx.index(b"\0", p)
            name = idx[p:end].decode("utf-8", "replace").replace("\\", "/")
            p = end + 1
            self.entries.append([name, size, compressed, 0])
        off = pos + dep_len + index_len
        for e in self.entries:
            e[3] = off
            off += e[1]
        self.by_name = {e[0].lower(): e for e in self.entries}

    def read(self, name_or_entry):
        e = name_or_entry if isinstance(name_or_entry, list) else self.by_name[name_or_entry.lower()]
        self.f.seek(e[3])
        data = self.f.read(e[1])
        return decompress(data) if e[2] else data


def decompress(data):
    """PFH5 compressed file: u32 uncompressed size + stream (LZMA-alone, zstd, lz4 frame or zlib)."""
    size = struct.unpack_from("<I", data, 0)[0]
    body = data[4:]
    if body[:4] == b"\x28\xb5\x2f\xfd":
        try:
            import zstandard
        except ImportError:
            sys.exit("zstd-compressed pack: run `pip install zstandard`")
        return zstandard.ZstdDecompressor().decompress(body, max_output_size=size)
    if body[:4] == b"\x04\x22\x4d\x18":
        try:
            import lz4.frame
        except ImportError:
            sys.exit("lz4-compressed pack: run `pip install lz4`")
        return lz4.frame.decompress(body)
    if body[:2] in (b"\x78\x01", b"\x78\x9c", b"\x78\xda"):
        return zlib.decompress(body)
    import lzma
    # CA's LZMA1: 5-byte props followed by data; LZMA-alone needs an 8-byte size after the props.
    alone = body[:5] + struct.pack("<Q", size) + body[5:]
    return lzma.decompress(alone, format=lzma.FORMAT_ALONE)[:size]


# ------------------------------------------------------------------ schema (full)
def load_schema(ron_path):
    cache = ron_path + ".pkl"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(ron_path):
        with open(cache, "rb") as f:
            return pickle.load(f)
    s = open(ron_path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'\n        "([a-z0-9_]+_tables)": \[', s):
        t = m.group(1)
        if t in out:
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
            defs.setdefault(dm.group(1), re.findall(r'\(\s*name:\s*"([^"]+)",\s*field_type:\s*(\w+)', dm.group(2)))
        out[t] = defs
    with open(cache, "wb") as f:
        pickle.dump(out, f)
    return out


def decode_table(pack, entry, schema):
    table = entry[0].split("/")[1]
    data = pack.read(entry)
    _, version, rows = packlib.decode_db(data, table, schema)
    return table, version, rows


def write_tsv(path, table, version, pack_path, rows, fields):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(n for n, _ in fields) + "\n")
        f.write("#%s;%d;%s\n" % (table, version, pack_path))
        for r in rows:
            f.write("\t".join(r[n].replace("\t", "\\t").replace("\n", "\\n") for n, _ in fields) + "\n")


# ------------------------------------------------------------------ commands
def cmd_download(a):
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    hdr = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
    req = urllib.request.Request("https://api.github.com/repos/%s/releases/tags/%s" % (REPO, TAG), headers=hdr)
    try:
        rel = json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit("release '%s' not found: create it on GitHub (see game_data/README.md)" % TAG)
        raise
    os.makedirs(a.cache, exist_ok=True)
    for asset in rel.get("assets", []):
        dst = os.path.join(a.cache, asset["name"])
        if os.path.exists(dst) and os.path.getsize(dst) == asset["size"]:
            print("have  %s (%d bytes)" % (asset["name"], asset["size"]))
            continue
        print("fetch %s (%d bytes)..." % (asset["name"], asset["size"]), flush=True)
        r = urllib.request.Request(asset["url"], headers={"Authorization": hdr["Authorization"], "Accept": "application/octet-stream"})
        with urllib.request.urlopen(r) as src, open(dst + ".part", "wb") as out:
            while True:
                chunk = src.read(1 << 22)
                if not chunk:
                    break
                out.write(chunk)
        os.replace(dst + ".part", dst)
    if not rel.get("assets"):
        print("release '%s' has no files yet" % TAG)


def cmd_list(a):
    p = Pack(a.pack)
    print("%s flags=%#x files=%d" % (p.preamble.decode(), p.flags, len(p.entries)))
    for name, size, comp, _ in p.entries:
        if name.lower().startswith(a.prefix.lower()):
            print("%10d %s %s" % (size, "C" if comp else " ", name))


def db_entries(p, prefix="db/"):
    return [e for e in p.entries if e[0].lower().startswith(prefix.lower()) and e[0].count("/") == 2]


def cmd_dump(a):
    schema = load_schema(a.schema)
    p = Pack(a.pack)
    os.makedirs(a.out, exist_ok=True)
    want = set(t if t.endswith("_tables") else t + "_tables" for t in a.tables)
    for e in db_entries(p):
        table = e[0].split("/")[1]
        if table not in want:
            continue
        table, version, rows = decode_table(p, e, schema)
        fields = schema[table][str(version)]
        dst = os.path.join(a.out, "%s__%s.tsv" % (table, e[0].split("/")[2]))
        write_tsv(dst, table, version, e[0], rows, fields)
        print("%-60s v%-2d %6d rows -> %s" % (e[0], version, len(rows), dst))


def cmd_find(a):
    schema = load_schema(a.schema)
    p = Pack(a.pack)
    for e in db_entries(p, "db/" + (a.tables or "")):
        try:
            table, version, rows = decode_table(p, e, schema)
        except Exception as ex:  # unknown/unsupported table version
            print("skip %s: %s" % (e[0], ex), file=sys.stderr)
            continue
        for r in rows:
            if any(a.text in v for v in r.values()):
                print("%s v%d\t%s" % (table, version, "\t".join("%s=%s" % kv for kv in r.items() if kv[1] != "")))


def cmd_loc(a):
    p = Pack(a.pack)
    for e in p.entries:
        if e[0].endswith(".loc"):
            for r in packlib.decode_loc(p.read(e)):
                if a.text in r["key"] or a.text in r["text"]:
                    print("%s\t%s" % (r["key"], r["text"].replace("\n", "\\n")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("download"); s.add_argument("--cache", required=True); s.set_defaults(fn=cmd_download)
    s = sub.add_parser("list"); s.add_argument("pack"); s.add_argument("--prefix", default=""); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("dump"); s.add_argument("pack"); s.add_argument("--schema", required=True); s.add_argument("--out", required=True)
    s.add_argument("tables", nargs="+"); s.set_defaults(fn=cmd_dump)
    s = sub.add_parser("find"); s.add_argument("pack"); s.add_argument("--schema", required=True); s.add_argument("text")
    s.add_argument("--tables", default=""); s.set_defaults(fn=cmd_find)
    s = sub.add_parser("loc"); s.add_argument("pack"); s.add_argument("text"); s.set_defaults(fn=cmd_loc)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
