#!/usr/bin/env python3
"""
Add-on for the ORIGINAL Iron Caravan (iron_caravan_draft.pack, Chaos Dwarf caravan on MIXER's Lost Slavers):
regular dwarf units and heroes join the caravan. The original mod stays enabled and unchanged.

  python3 -I converters/iron_caravan_dwarfs_addon/build.py --src iron_caravan_draft.pack \
      --game-db db.pack --schema schema_wh3.ron --out build/mods/iron_caravan_dwarfs_addon

What the add-on adds (tables only add rows, nothing of the original is replaced):
  * every caravan building that recruits a Chaos Dwarf unit also recruits the dwarf unit with the same role;
  * buildings that unlock Infernal Castellans / Taur'ruks also unlock Master Engineers / Thanes;
    caravan bonuses for Chaos Dwarf missile units / artillery also apply to dwarf ones;
  * dwarf heroes (thane, master engineer, runesmith, dragon slayer) are allowed for the faction;
  * unit-mod compatibility: standard dwarf military buildings can be built in caravan workshop slots, so units
    that other mods add to those buildings appear in the caravan;
  * a small campaign script removes dwarf units and heroes from the caravan's block lists at load.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "archive", "iron_caravan_dwf"))
import packlib  # noqa: E402
from game_data import Pack, load_meta, load_schema, write_tsv  # noqa: E402
from convert import UNITS, EFFECTS, DWARF_MILITARY_CHAINS, header_version  # noqa: E402

FACTION = "mixer_chd_lost_slavers"
DWARF_HEROES = [("champion", "wh_main_dwf_thane"), ("engineer", "wh_main_dwf_master_engineer"),
                ("runesmith", "wh_main_dwf_runesmith"), ("dignitary", "wh3_dlc25_dwf_dragon_slayer")]
HERO_TWINS = {"wh3_dlc23_chd_infernal_castellan": "wh_main_dwf_master_engineer",
              "wh3_dlc23_chd_bull_centaur_taurruk": "wh_main_dwf_thane"}
FILE = "ic_dwarfs_addon"

ADDON_LUA = r"""-- Iron Caravan: dwarfs add-on. Runs after script/campaign/mod/iron_caravan_init.lua (alphabetical order).
-- The caravan blocks foreign units and kills foreign spellcasters by lists in iron_caravan.config; dwarf units and
-- heroes are taken off those lists here, before the caravan applies them on the first tick.
local function log(m) pcall(out, "[Iron Caravan dwarfs] " .. tostring(m)) end
local X = iron_caravan
if type(X) ~= "table" or type(X.config) ~= "table" then
    log("Iron Caravan is not loaded - add-on inactive")
    return
end
local C = X.config
local function is_dwarf(key) return type(key) == "string" and string.find(key, "_dwf_", 1, true) ~= nil end
local function filter(list)
    if type(list) ~= "table" then return 0 end
    local removed, i = 0, 1
    while i <= #list do
        if is_dwarf(list[i]) then table.remove(list, i); removed = removed + 1 else i = i + 1 end
    end
    return removed
end
local units = filter(C.blocked_units)
local casters = filter(C.caster_subtypes)
-- caravan hero services (survey / buy out, seize / ravage) for the dwarf twins of castellan and taur'ruk
local ok, D = pcall(require, "script/iron_caravan/hero_services_config")
if ok and type(D) == "table" and type(D.subtypes) == "table" then
    D.subtypes["wh_main_dwf_master_engineer"] = D.subtypes["wh3_dlc23_chd_infernal_castellan"] or "infernal_castellan"
    D.subtypes["wh_main_dwf_thane"] = D.subtypes["wh3_dlc23_chd_bull_centaur_taurruk"] or "bull_centaur_taurruk"
