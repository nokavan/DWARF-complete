#!/usr/bin/env python3
"""
Minimal reader for Total War ESF files (CBAB), e.g. campaigns/<campaign>/startpos.esf.
Format per RPFM's rpfm_lib (files/esf). Handles the compressed inner startpos (COMPRESSED_DATA).

  python3 tools/esf_dump.py STARTPOS.esf --find TEXT [--depth N]
      prints the path of every record whose subtree contains the string TEXT, and a compact dump
      of the smallest such records
"""
import argparse
import lzma
import struct
import sys

sys.setrecursionlimit(100000)

FIXED = {0x01: 1, 0x02: 1, 0x03: 2, 0x04: 4, 0x05: 8, 0x06: 1, 0x07: 2, 0x08: 4, 0x09: 8, 0x0a: 4, 0x0b: 8,
         0x0c: 8, 0x0d: 12, 0x10: 2, 0x12: 0, 0x13: 0, 0x14: 0, 0x15: 0, 0x16: 1, 0x17: 2, 0x18: 3,
         0x19: 0, 0x1a: 1, 0x1b: 2, 0x1c: 3, 0x1d: 0, 0x21: 4, 0x23: 1, 0x24: 2, 0x25: 4}
ARRAYS = set(range(0x41, 0x51)) | set(range(0x52, 0x5e))


class ESF:
    def __init__(self, data):
        self.d = data
        if data[:4] != b"\xcb\xab\x00\x00":
            raise ValueError("not a CBAB ESF")
        rno = struct.unpack_from("<I", data, 12)[0]
        p = rno
        n = struct.unpack_from("<H", data, p)[0]
        p += 2
        self.names = []
        for _ in range(n):
            ln = struct.unpack_from("<H", data, p)[0]
            self.names.append(data[p + 2:p + 2 + ln].decode("utf-8", "replace"))
            p += 2 + ln
        self.utf16, self.utf8 = {}, {}
        for table, wide in ((self.utf16, True), (self.utf8, False)):
            cnt = struct.unpack_from("<I", data, p)[0]
            p += 4
            for _ in range(cnt):
                ln = struct.unpack_from("<I", data, p)[0]
                p += 4
                nb = ln * 2 if wide else ln
                s = data[p:p + nb].decode("utf-16-le" if wide else "utf-8", "replace")
                p += nb
                table[struct.unpack_from("<I", data, p)[0]] = s
                p += 4
        self.p = 16
        self.root = self.node(True)

    def leb(self):
        v = 0
        b = self.d[self.p]
        self.p += 1
        while b & 0x80:
            v = (v << 7) | (b & 0x7f)
            b = self.d[self.p]
            self.p += 1
        return (v << 7) | (b & 0x7f)

    def node(self, root=False):
        d = self.d
        t = d[self.p]
        self.p += 1
        if t & 0x80:
            if t & 0x20 or root:
                ni = struct.unpack_from("<H", d, self.p)[0]
                self.p += 3
            else:
                ni = ((t & 1) << 8) + d[self.p]
                self.p += 1
            size = self.leb()
            groups = self.leb() if t & 0x40 else 1
            end = self.p + size  # counted from after the group count (as in RPFM)
            children = []
            for _ in range(groups):
                if t & 0x40:
                    entry = self.leb()          # read first: self.p moves
                    gend = self.p + entry
                else:
                    gend = end
                lst = []
                while self.p < gend:
                    lst.append(self.node())
                children.append(lst)
            return ("R", self.names[ni], children)
        if t in FIXED:
            v = d[self.p:self.p + FIXED[t]]
            self.p += FIXED[t]
            return ("V", t, v)
        if t == 0x0e or t == 0x0f:
            i = struct.unpack_from("<I", d, self.p)[0]
            self.p += 4
            return ("S", (self.utf16 if t == 0x0e else self.utf8).get(i, "?"))
        if t in ARRAYS:
            n = self.leb()
            v = d[self.p:self.p + n]
            self.p += n
            if t in (0x4e, 0x4f):
                tab = self.utf16 if t == 0x4e else self.utf8
                return ("SA", [tab.get(struct.unpack_from("<I", v, k)[0], "?") for k in range(0, len(v), 4)])
            return ("A", t, v)
        if t == 0x26:
            fb = d[self.p]
            self.p += 1 + (fb if fb % 8 == 0 and fb != 0 else 7)
            if self.p < len(d) and d[self.p] == 0x9C:
                self.p += 1
            return ("V", t, b"")
        raise ValueError("unknown node type %#x at %d" % (t, self.p - 1))


def load(path):
    data = open(path, "rb").read()
    esf = ESF(data)
    # compressed inner ESF: last child of the root's first group
    last = esf.root[2][0][-1]
    if last[0] == "R" and last[1] == "COMPRESSED_DATA":
        blob = last[2][0][0][2]
        info = last[2][0][1]
        ulen = struct.unpack("<I", info[2][0][0][2])[0]
        props = info[2][0][1][2]
        inner = lzma.decompress(props + struct.pack("<Q", ulen) + blob, format=lzma.FORMAT_ALONE)
        esf = ESF(inner)
    return esf


def strings_in(n):
    if n[0] == "S":
        yield n[1]
    elif n[0] == "SA":
        yield from n[1]
    elif n[0] == "R":
        for g in n[2]:
            for c in g:
                yield from strings_in(c)


def short(n, depth, ind=0, out=None):
    out = [] if out is None else out
    pad = "  " * ind
    if n[0] == "R":
        out.append("%s[%s]" % (pad, n[1]))
        if depth > 0:
            for gi, g in enumerate(n[2]):
                for c in g:
                    short(c, depth - 1, ind + 1, out)
    elif n[0] == "S":
        out.append("%s'%s'" % (pad, n[1]))
    elif n[0] == "SA":
        out.append("%s%s" % (pad, n[1][:12]))
    elif n[0] == "V":
        out.append("%s<%#x %s>" % (pad, n[1], n[2].hex()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("esf")
    ap.add_argument("--find", required=True)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--record", default="", help="only report records with this name")
    a = ap.parse_args()
    esf = load(a.esf)
    found = []

    def walk(n, path):
        if n[0] != "R":
            return False
        hit = False
        for g in n[2]:
            for c in g:
                if c[0] in ("S", "SA") and a.find in (c[1] if c[0] == "S" else " ".join(c[1])):
                    hit = True
                elif c[0] == "R" and walk(c, path + [n[1]]):
                    hit = True
        if hit and (not a.record or n[1] == a.record):
            found.append((path + [n[1]], n))
        return hit

    walk(esf.root, [])
    for path, n in found[:40]:
        print("/".join(path))
    if a.record:
        for path, n in found[:3]:
            print("\n".join(short(n, a.depth)))


if __name__ == "__main__":
    main()
