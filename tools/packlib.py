"""
Minimal reader/writer for Total War: WARHAMMER III mod packs (PFH5),
binary DB tables and .loc files.

The binary formats follow RPFM's rpfm_lib (MIT):
  * Pack PFH5:  "PFH5" | u32 type|flags | u32 dep_count | u32 dep_index_len |
                u32 file_count | u32 file_index_len | u32 timestamp |
                dep index | file index (u32 size, u8 compressed, cstring path) | data
  * DB table:   [GUID marker FD FE FC FF + sized UTF-16 guid] |
                [version marker FC FD FE FF + i32 version] | u8 1 | u32 rows | rows
  * Loc:        u16 FEFF | "LOC" | u8 0 | i32 1 | u32 rows | (u16-str key, u16-str text, bool tooltip)*
"""
import struct
import uuid

PFH5 = b"PFH5"
PACK_TYPE_MOD = 3
GUID_MARKER = bytes([253, 254, 252, 255])
VERSION_MARKER = bytes([252, 253, 254, 255])
LOC_BOM = 0xFEFF


# ---------------------------------------------------------------- primitives
def w_bool(v):
    return struct.pack("<B", 1 if v else 0)


def w_i32(v):
    return struct.pack("<i", int(v))


def w_u32(v):
    return struct.pack("<I", int(v))


def w_str_u8(s):
    b = s.encode("utf-8")
    if len(b) > 0xFFFF:
        raise ValueError("string too long")
    return struct.pack("<H", len(b)) + b


def w_opt_str_u8(s):
    return w_bool(False) if s == "" else w_bool(True) + w_str_u8(s)


