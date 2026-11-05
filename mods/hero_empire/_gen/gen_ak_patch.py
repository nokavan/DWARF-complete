#!/usr/bin/env python3
"""
Builds the Assembly Kit patch for the startpos of "Империя героев".

  python3 -I mods/hero_empire/_gen/gen_ak_patch.py --ak <assembly_kit/raw_data/db> --out <dir>

Writes modified copies of the AK raw-data XML files into <out>/raw_data/db/ (only files that change):

  1. Our DB records the Assembly Kit must know when it builds the startpos (cloned from the Empire's AK
     records, overridden with our generated rows): cultures, cultures_subcultures, factions,
     technology_node_sets, technology_nodes, technology_node_links.
  2. The startpos: the Spine of Sotek's startpos records are REASSIGNED to our faction. All startpos links
     are numeric IDs and the faction key only lives in start_pos_factions, so regions, leader, diplomacy
     and past events stay consistent:
       - start_pos_factions: faction key -> he_faction_hero_empire, playable, major, Empire AI settings;
       - start_pos_characters: leader -> Empire lord (names of an Empire faction leader);
       - start_pos_land_units: the leader's dwarf army -> Empire units;
       - start_pos_settlements: dwarf settlement buildings -> Empire ones;
       - start_pos_regions: cultural originator + rebel faction -> ours.
Every edit is checked (expected record found, field present) - otherwise the script stops.
"""
import argparse
import os
import re
import sys
import time
import uuid
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import packlib  # noqa: E402

MOD = os.path.join(ROOT, "mods", "hero_empire")
GEN = "!he_faction"
FACTION = "he_faction_hero_empire"
NEW_SUB = "he_sc_hero_empire"
SPINE_ID = "1754835792"            # start_pos_factions.ID of wh2_main_dwf_spine_of_sotek_dwarfs (wh3_main_combi)
SPINE_KEY = "wh2_main_dwf_spine_of_sotek_dwarfs"
ARMY = ["wh_main_emp_inf_swordsmen", "wh_main_emp_inf_swordsmen", "wh_main_emp_inf_halberdiers",
        "wh_main_emp_inf_halberdiers", "wh_main_emp_inf_handgunners", "wh_main_emp_inf_handgunners",
        "wh_main_emp_art_great_cannon"]
SETTLEMENT_BUILDINGS = {"wh_main_dwf_settlement_major_1": "wh_main_emp_settlement_major_1",
                        "wh_main_dwf_settlement_minor_1": "wh_main_emp_settlement_minor_1"}
CLONE_TABLES = [  # table, key field(s) used to find the template, how to map our key to the vanilla template key
    ("cultures", ["key"]),
    ("cultures_subcultures", ["subculture"]),
    ("factions", ["key"]),
    ("technology_node_sets", ["key"]),
    ("technology_nodes", ["key"]),
    ("technology_node_links", ["parent_key", "child_key"]),
]
TEMPLATE_OF = {"he_hero_empire": "wh_main_emp_empire", "he_sc_hero_empire": "wh_main_sc_emp_empire",
               FACTION: "wh_main_emp_empire"}


class XmlTable:
    def __init__(self, path, name):
        self.path, self.name = path, name
        self.text = open(path, encoding="utf-8", newline="").read()   # keep CRLF as is
        self.pat = re.compile(r"<%s [^>]*>.*?</%s>" % (name, name), re.S)

    def records(self):
        return [(m.start(), m.end(), m.group(0)) for m in self.pat.finditer(self.text)]

    @staticmethod
    def field(rec, f):
        m = re.search(r"<%s(?: [^>]*)?>(.*?)</%s>|<%s ?/>" % (f, f, f), rec, re.S)
        if not m:
            return None
        return m.group(1) if m.group(1) is not None else ""

    @staticmethod
    def set_field(rec, f, value):
        v = escape(str(value))
        new, n = re.subn(r"(<%s(?: [^>]*)?>)(.*?)(</%s>)" % (f, f), lambda m: m.group(1) + v + m.group(3), rec, count=1, flags=re.S)
        if n == 0:
            new, n = re.subn(r"<%s ?/>" % f, "<%s>%s</%s>" % (f, v, f), rec, count=1)
        if n == 0:
            raise KeyError("field %s not in record" % f)
        return new

    def find(self, **kv):
        out = []
        for s, e, rec in self.records():
            if all(self.field(rec, k) == v for k, v in kv.items()):
                out.append((s, e, rec))
        return out

    def replace_record(self, start, end, new):
        self.text = self.text[:start] + new + self.text[end:]

    def append(self, rec):
        i = self.text.rindex("</dataroot>")
        nl = "\r\n" if "\r\n" in self.text else "\n"
        self.text = self.text[:i] + rec + nl + self.text[i:]

    def save(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, os.path.basename(self.path)), "w", encoding="utf-8", newline="") as f:
            f.write(self.text)


