#!/usr/bin/env python3
"""
Generates the new culture "Империя героев" for wh2_main_dwf_spine_of_sotek_dwarfs from the ORIGINAL game data.

  python3 -I mods/hero_empire_sotek/_gen/gen_culture.py --db db.pack --loc local_ru.pack --schema schema_wh3.ron

Stage 1 strategy ("dwarf-based culture"):
  * new culture he_hero_empire + subculture he_sc_hero_empire;
  * the faction row of Spine of Sotek is overridden to use the new subculture;
  * every game row that grants something to the dwarf culture/subculture (building availability,
    building names, agent art, diplomacy relations, UI features, campaign features ...) is cloned for the
    new culture, so the faction keeps working. Later stages replace dwarf content with our own.
  * campaign-group members can only hold ONE culture/subculture criterion, so members are cloned
    (member -> member_he, all criteria copied) and the clone is added to the same groups.

Output: mods/hero_empire_sotek/db/<table>/!he_culture.tsv and text/db/!he_culture.loc.tsv
Needs the game files, so CI does not run it; the generated TSVs are committed.
"""
import argparse
import hashlib
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import packlib  # noqa: E402
from game_data import Pack, load_schema  # noqa: E402

MOD = os.path.join(ROOT, "mods", "hero_empire_sotek")
FILE = "!he_culture"

FACTION = "wh2_main_dwf_spine_of_sotek_dwarfs"
OLD_CUL, OLD_SUB = "wh_main_dwf_dwarfs", "wh_main_sc_dwf_dwarfs"
NEW_CUL, NEW_SUB = "he_hero_empire", "he_sc_hero_empire"
SUFFIX = "_he"

CULTURE_NAME = "Империя героев"

# tables never cloned: map/startpos content, quest battles, narrative UI, single tech-tree/skill rows
SKIP = {
    "start_pos_regions_tables", "battles_tables", "battle_set_pieces_tables", "character_skill_nodes_tables",
    "technology_node_sets_tables", "narrative_viewer_tabs_tables", "prefab_types_tables",
    "intrigue_actions_incidents_junctions_tables", "subculture_conditions_tables",
    "factions_tables", "cultures_tables", "cultures_subcultures_tables", "campaign_group_members_tables",
    "frontend_factions_tables",
    # event conditions: a second GEN_CND_SUBCULTURE row may AND with the dwarf one and break dwarf events
    "cdir_events_incident_option_junctions_tables", "cdir_events_dilemma_option_junctions_tables",
    "cdir_events_mission_option_junctions_tables",
    # a cloned art set id would have no character arts behind it
    "campaign_character_art_sets_tables",
}
CRITERIA_PREFIX = "campaign_group_member_criteria_"


def load_meta(ron_path):
    """field name/type/is_key per table+version, plus localised field names."""
    s = open(ron_path, encoding="utf-8").read()
    meta = {}
    for m in re.finditer(r'\n        "([a-z0-9_]+_tables)": \[', s):
        t = m.group(1)
        if t in meta:
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
        for dm in re.finditer(r"\(\s*version:\s*(\d+),\s*fields:\s*\[(.*?)\],\s*localised_fields:\s*\[(.*?)\]", s[j:k], re.S):
            fields, culture_refs, tech_refs = [], set(), []
            for fm in re.finditer(r'\(\s*name:\s*"([^"]+)",\s*field_type:\s*(\w+),\s*is_key:\s*(\w+),.*?'
                                  r'is_reference:\s*(None|Some\(\("([^"]+)",\s*"([^"]+)"\)\))', dm.group(2), re.S):
                fields.append((fm.group(1), fm.group(2), fm.group(3) == "true"))
                if fm.group(5) == "cultures" and fm.group(6) == "key":
                    culture_refs.add(fm.group(1))
                if fm.group(5) in ("technology_nodes", "technology_node_sets") and fm.group(6) == "key":
                    tech_refs.append((fm.group(1), (fm.group(5) + "_tables", "key")))
            defs.setdefault(dm.group(1), {"fields": fields, "culture_refs": culture_refs, "refs": tech_refs,
                                          "loc": re.findall(r'name:\s*"([^"]+)"', dm.group(3))})
        meta[t] = defs
    return meta


def sub(v):
    return NEW_CUL if v == OLD_CUL else NEW_SUB if v == OLD_SUB else v


def sub_row(row, culture_refs):
    """Subculture key is unique -> replaced in any field. The culture key equals a FACTION key
    (wh_main_dwf_dwarfs = Karaz-a-Karak), so it is replaced only in fields referencing cultures."""
    out = {}
    for k, v in row.items():
        if v == OLD_SUB:
            out[k] = NEW_SUB
        elif v == OLD_CUL and k in culture_refs:
            out[k] = NEW_CUL
        else:
            out[k] = v
    return out


def touches(row, culture_refs):
    return any(v == OLD_SUB or (v == OLD_CUL and k in culture_refs) for k, v in row.items())