def w_str_u16(s):
    b = s.encode("utf-16-le")
    return struct.pack("<H", len(b) // 2) + b


def parse_bool(s):
    s = s.strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", ""):
        return False
    raise ValueError("bad boolean: %r" % s)


ENCODERS = {
    "Boolean": lambda s: w_bool(parse_bool(s)),
    "I32": lambda s: w_i32(int(s or 0)),
    "StringU8": w_str_u8,
    "OptionalStringU8": w_opt_str_u8,
    "StringU16": w_str_u16,
}


class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def take(self, n):
        if self.p + n > len(self.d):
            raise ValueError("unexpected end of data")
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def u8(self):
        return self.take(1)[0]

    def bool(self):
        v = self.u8()
        if v not in (0, 1):
            raise ValueError("bad bool byte %d at %d" % (v, self.p - 1))
        return v == 1

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def str_u8(self):
        return self.take(self.u16()).decode("utf-8")

    def str_u16(self):
        return self.take(self.u16() * 2).decode("utf-16-le")

    def opt_str_u8(self):
        return self.str_u8() if self.bool() else ""

    def cstr(self):
        end = self.d.index(b"\0", self.p)
        s = self.d[self.p:end].decode("utf-8")
        self.p = end + 1
        return s

    def done(self):
        return self.p == len(self.d)


DECODERS = {
    "Boolean": lambda r: "true" if r.bool() else "false",
    "I32": lambda r: str(r.i32()),
    "StringU8": lambda r: r.str_u8(),
    "OptionalStringU8": lambda r: r.opt_str_u8(),
    "StringU16": lambda r: r.str_u16(),
}


# ---------------------------------------------------------------- TSV
def read_tsv(path):
    """RPFM-style TSV: line 1 = column names, line 2 = '#table;version;path', then rows."""
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\r\n") for l in f]
    header = lines[0].split("\t")
    meta = lines[1]
    if not meta.startswith("#"):
        raise ValueError("%s: second line must be '#table;version;path'" % path)
    table, version, pack_path = meta[1:].split(";")
    rows = []
    for n, l in enumerate(lines[2:], start=3):
        if l.strip() == "":
            continue
        cells = l.split("\t")
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        if len(cells) != len(header):
            raise ValueError("%s:%d: expected %d columns, got %d" % (path, n, len(header), len(cells)))
        rows.append(dict(zip(header, cells)))
    return table, int(version), pack_path, header, rows


# ---------------------------------------------------------------- DB
def encode_db(table, version, rows, schema):
    sd = schema[table]
    if sd["version"] != version:
        raise ValueError("%s: TSV version %d != schema version %d" % (table, version, sd["version"]))
    out = bytearray()
    guid = str(uuid.uuid5(uuid.NAMESPACE_URL, "dwf_ancient_lineages/" + table))
    out += GUID_MARKER + w_str_u16(guid)
    out += VERSION_MARKER + w_i32(version)
    out += w_bool(True)
    out += w_u32(len(rows))
    for row in rows:
        for name, ftype in sd["fields"]:
            if name not in row:
                raise ValueError("%s: missing column %s" % (table, name))
            out += ENCODERS[ftype](row[name])
    return bytes(out)


def decode_db(data, table, schema):
    sd = schema[table]
    r = Reader(data)
    guid = None
    if data[:4] == GUID_MARKER:
        r.take(4)
        guid = r.str_u16()
    version = 0
    if data[r.p:r.p + 4] == VERSION_MARKER:
        r.take(4)
        version = r.i32()
    r.bool()
    count = r.u32()
    rows = []
    for _ in range(count):
        rows.append({name: DECODERS[ft](r) for name, ft in sd["fields"]})
    if not r.done():
        raise ValueError("%s: %d trailing bytes" % (table, len(data) - r.p))
    return guid, version, rows


# ---------------------------------------------------------------- Loc
def unescape_loc(s):
    return s.replace("\\n", "\n").replace("\\t", "\t")


def encode_loc(rows):
    out = bytearray(struct.pack("<H", LOC_BOM) + b"LOC" + b"\0" + w_i32(1) + w_u32(len(rows)))
    for row in rows:
        out += w_str_u16(row["key"]) + w_str_u16(unescape_loc(row["text"])) + w_bool(parse_bool(row["tooltip"]))
    return bytes(out)


def decode_loc(data):
    r = Reader(data)
    if r.u16() != LOC_BOM or r.take(3) != b"LOC" or r.u8() != 0:
        raise ValueError("bad loc header")
    if r.i32() != 1:
        raise ValueError("bad loc version")
    rows = []
    for _ in range(r.u32()):
        rows.append({"key": r.str_u16(), "text": r.str_u16(), "tooltip": r.bool()})
    if not r.done():
        raise ValueError("loc: trailing bytes")
    return rows


# ---------------------------------------------------------------- Pack
def encode_pack(files, timestamp=0):
    """files: dict 'a/b/c' -> bytes. Returns PFH5 mod pack bytes."""
    entries = sorted(((p.replace("/", "\\"), d) for p, d in files.items()), key=lambda e: e[0].lower())
    index = bytearray()
    for path, data in entries:
        index += w_u32(len(data)) + w_bool(False) + path.encode("utf-8") + b"\0"
    header = PFH5 + w_u32(PACK_TYPE_MOD) + w_u32(0) + w_u32(0) + w_u32(len(entries)) + w_u32(len(index)) + w_u32(timestamp)
    return header + bytes(index) + b"".join(d for _, d in entries)


def decode_pack(data):
    r = Reader(data)
    if r.take(4) != PFH5:
        raise ValueError("not a PFH5 pack")
    flags = r.u32()
    dep_count, dep_len = r.u32(), r.u32()
    file_count, index_len = r.u32(), r.u32()
    r.u32()  # timestamp
    deps = [r.cstr() for _ in range(dep_count)]
    index_start = r.p
    entries = []
    for _ in range(file_count):
        size = r.u32()
        compressed = r.bool()
        entries.append((r.cstr(), size, compressed))
    if r.p - index_start != index_len:
        raise ValueError("file index length mismatch")
    files = {}
    for path, size, compressed in entries:
        files[path.replace("\\", "/")] = r.take(size)
    if not r.done():
        raise ValueError("pack: trailing bytes")
    return {"type": flags & 0xF, "flags": flags & ~0xF, "deps": deps, "files": files}