def ak_format(template_value, value):
    """Write values the way the Assembly Kit does: booleans as 0/1, integers without a fraction."""
    v = str(value)
    if v in ("true", "false") and template_value in ("0", "1", ""):
        return "1" if v == "true" else "0"
    if re.fullmatch(r"-?\d+\.0+", v) and re.fullmatch(r"-?\d+", template_value or "0"):
        return v.split(".")[0]
    return v


def new_header(rec, table, key):
    head = re.match(r"<%s [^>]*>" % table, rec).group(0)
    head = re.sub(r'record_uuid="[^"]*"', 'record_uuid="{%s}"' % uuid.uuid5(uuid.NAMESPACE_URL, "hero_empire/%s/%s" % (table, key)), head)
    head = re.sub(r'record_timestamp="[^"]*"', 'record_timestamp="%d"' % int(time.time() * 1000), head)
    head = re.sub(r'record_key="[^"]*"', 'record_key="%s"' % escape(key), head)
    return head + rec[len(re.match(r"<%s [^>]*>" % table, rec).group(0)):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ak", required=True, help="assembly_kit/raw_data/db")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out_db = os.path.join(a.out, "raw_data", "db")
    report = []

    # ---------------------------------------------------------------- 1. our DB records for the Assembly Kit
    for table, keys in CLONE_TABLES:
        tsv = os.path.join(MOD, "db", table + "_tables", GEN + ".tsv")
        _, _, _, _, rows = packlib.read_tsv(tsv)
        xt = XmlTable(os.path.join(a.ak, table + ".xml"), table)
        added = 0
        for row in rows:
            tpl_kv = {}
            for k in keys:
                v = row[k]
                tpl_kv[k] = TEMPLATE_OF.get(v, v[:-3] if v.endswith("_he") else v)
            if xt.find(**{k: row[k] for k in keys}):
                continue  # already patched
            found = xt.find(**tpl_kv)
            if not found:
                sys.exit("%s: no AK template record for %s" % (table, tpl_kv))
            rec = found[0][2]
            for f, v in row.items():
                old = xt.field(rec, f)
                if old is not None:
                    rec = xt.set_field(rec, f, ak_format(old, v))
            if table in ("cultures", "cultures_subcultures"):
                rec = xt.set_field(rec, "name", "Империя героев")
            if table == "factions":
                rec = xt.set_field(rec, "screen_name", "Империя героев")
                rec = xt.set_field(rec, "screen_name_when_rebels", "Мятежники Империи героев")
            rec = new_header(rec, table, "|".join(row[k] for k in keys))
            xt.append(rec)
            added += 1
        xt.save(out_db)
        report.append("%-24s +%d records" % (table, added))

    # ---------------------------------------------------------------- 2. startpos: reassign Spine of Sotek to our faction
    spf = XmlTable(os.path.join(a.ak, "start_pos_factions.xml"), "start_pos_factions")
    f = spf.find(ID=SPINE_ID)
    if len(f) != 1 or XmlTable.field(f[0][2], "faction") not in (SPINE_KEY, FACTION):
        sys.exit("start_pos_factions: Spine of Sotek record %s not found" % SPINE_ID)
    # AI settings of an Empire minor faction in the same campaign
    emp_minor = next(r for _, _, r in spf.records() if XmlTable.field(r, "campaign") == "wh3_main_combi"
                     and (XmlTable.field(r, "faction") or "").startswith("wh_main_emp_") and XmlTable.field(r, "is_major") == "0")
    rec = f[0][2]
    for k, v in (("faction", FACTION), ("playable", "1"), ("is_major", "1"),
                 ("cdir_military_generator_config", XmlTable.field(emp_minor, "cdir_military_generator_config")),
                 ("cai_personality_group", XmlTable.field(emp_minor, "cai_personality_group"))):
        rec = XmlTable.set_field(rec, k, v)
    spf.replace_record(f[0][0], f[0][1], rec)
    spf.save(out_db)
    report.append("start_pos_factions       record %s -> %s (playable, major; AI like %s)" % (SPINE_ID, FACTION, XmlTable.field(emp_minor, "faction")))

    spc = XmlTable(os.path.join(a.ak, "start_pos_characters.xml"), "start_pos_characters")
    leaders = spc.find(faction=SPINE_ID, ministerial_position="faction_leader")
    if len(leaders) != 1:
        sys.exit("start_pos_characters: leader of %s not found" % SPINE_ID)
    leader_id = XmlTable.field(leaders[0][2], "ID")
    emp_minor_id = XmlTable.field(emp_minor, "ID")
    emp_leader = spc.find(faction=emp_minor_id, ministerial_position="faction_leader")
    rec = XmlTable.set_field(leaders[0][2], "subtype", "wh_main_emp_lord")
    if emp_leader:
        for k in ("Name", "Surname"):
            rec = XmlTable.set_field(rec, k, XmlTable.field(emp_leader[0][2], k))
    spc.replace_record(leaders[0][0], leaders[0][1], rec)
    spc.save(out_db)
    report.append("start_pos_characters     leader %s -> wh_main_emp_lord" % leader_id)

    spl = XmlTable(os.path.join(a.ak, "start_pos_land_units.xml"), "start_pos_land_units")
    units = spl.find(general=leader_id)
    if not units:
        sys.exit("start_pos_land_units: no army for leader %s" % leader_id)
    for (s, e, r), unit in sorted(zip(units, ARMY), key=lambda x: -x[0][0]):   # back to front: offsets stay valid
        spl.replace_record(s, e, XmlTable.set_field(r, "unit_type", unit))
    spl.save(out_db)
    report.append("start_pos_land_units     %d units -> Empire army" % min(len(units), len(ARMY)))

    spr = XmlTable(os.path.join(a.ak, "start_pos_regions.xml"), "start_pos_regions")
    regions = spr.find(owning_faction=SPINE_ID)
    for s, e, r in sorted(regions, key=lambda x: -x[0]):
        r2 = XmlTable.set_field(XmlTable.set_field(r, "cultural_originator", NEW_SUB), "rebel_faction", FACTION)
        spr.replace_record(s, e, r2)
    spr.save(out_db)
    report.append("start_pos_regions        %d regions: %s" % (len(regions), ", ".join(XmlTable.field(r, "region") for _, _, r in regions)))

    sps = XmlTable(os.path.join(a.ak, "start_pos_settlements.xml"), "start_pos_settlements")
    region_ids = {XmlTable.field(r, "id") for _, _, r in regions}
    n = 0
    for s, e, r in sorted(sps.records(), key=lambda x: -x[0]):
        if XmlTable.field(r, "region") in region_ids:
            b = XmlTable.field(r, "primary_building")
            if b not in SETTLEMENT_BUILDINGS and b not in SETTLEMENT_BUILDINGS.values():
                sys.exit("start_pos_settlements: unexpected building %s" % b)
            sps.replace_record(s, e, XmlTable.set_field(r, "primary_building", SETTLEMENT_BUILDINGS.get(b, b)))
            n += 1
    sps.save(out_db)
    report.append("start_pos_settlements    %d settlements -> Empire buildings" % n)

    # ---------------------------------------------------------------- 3. verify: untouched records byte-identical
    for fn in sorted(os.listdir(out_db)):
        table = fn[:-4]
        old = XmlTable(os.path.join(a.ak, fn), table)
        new = XmlTable(os.path.join(out_db, fn), table)
        o, nw = [r for _, _, r in old.records()], [r for _, _, r in new.records()]
        changed = sum(1 for x, y in zip(o, nw) if x != y)
        if nw[:len(o)] != o and len(nw) != len(o):
            # appended tables: the original records must be an unchanged prefix
            if nw[:len(o)] != o:
                sys.exit("%s: original records changed" % fn)
        head_old, head_new = old.text[:old.records()[0][0]], new.text[:new.records()[0][0]]
        if head_old != head_new or not new.text.endswith(old.text[old.records()[-1][1]:]):
            sys.exit("%s: file header/footer changed" % fn)
        report.append("verify %-28s records %d -> %d, modified in place %d" % (fn, len(o), len(nw), changed))

    with open(os.path.join(a.out, "PATCH_REPORT.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