def new_int(seed, existing):
    n = int(hashlib.sha1(seed.encode()).hexdigest()[:7], 16) + 100000000
    while str(n) in existing:
        n += 1
    existing.add(str(n))
    return str(n)


class Out:
    def __init__(self):
        self.tables = {}   # table -> (version, header, rows)
        self.loc = {}

    def add(self, table, version, header, row):
        t = self.tables.setdefault(table, (version, header, []))
        t[2].append(row)

    def write(self):
        for table, (version, header, rows) in sorted(self.tables.items()):
            d = os.path.join(MOD, "db", table)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, FILE + ".tsv"), "w", encoding="utf-8") as f:
                f.write("\t".join(header) + "\n#%s;%d;db/%s/%s\n" % (table, version, table, FILE))
                seen = set()
                for r in rows:
                    line = "\t".join(r[h].replace("\t", "\\t").replace("\n", "\\n") for h in header)
                    if line not in seen:
                        seen.add(line)
                        f.write(line + "\n")
        os.makedirs(os.path.join(MOD, "text", "db"), exist_ok=True)
        with open(os.path.join(MOD, "text", "db", FILE + ".loc.tsv"), "w", encoding="utf-8") as f:
            f.write("key\ttext\ttooltip\n#Loc;1;text/db/%s.loc\n" % FILE)
            for k in sorted(self.loc):
                f.write("%s\t%s\tfalse\n" % (k, self.loc[k].replace("\t", " ").replace("\n", "\\n")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--loc", required=True)
    ap.add_argument("--schema", required=True)
    a = ap.parse_args()

    schema = load_schema(a.schema)
    meta = load_meta(a.schema)
    pack = Pack(a.db)
    loc = {}
    for e in Pack(a.loc).entries:
        pass
    lp = Pack(a.loc)
    for e in lp.entries:
        if e[0].endswith(".loc"):
            for r in packlib.decode_loc(lp.read(e)):
                loc[r["key"]] = r["text"]

    tables = {}
    for e in pack.entries:
        parts = e[0].split("/")
        if len(parts) == 3 and parts[0] == "db":
            try:
                g, v, rows = packlib.decode_db(pack.read(e), parts[1], schema)
            except Exception as ex:
                print("skip %s: %s" % (e[0], ex))
                continue
            t = tables.setdefault(parts[1], {"version": v, "rows": []})
            t["rows"] += rows

    out = Out()
    stats = {}

    def fields(t):
        return meta[t][str(tables[t]["version"])]["fields"]

    def loc_copy(t, old_row, new_row, prefix_table=None):
        lf = meta[t][str(tables[t]["version"])]["loc"]
        if not lf:
            return
        keys = [n for n, _, k in fields(t) if k]
        base = (prefix_table or t[:-len("_tables")])
        old_k = "".join(old_row[k] for k in keys)
        new_k = "".join(new_row[k] for k in keys)
        for name in lf:
            ok = "%s_%s_%s" % (base, name, old_k)
            if ok in loc:
                out.loc["%s_%s_%s" % (base, name, new_k)] = loc[ok]

    # ---------------------------------------------------------------- 1. culture + subculture
    for t, src_key, field in (("cultures_tables", OLD_CUL, "key"), ("cultures_subcultures_tables", OLD_SUB, "subculture")):
        rows = tables[t]["rows"]
        existing = {r["index"] for r in rows}
        old = next(r for r in rows if r[field] == src_key)
        new = {k: sub(v) for k, v in old.items()}
        new[field] = NEW_CUL if t == "cultures_tables" else NEW_SUB
        new["index"] = new_int(t + NEW_CUL, existing)
        if t == "cultures_tables":
            new["fallback_ui_culture"] = "Dwarfs"
        out.add(t, tables[t]["version"], [n for n, _, _ in fields(t)], new)
    for prefix in ("cultures_name", "cultures_subcultures_name"):
        out.loc["%s_%s" % (prefix, NEW_CUL if prefix == "cultures_name" else NEW_SUB)] = CULTURE_NAME
    # copy any other culture/subculture loc fields (descriptions etc.)
    for k, v in loc.items():
        for old, new in ((OLD_SUB, NEW_SUB), (OLD_CUL, NEW_CUL)):
            if k.startswith(("cultures_", "cultures_subcultures_")) and k.endswith("_" + old):
                nk = k[: -len(old)] + new
                out.loc.setdefault(nk, v)

    # ---------------------------------------------------------------- 2. faction row override
    t = "factions_tables"
    row = dict(next(r for r in tables[t]["rows"] if r["key"] == FACTION))
    row["subculture"] = NEW_SUB
    out.add(t, tables[t]["version"], [n for n, _, _ in fields(t)], row)

    # ---------------------------------------------------------------- 3. campaign-group members
    crit_tables = [t for t in tables if t.startswith(CRITERIA_PREFIX)]
    members = set()
    for t in crit_tables:
        refs = meta[t][str(tables[t]["version"])]["culture_refs"]
        for r in tables[t]["rows"]:
            if touches(r, refs):
                members.add(r["member"])
    # members also bound to another specific faction would never apply to us -> do not clone
    for r in tables[CRITERIA_PREFIX + "factions_tables"]["rows"]:
        if r["member"] in members and r["context"] == "ACTOR" and r["faction"] != FACTION:
            members.discard(r["member"])
    for t in crit_tables:
        hdr = [n for n, _, _ in fields(t)]
        for r in tables[t]["rows"]:
            if r["member"] in members:
                nr = sub_row(r, meta[t][str(tables[t]["version"])]["culture_refs"])
                nr["member"] = r["member"] + SUFFIX
                out.add(t, tables[t]["version"], hdr, nr)
                stats[t] = stats.get(t, 0) + 1
    t = "campaign_group_members_tables"
    hdr = [n for n, _, _ in fields(t)]
    for r in tables[t]["rows"]:
        if r["id"] in members:
            nr = dict(r)
            nr["id"] = r["id"] + SUFFIX
            out.add(t, tables[t]["version"], hdr, nr)
            stats[t] = stats.get(t, 0) + 1

    # ---------------------------------------------------------------- 4. generic clone of every other dwarf row
    for t, data in sorted(tables.items()):
        if t in SKIP or t.startswith(CRITERIA_PREFIX):
            continue
        fl = fields(t)
        hdr = [n for n, _, _ in fl]
        keyf = [(n, ty) for n, ty, k in fl if k]
        refs = meta[t][str(data["version"])]["culture_refs"]
        existing_keys = {tuple(r[n] for n, _ in keyf) for r in data["rows"]}
        for r in data["rows"]:
            if not touches(r, refs):
                continue
            nr = sub_row(r, refs)
            nk = tuple(nr[n] for n, _ in keyf)
            if keyf and nk in existing_keys:
                # culture is not part of the key: give the clone a new key
                n0, ty0 = keyf[0]
                if ty0.startswith("I"):
                    nr[n0] = new_int(t + "|".join(r[n] for n, _ in keyf), {x[0] for x in existing_keys})
                else:
                    nr[n0] = r[n0] + SUFFIX
                nk = tuple(nr[n] for n, _ in keyf)
            existing_keys.add(nk)
            out.add(t, data["version"], hdr, nr)
            loc_copy(t, r, nr)
            stats[t] = stats.get(t, 0) + 1

    # ---------------------------------------------------------------- 5. tech tree: deep copy of the dwarf node set
    sets = [r for r in tables["technology_node_sets_tables"]["rows"] if r["culture"] == OLD_CUL or r["subculture"] == OLD_SUB]
    node_map = {}
    set_map = {}
    for r in sets:
        nr = sub_row(r, {"culture"})
        nr["key"] = r["key"] + SUFFIX
        set_map[r["key"]] = nr["key"]
        out.add("technology_node_sets_tables", tables["technology_node_sets_tables"]["version"],
                [n for n, _, _ in fields("technology_node_sets_tables")], nr)
        loc_copy("technology_node_sets_tables", r, nr)
    for r in tables["technology_nodes_tables"]["rows"]:
        if r["technology_node_set"] in set_map:
            node_map[r["key"]] = r["key"] + SUFFIX
    tech_refs = {"technology_nodes_tables": node_map, "technology_node_sets_tables": set_map}
    for t, data in sorted(tables.items()):
        fl = meta[t][str(data["version"])]
        ref_fields = [(n, ref[0]) for n, ref in fl.get("refs", [])]
        if not ref_fields:
            continue
        hdr = [n for n, _, _ in fields(t)]
        for r in data["rows"]:
            hit = [(n, rt) for n, rt in ref_fields if r[n] in tech_refs[rt]]
            if not hit and not (t == "technology_nodes_tables" and r["key"] in node_map):
                continue
            nr = dict(r)
            for n, rt in ref_fields:
                if r[n] in tech_refs[rt]:
                    nr[n] = tech_refs[rt][r[n]]
            if t == "technology_nodes_tables":
                nr["key"] = node_map[r["key"]]
            out.add(t, data["version"], hdr, nr)
            loc_copy(t, r, nr)
            stats[t] = stats.get(t, 0) + 1

    # ---------------------------------------------------------------- write
    for t in list(out.tables):
        pass
    if os.path.isdir(MOD):
        for d in os.listdir(os.path.join(MOD, "db")):
            p = os.path.join(MOD, "db", d, FILE + ".tsv")
            if os.path.exists(p):
                os.remove(p)
            if not os.listdir(os.path.join(MOD, "db", d)):
                shutil.rmtree(os.path.join(MOD, "db", d))
    out.write()
    total = 0
    for t, n in sorted(stats.items(), key=lambda x: -x[1]):
        print("%5d %s" % (n, t))
        total += n
    print("tables: %d, cloned rows: %d, loc: %d" % (len(out.tables), total, len(out.loc)))


if __name__ == "__main__":
    main()