end
log("unblocked " .. units .. " dwarf units, " .. casters .. " dwarf heroes")
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--game-db", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    schema, meta = load_schema(a.schema), load_meta(a.schema)
    src, game = Pack(a.src), Pack(a.game_db)

    def src_rows(table):
        out = []
        for e in src.entries:
            if e[0].startswith("db/%s/" % table):
                out += packlib.decode_db(src.read(e), table, schema)[2]
        return out

    game_index = {}
    for e in game.entries:
        p = e[0].split("/")
        if len(p) == 3 and p[0] == "db":
            game_index.setdefault(p[1], []).append(e)

    def vanilla(table):
        rows = []
        for e in game_index.get(table, []):
            rows += packlib.decode_db(game.read(e), table, schema)[2]
        return rows

    def version(table):
        return max(header_version(game.read(e)) for e in game_index[table])

    out_tables = {}

    def new_id(used, seed):
        n = int(seed) if seed.isdigit() else 1700000000
        while str(n) in used:
            n = (n + 7919) % 2147483647
        used.add(str(n))
        return str(n)

    # 1. dwarf twins of Chaos Dwarf recruitment rows
    bua = src_rows("building_units_allowed_tables")
    used = {r["key"] for r in bua} | {r["key"] for r in vanilla("building_units_allowed_tables")}
    have = {(r["building"], r["unit"]) for r in bua}
    rows = []
    for r in bua:
        dw = UNITS.get(r["unit"])
        if dw and (r["building"], dw) not in have:
            have.add((r["building"], dw))
            rows.append(dict(r, unit=dw, key=new_id(used, str(int(r["key"]) + 7919))))
    out_tables["building_units_allowed_tables"] = rows

    # 2. dwarf twins of building effects (hero availability, unit-type bonuses)
    bej = src_rows("building_effects_junction_tables")
    have = {(r["building"], r["effect"]) for r in bej}
    rows = []
    for r in bej:
        dw = EFFECTS.get(r["effect"])
        if dw and (r["building"], dw) not in have:
            have.add((r["building"], dw))
            rows.append(dict(r, effect=dw))
    out_tables["building_effects_junction_tables"] = rows

    # 3. dwarf heroes allowed for the faction
    tpl = src_rows("faction_agent_permitted_subtypes_tables")[0]
    out_tables["faction_agent_permitted_subtypes_tables"] = [
        dict(tpl, faction=FACTION, agent=agent, subtype=sub) for agent, sub in DWARF_HEROES]

    # 4. dwarf military chains in caravan workshop slots + caravan building set
    stp = src_rows("slot_template_permitted_building_chains_tables")
    secondary = sorted({r["slot_template"] for r in stp if r["slot_template"].startswith("ic_")
                        and r["slot_template"].endswith("_secondary") and r["slot_template"] != "ic_enclave_secondary"})
    out_tables["slot_template_permitted_building_chains_tables"] = [
        dict(stp[0], chain=ch, chain_set="", remove="false", slot_template=st, super_chain="")
        for st in secondary for ch in DWARF_MILITARY_CHAINS]
    sets = src_rows("building_chain_availability_sets_tables")
    set_ids = sorted({r["id"] for r in sets})
    in_set = {(r["id"], r["building_chain"]) for r in sets}
    out_tables["building_chain_availability_sets_tables"] = [
        {"id": s, "building_chain": ch} for s in set_ids for ch in DWARF_MILITARY_CHAINS if (s, ch) not in in_set]

    # write
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    for t, rows in out_tables.items():
        if not rows:
            continue
        v = version(t)
        fields = [(n, ty) for n, ty, _, _ in meta[t][str(v)]["fields"]]
        for r in rows:
            for n, _ in fields:
                r.setdefault(n, "")
        path = os.path.join(a.out, "db", t, FILE + ".tsv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_tsv(path, t, v, "db/%s/%s" % (t, FILE), rows, fields)
        print("%-58s %4d rows" % (t, len(rows)))
    lua = os.path.join(a.out, "script", "campaign", "mod", "zz_iron_caravan_dwarfs_addon.lua")
    os.makedirs(os.path.dirname(lua), exist_ok=True)
    with open(lua, "w", encoding="utf-8") as f:
        f.write(ADDON_LUA)
    # the original pack defines the caravan's own records (buildings, slot templates, building set)
    with open(os.path.join(a.out, "_external_keys.tsv"), "w", encoding="utf-8") as f:
        for t, k in (("building_levels_tables", "level_name"), ("slot_templates_tables", "key"),
                     ("building_chain_availability_set_ids_tables", "id")):
            src_table = {"building_levels_tables": "building_levels_tables"}.get(t, t)
            for r in src_rows(src_table):
                f.write("%s\t%s\t%s\n" % (t, k, r[k]))
        f.write("factions_tables\tkey\t%s\n" % FACTION)


if __name__ == "__main__":
    main()
