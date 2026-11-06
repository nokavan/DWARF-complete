#!/usr/bin/env python3
"""
Iron Caravan (Chaos Dwarf mercenary convoy, mixer_chd_lost_slavers) -> regular Dwarfs
(MIXER slot "Dain's Expedition", mixer_dwf_dains_expedition).

The source mod is the user's own pack iron_caravan_draft.pack (private "game-data" release).
It is never committed; this script rebuilds the converted mod tree from it:

  python3 -I converters/iron_caravan_dwf/convert.py --src iron_caravan_draft.pack \
      --game-db db.pack --schema schema_wh3.ron --out build/mods/iron_caravan_dwf

Stage 1:
  * faction slot / frontend leader id / subculture / culture -> dwarfs;
  * every Chaos Dwarf unit -> a dwarf unit with the same role (DB and Lua);
  * Chaos Dwarf hero types -> dwarf hero types; vanilla dwarf heroes keep vanilla dwarf skills;
  * Rykarth / Tordrek / convoy lords keep keys, names, skills and roles but use dwarf models;
    the Skullcannon mount is removed;
  * economy: Raw Materials -> gold, Armaments -> Oathgold;
  * unit compatibility with other mods: the caravan no longer blocks any unit by list, and the
    standard dwarf military building chains can be built in the caravan, so units that other mods
    add to those buildings show up automatically.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import packlib  # noqa: E402
from game_data import Pack, load_meta, load_schema, write_tsv  # noqa: E402

OLD_FACTION, NEW_FACTION = "mixer_chd_lost_slavers", "mixer_dwf_dains_expedition"
OLD_LEADER, NEW_LEADER = "424817151", "1176379500"
CHD_SC, DWF_SC = "wh3_dlc23_sc_chd_chaos_dwarfs", "wh_main_sc_dwf_dwarfs"
CHD_CULTURE, DWF_CULTURE = "wh3_dlc23_chd_chaos_dwarfs", "wh_main_dwf_dwarfs"
EMPLOYER = "wh_main_dwf_karak_azul"           # nearest dwarf hold to Ekrund, first contract giver
ARMS, RAW, OATHGOLD = "wh3_dlc23_chd_armaments", "wh3_dlc23_chd_raw_materials", "dwf_oathgold"

# Chaos Dwarf unit -> dwarf unit with a similar role
UNITS = {
    "wh3_dlc23_chd_inf_chaos_dwarf_warriors": "wh_main_dwf_inf_dwarf_warrior_0",
    "wh3_dlc23_chd_inf_chaos_dwarf_warriors_great_weapons": "wh_main_dwf_inf_dwarf_warrior_1",
    "wh3_dlc23_chd_inf_chaos_dwarf_warriors_ror": "wh_dlc06_dwf_inf_warriors_dragonfire_pass_0",
    "wh3_dlc23_chd_inf_chaos_dwarf_blunderbusses": "wh_main_dwf_inf_thunderers_0",
    "wh3_dlc23_chd_inf_chaos_dwarf_blunderbusses_ror": "wh3_dlc25_dwf_inf_thunderers_ror",
    "wh3_dlc23_chd_inf_infernal_guard": "wh_main_dwf_inf_longbeards",
    "wh3_dlc23_chd_inf_infernal_guard_great_weapons": "wh_main_dwf_inf_longbeards_1",
    "wh3_dlc23_chd_inf_infernal_guard_fireglaives": "wh_main_dwf_inf_quarrellers_1",
    "wh3_dlc23_chd_inf_infernal_ironsworn": "wh_main_dwf_inf_ironbreakers",
    "wh3_dlc23_chd_inf_infernal_ironsworn_ror": "wh_dlc06_dwf_inf_norgrimlings_ironbreakers_0",
    "wh3_dlc23_chd_inf_goblin_labourers": "wh_main_dwf_inf_miners_0",
    "wh3_dlc23_chd_inf_orc_labourers": "wh_main_dwf_inf_miners_1",
    "wh3_dlc23_chd_inf_hobgoblin_archers": "wh_main_dwf_inf_quarrellers_0",
    "wh3_dlc23_chd_inf_hobgoblin_cutthroats": "wh_main_dwf_inf_dwarf_warrior_0",
    "wh3_dlc23_chd_inf_hobgoblin_cutthroats_summoned": "wh3_dlc25_dwf_inf_miners_1_summoned",
    "wh3_dlc23_chd_inf_hobgoblin_sneaky_gits": "wh_dlc06_dwf_inf_rangers_0",
    "wh3_dlc23_chd_cav_hobgoblin_wolf_raiders_spears": "wh_main_dwf_veh_gyrocopter_0",
    "wh3_dlc23_chd_cav_hobgoblin_wolf_raiders_bows": "wh_main_dwf_veh_gyrocopter_1",
    "wh3_dlc23_chd_cav_hobgoblin_wolf_raiders_ror": "wh_main_dwf_veh_gyrobomber",
    "wh3_dlc23_chd_cav_bull_centaurs_axe": "wh_main_dwf_inf_slayers",
    "wh3_dlc23_chd_cav_bull_centaurs_dual_axe": "wh2_dlc10_dwf_inf_giant_slayers",
    "wh3_dlc23_chd_cav_bull_centaurs_dual_axe_ror": "wh_dlc06_dwf_inf_dragonback_slayers_0",
    "wh3_dlc23_chd_cav_bull_centaurs_greatweapons": "wh_main_dwf_inf_hammerers",
    "wh3_dlc23_chd_cav_bull_centaur_taurruk_blood": "wh3_dlc25_dwf_inf_doomseekers",
    "wh3_dlc23_chd_mon_bale_taurus": "wh3_dlc25_dwf_veh_thunderbarge",
    "wh3_dlc23_chd_mon_great_taurus": "wh_main_dwf_veh_gyrobomber",
    "wh3_dlc23_chd_mon_lammasu": "wh_main_dwf_veh_gyrobomber",
    "wh3_dlc23_chd_mon_kdaai_fireborn": "wh3_dlc25_dwf_inf_doomseekers",
    "wh3_dlc23_chd_mon_kdaai_fireborn_summoned": "wh3_dlc25_dwf_inf_doomseekers",
    "wh3_dlc23_chd_mon_kdaai_destroyer": "wh_main_dwf_inf_irondrakes_2",
    "wh3_dlc23_chd_veh_deathshrieker_rocket_launcher": "wh_main_dwf_art_organ_gun",
    "wh3_dlc23_chd_veh_dreadquake_mortar": "wh_main_dwf_art_grudge_thrower",
    "wh3_dlc23_chd_veh_iron_daemon": "wh_main_dwf_art_flame_cannon",
    "wh3_dlc23_chd_veh_iron_daemon_1dreadquake": "wh_main_dwf_art_flame_cannon",
    "wh3_dlc23_chd_veh_iron_daemon_3payload_qb": "wh_main_dwf_art_flame_cannon",
    "wh3_dlc23_chd_veh_iron_daemon_ror": "wh_main_dwf_art_flame_cannon",
    "wh3_dlc23_chd_veh_iron_daemon_ror_1dreadquake": "wh_main_dwf_art_flame_cannon",
    "wh3_dlc23_chd_veh_magma_cannon": "wh_main_dwf_art_cannon",
    "wh3_dlc23_chd_veh_skullcracker": "wh_dlc06_dwf_art_bolt_thrower_0",
    "wh3_dlc23_chd_veh_skullcracker_1dreadquake": "wh_dlc06_dwf_art_bolt_thrower_0",
    "wh_main_chs_art_hellcannon": "wh_main_dwf_art_cannon",
    "wh3_main_chd_art_hobgob_bolt_thrower": "wh_dlc06_dwf_art_bolt_thrower_0",
}
# Combined dwarfs: every building effect below gets a dwarf twin (same building, level, value);
# the Chaos Dwarf effect stays. Hero availability: castellan -> also engineer, taurruk -> also thane.
EFFECTS = {
    "wh3_dlc23_effect_enable_recruitment_chd_infernal_castellan": "wh_main_effect_agent_enable_recruitment_engineer",
    "wh3_dlc23_effect_enable_recruitment_chd_bull_centaur_taurruk": "wh_main_effect_agent_enable_recruitment_champion_dwarfs",
    # caravan workshop bonuses aimed at Chaos Dwarf units -> the same bonus for dwarf units
    "wh3_dlc23_effect_force_stat_missile_damage_chd_missiles_chaos_dwarfs":
        "wh2_dlc11_effect_force_stat_missile_damage_dwf_quarrellers_thunderers_rangers",
    "wh3_dlc23_effect_force_stat_reload_chd_missiles_chaos_dwarfs": "wh3_dlc25_effect_force_stat_reload_dwf_thunderers",
    "wh3_dlc23_effect_force_stat_reload_chd_artillery": "wh3_dlc25_effect_force_stat_reload_time_dwf_arty_warmachines",
    "wh3_dlc23_effect_force_stat_leadership_chd_hobgoblins": "wh_main_effect_force_stat_leadership",
}
# Chaos Dwarf hero types the caravan uses -> dwarf hero types with the same role
SUBTYPES = {
    # the generic convoy lord gets its own subtype (a copy of the caravan's castellan lord): mapping it onto
    # wh_main_dwf_lord made every vanilla dwarf lord a convoy lord, and MIXER's starting general (a vanilla
    # dwarf lord on a Spirit of Grungni horde) no longer matched his force -> horde destroyed at load
    "wh3_dlc23_chd_overseer": "ic_overseer_lord",
    "wh3_dlc23_chd_lord_convoy_overseer": "ic_overseer_lord",
}
# Combined dwarfs: Chaos Dwarf heroes stay; these dwarf heroes get the same caravan hero services
HERO_TWINS = {"wh3_dlc23_chd_infernal_castellan": "wh_main_dwf_master_engineer",
              "wh3_dlc23_chd_bull_centaur_taurruk": "wh_main_dwf_thane"}
# custom characters: (vanilla dwarf land unit to copy the model/stats from, vanilla art set prefix)
CHARACTERS = {
    "ic_cha_rykarth": "wh_main_dwf_cha_lord_0",
    "ic_cha_tordrek": "wh_main_dwf_cha_master_engineer_0",
    "ic_castellan_lord_unit": "wh_main_dwf_cha_lord_0",
    "ic_bull_centaur_lord_unit": "wh3_dlc25_dwf_cha_daemon_slayer",
}
ART = {  # IC art set -> vanilla dwarf art sets to cycle through
    "ic_rykarth": ["wh_main_art_set_dwf_lord_01"],
    "ic_tordrek": ["wh_main_art_set_dwf_engineer_01"],
    "ic_castellan_lord": ["wh_main_art_set_dwf_lord_01", "wh_main_art_set_dwf_lord_02", "wh_main_art_set_dwf_lord_03"],
    "ic_bull_centaur_lord": ["wh3_dlc25_art_set_dwf_daemon_slayer_01", "wh3_dlc25_art_set_dwf_daemon_slayer_02",
                             "wh3_dlc25_art_set_dwf_daemon_slayer_03"],
}
SKULLCANNON = "ic_cha_rykarth_skullcannon"
CLONE_FROM, CLONE_TO = "ic_castellan_lord", "ic_overseer_lord"
# standard dwarf military chains allowed in every caravan workshop slot (unit compatibility)
DWARF_MILITARY_CHAINS = [
    "wh_main_DWARFS_barracks", "wh_main_DWARFS_smiths", "wh_main_DWARFS_slayers", "wh_main_DWARFS_workshops",
    "wh_main_DWARFS_engineer", "wh3_dlc25_DWARFS_workshops_infantry", "wh_dlc06_DWARFS_ranger_hub",
]
COPY_FACTION_HEROES_FROM = "wh_main_dwf_karak_azul"
# records that exist in MIXER (a required mod), not in the base game
EXTERNAL = {("factions_tables", "key"): {NEW_FACTION}, ("frontend_faction_leaders_tables", "key"): {NEW_FACTION},
            ("agent_subtypes_tables", "key"): {"mixer_dummy"}}

VALUE_MAP = dict(SUBTYPES)
VALUE_MAP.update({OLD_FACTION: NEW_FACTION, OLD_LEADER: NEW_LEADER, CHD_SC: DWF_SC})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--game-db", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    schema, meta = load_schema(a.schema), load_meta(a.schema)
    src, game = Pack(a.src), Pack(a.game_db)

    game_index = {}
    for e in game.entries:
        p = e[0].split("/")
        if len(p) == 3 and p[0] == "db":
            game_index.setdefault(p[1], []).append(e)
    game_cache = {}

    def vanilla(table):
        if table not in game_cache:
            rows = []
            for e in game_index.get(table, []):
                rows += packlib.decode_db(game.read(e), table, schema)[2]
            game_cache[table] = rows
        return game_cache[table]

    # ---------------------------------------------------------------- read source
    tables, raw_files = {}, {}
    for e in src.entries:
        name = e[0]
        p = name.split("/")
        if name.endswith(".rpfm_reserved"):
            continue
        if len(p) == 3 and p[0] == "db":
            _, version, rows = packlib.decode_db(src.read(e), p[1], schema)
            tables[p[1]] = {"version": version, "path": name, "rows": rows}
        else:
            raw_files[name] = src.read(e)
    print("source: %d tables, %d other files" % (len(tables), len(raw_files)))

    def rows(t):
        return tables[t]["rows"] if t in tables else []

    def set_rows(t, new):
        tables[t]["rows"] = new

    def ensure(t, version_like=None):
        if t not in tables:
            versions = sorted({header_version(game.read(e)) for e in game_index[t]})
            tables[t] = {"version": versions[-1], "path": "db/%s/ic_dwf" % t, "rows": []}
        return tables[t]["rows"]

    def fields(t):
        return [f for f in meta[t][str(tables[t]["version"])]["fields"]]

    # ---------------------------------------------------------------- 1. drop what only makes sense for Chaos Dwarfs
    dropped = {}

    def drop(t, pred, why):
        before = rows(t)
        keep = [r for r in before if not pred(r)]
        if len(keep) != len(before):
            dropped.setdefault(why, 0)
            dropped[why] += len(before) - len(keep)
            set_rows(t, keep)

    # the faction row itself stays MIXER's dwarf row; IC only renamed it through loc
    drop("factions_tables", lambda r: True, "IC faction row (MIXER's dwarf row is used)")
    # vanilla dwarf heroes keep vanilla dwarf skill trees
    removed_skill_sets = [r for r in rows("character_skill_node_sets_tables") if r["agent_subtype_key"] in SUBTYPES]
    drop("character_skill_node_sets_tables", lambda r: r["agent_subtype_key"] in SUBTYPES, "skill trees of Chaos Dwarf heroes")
    # Chaos Dwarf hero types in the faction hero list are replaced by the dwarf list below
    drop("faction_agent_permitted_subtypes_tables", lambda r: r["subtype"] in ("wh3_dlc23_chd_overseer_hobgoblin_spawned_army",),
         "Chaos Dwarf hero types")
    # IC tech tree: its own node set cannot replace the node set saved in MIXER's startpos.
    # The technologies stay (scripts check them); the tree is rebuilt inside the dwarf tree later.
    for t in ("technology_node_sets_tables", "technology_nodes_tables", "technology_node_links_tables",
              "technology_ui_tabs_to_technology_nodes_junctions_tables"):
        drop(t, lambda r: True, "IC technology tree (dwarf tree stays)")
    # Rykarth's Skullcannon
    drop("main_units_tables", lambda r: r["unit"] == SKULLCANNON, "Skullcannon mount")
    drop("land_units_tables", lambda r: r["key"] == SKULLCANNON, "Skullcannon mount")
    drop("campaign_character_uniform_ancillary_junctions_tables", lambda r: True, "Skullcannon mount")
    for t in list(tables):
        drop(t, lambda r: any("skullcannon" in v.lower() for v in r.values()), "Skullcannon mount")
    for name in [n for n in raw_files if "skullcannon" in n.lower()]:
        del raw_files[name]
    drop("agent_uniforms_tables", lambda r: True, "Chaos Dwarf models")
    # Chaos Dwarf resources that dwarfs do not have
    drop("campaign_group_pooled_resources_tables", lambda r: True, "Chaos Dwarf resources")

    # ---------------------------------------------------------------- 2. exact value mapping
    mapped = 0
    GLOBAL = {OLD_FACTION: NEW_FACTION, OLD_LEADER: NEW_LEADER, CHD_SC: DWF_SC}
    for t, d in tables.items():
        kinds = {}
        for name, _, _, ref in fields(t):
            target = ref[0] if ref else ""
            if target == "agent_subtypes_tables" or (not ref and "subtype" in name):
                kinds[name] = SUBTYPES
        for r in d["rows"]:
            for k, v in r.items():
                m = kinds.get(k)
                if v in GLOBAL:
                    r[k] = GLOBAL[v]
                elif m and v in m:
                    r[k] = m[v]
                elif v == CHD_CULTURE and k in ("culture", "culture_key"):
                    r[k] = DWF_CULTURE
                else:
                    continue
                mapped += 1
    print("mapped %d values" % mapped)

    # ---------------------------------------------------------------- 3. economy: raw -> gold, armaments -> Oathgold
    factors = ensure("pooled_resource_factor_junctions_tables")
    new_factors, renamed = [], {}
    for r in factors:
        if r["resource"] == ARMS:
            nid = "%s_%s" % (OATHGOLD, r["factor"])
            renamed[r["unique_id"]] = nid
            new_factors.append(dict(r, unique_id=nid, resource=OATHGOLD))
        elif r["resource"] == RAW or r["factor"] == "ic_removed_systems":
            renamed[r["unique_id"]] = None
        else:
            new_factors.append(r)
    set_rows("pooled_resource_factor_junctions_tables", new_factors)
    renamed["%s_construction" % ARMS] = "%s_buildings" % OATHGOLD
    renamed["%s_construction" % RAW] = None

    costs = {r["id"]: r for r in rows("resource_costs_tables")}
    keep = []
    for r in rows("resource_cost_pooled_resource_junctions_tables"):
        f = r["pooled_resource_factor"]
        if f.startswith(RAW):
            c = costs[r["resource_cost"]]
            c["treasury_cost"] = str(int(c["treasury_cost"]) - int(r["amount"]))  # amounts are negative
        elif f in renamed and renamed[f]:
            keep.append(dict(r, pooled_resource_factor=renamed[f]))
        else:
            keep.append(r)
    set_rows("resource_cost_pooled_resource_junctions_tables", keep)

    keep = []
    for r in rows("effect_bonus_value_pooled_resource_factor_junctions_tables"):
        f = r["resource_factor"]
        if f in renamed:
            if renamed[f]:
                keep.append(dict(r, resource_factor=renamed[f]))
        elif not f.startswith(RAW):
            keep.append(r)
    set_rows("effect_bonus_value_pooled_resource_factor_junctions_tables", keep)

    # events: Chaos Dwarf culture checks and resource payloads
    def payload(v):
        v = v.replace("RESOURCE[%s];FACTOR[%s_events]" % (ARMS, ARMS), "RESOURCE[%s];FACTOR[%s_missions]" % (OATHGOLD, OATHGOLD))
        return v.replace(ARMS + ":", OATHGOLD + ":")
    for t in ("cdir_events_dilemma_payloads_tables", "cdir_events_incident_payloads_tables"):
        for r in rows(t):
            r["value"] = payload(r["value"])
            m = re.match(r"RESOURCE\[%s\];FACTOR\[[a-z0-9_]+\];AMOUNT\[(-?\d+)\]" % RAW, r["value"])
            if r["payload_key"] == "FACTION_POOLED_RESOURCE_TRANSACTION" and m:
                r["payload_key"], r["value"] = "TREASURY", "AMOUNT[%s]" % m.group(1)
    for t in ("cdir_events_dilemma_option_junctions_tables", "cdir_events_incident_option_junctions_tables"):
        for r in rows(t):
            r["value"] = payload(r["value"])
            if r["option_key"] in ("CND_CULTURE", "GEN_CND_CULTURE") and r["value"] == CHD_CULTURE:
                r["value"] = DWF_CULTURE

    # Extraction Works produced raw materials -> gold income of the foreign building (like Skaven undercities)
    for r in rows("building_effects_junction_tables"):
        if r["effect"] == "ic_enclave_display_raw":
            r["effect"] = "wh_main_effect_economy_gdp_other"
            r["effect_scope"] = "foreign_building_to_foreign_building_own"

    # MIXER starts Dain's Expedition as a Spirit of Grungni airship HORDE (Lost Slavers start as a normal
    # army). Turning that starting general into Rykarth crashes the campaign start, so the MIXER general
    # stays; the caravan script removes it and creates Rykarth with his convoy near Ekrund.
    for r in rows("frontend_faction_leaders_tables"):
        r["agent_subtype_record"] = "mixer_dummy"
        r["voiceover"] = "wh_main_vo_actor_Dwarf_Thane1"

    # ---------------------------------------------------------------- 4. heroes of the faction
    permitted = rows("faction_agent_permitted_subtypes_tables")
    have = {(r["agent"], r["subtype"]) for r in permitted}
    for r in vanilla("faction_agent_permitted_subtypes_tables"):
        if r["faction"] == COPY_FACTION_HEROES_FROM and (r["agent"], r["subtype"]) not in have:
            permitted.append(dict(r, faction=NEW_FACTION))
            have.add((r["agent"], r["subtype"]))

    # ---------------------------------------------------------------- 5. dwarf models for the custom characters
    v_main = {r["unit"]: r for r in vanilla("main_units_tables")}
    v_land = {r["key"]: r for r in vanilla("land_units_tables")}
    keep_main = ("unit", "land_unit", "campaign_cap", "caste", "recruitment_cost", "upkeep_cost",
                 "multiplayer_cost", "restrict_xp_gain_in_campaign", "multiplayer_cap")
    for r in rows("main_units_tables"):
        tpl = v_main.get(CHARACTERS.get(r["unit"], ""))
        if tpl:
            r.update({k: v for k, v in tpl.items() if k not in keep_main and k in r})
    keep_land = ("key", "historical_description_text", "short_description_text")
    for r in rows("land_units_tables"):
        tpl = v_land.get(CHARACTERS.get(r["key"], ""))
        if tpl:
            r.update({k: v for k, v in tpl.items() if k not in keep_land and k in r})
    drop("unit_variants_tables", lambda r: r["unit"] in CHARACTERS or r["unit"] == SKULLCANNON, "Chaos Dwarf character models")
    variants = ensure("unit_variants_tables")
    for unit, tpl in CHARACTERS.items():
        for vr in vanilla("unit_variants_tables"):
            if vr["unit"] == tpl:
                variants.append(dict(vr, unit=unit, name=vr["name"].replace(tpl, unit)))

    v_arts = vanilla("campaign_character_arts_tables")
    art_rows, next_id = [], 1700000000
    for s in rows("campaign_character_art_sets_tables"):
        templates = ART.get(s["agent_subtype"])
        if not templates:
            continue
        n = int(re.search(r"(\d+)$", s["art_set_id"]).group(1)) if re.search(r"_(\d+)$", s["art_set_id"]) else 1
        tpl = templates[(n - 1) % len(templates)]
        for ar in v_arts:
            if ar["art_set_id"] == tpl:
                next_id += 1
                art_rows.append(dict(ar, art_set_id=s["art_set_id"], id=str(next_id)))
    set_rows("campaign_character_arts_tables", art_rows)
    for r in rows("agent_subtypes_tables"):
        r["audio_voiceover_actor_group"] = {"ic_rykarth": "wh_main_vo_actor_Dwarf_Lord",
                                            "ic_castellan_lord": "wh_main_vo_actor_Dwarf_Lord",
                                            "ic_bull_centaur_lord": "wh_main_vo_actor_Dwarf_Lord",
                                            "ic_tordrek": "wh_main_vo_actor_Dwarf_MasterEngineer"}.get(
            r["key"], r["audio_voiceover_actor_group"])
        if "wh3_dlc23_chd_" in r["small_icon"]:
            r["small_icon"] = "ui/campaign ui/agents/wh_main_dwf_engineer.png" if r["key"] == "ic_tordrek" else ""
        if r["recruitment_category"].startswith("wh3_dlc23_chd_"):
            r["recruitment_category"] = "dwf_lord"
        if r["names_group"] == "names_chd_bull_centaurs":
            r["names_group"] = ""

    # new subtype ic_overseer_lord = copy of ic_castellan_lord (rows, art sets, unit, skills)
    for t, d in tables.items():
        if t in ("campaign_group_member_criteria_agent_subtypes_tables",):
            continue
        clones = [{k: v.replace(CLONE_FROM, CLONE_TO) for k, v in r.items()}
                  for r in d["rows"] if any(CLONE_FROM in v for v in r.values())]
        for c in clones:
            for k in ("id", "key") if t in ("campaign_character_arts_tables", "building_units_allowed_tables") else ():
                if k in c and c[k].isdigit():
                    c[k] = str(int(c[k]) + 50000)
        d["rows"].extend(clones)

    # ---------------------------------------------------------------- 6. unit compatibility: dwarf military chains in caravan slots
    permitted_chains = rows("slot_template_permitted_building_chains_tables")
    secondary = sorted({r["slot_template"] for r in permitted_chains
                        if r["slot_template"].startswith("ic_") and r["slot_template"].endswith("_secondary")
                        and r["slot_template"] != "ic_enclave_secondary"})
    tpl_row = permitted_chains[0]
    for st in secondary:
        for ch in DWARF_MILITARY_CHAINS:
            permitted_chains.append(dict(tpl_row, chain=ch, chain_set="", remove="false", slot_template=st, super_chain=""))
    sets = rows("building_chain_availability_sets_tables")
    in_set = {(r["id"], r["building_chain"]) for r in sets}
    # The faction set REPLACES the dwarf culture set. MIXER starts the faction as a Spirit of Grungni airship
    # horde whose buildings come from the dwarf set; without them the horde is invalid and destroyed at
    # load, killing the faction. So the caravan set contains the whole dwarf culture set as well.
    dwarf_set = [r["building_chain"] for r in vanilla("building_chain_availability_sets_tables") if r["id"] == "wh_main_bas_dwf"]
    assert len(dwarf_set) > 100, "dwarf culture building set not found"
    for set_id in sorted({r["id"] for r in sets}):
        for ch in DWARF_MILITARY_CHAINS + dwarf_set:
            if (set_id, ch) not in in_set:
                sets.append(dict(sets[0], id=set_id, building_chain=ch))

    # combined dwarfs: every Chaos Dwarf unit row gets a dwarf twin (recruitment, unit sets, effects)
    used_ids = {}
    for t, d in tables.items():
        if t in ("ui_unit_bullet_point_unit_overrides_tables", "main_units_tables", "land_units_tables"):
            continue
        unit_fields = [n for n, _, _, ref in fields(t)
                       if (ref and ref[0] in ("main_units_tables", "land_units_tables")) or (not ref and "unit" in n)]
        eff_fields = [n for n, _, _, ref in fields(t) if ref and ref[0] == "effects_tables"]
        id_fields = [n for n, ty, key, ref in fields(t) if key and not ref and n in ("key", "id", "unique_id")]
        ids = used_ids.setdefault(t, {r[f] for r in d["rows"] for f in id_fields})
        twins = []
        for r in d["rows"]:
            hit = {f: UNITS[r[f]] for f in unit_fields if r.get(f) in UNITS}
            hit.update({f: EFFECTS[r[f]] for f in eff_fields if r.get(f) in EFFECTS})
            if not hit:
                continue
            c = dict(r, **hit)
            for f in id_fields:
                v = c[f]
                n = (int(v) if v.isdigit() else 0) + 7919
                while str(n) in ids or not v.isdigit():
                    if not v.isdigit():
                        c[f] = v + "_dwf"
                        break
                    n += 7919
                if v.isdigit():
                    c[f] = str(n % 2147483647)
                ids.add(c[f])
            twins.append(c)
        d["rows"].extend(twins)

    # two Chaos Dwarf units can map to one dwarf unit: keep one recruitment row per building
    seen, keep = set(), []
    for r in rows("building_units_allowed_tables"):
        k = (r["building"], r["unit"], r["faction"])
        if k not in seen:
            seen.add(k)
            keep.append(r)
    set_rows("building_units_allowed_tables", keep)

    # ---------------------------------------------------------------- 7. dedupe + cascade removal of broken references
    for t, d in tables.items():
        seen, out = set(), []
        for r in d["rows"]:
            k = tuple(sorted(r.items()))
            if k not in seen:
                seen.add(k)
                out.append(r)
        d["rows"] = out

    # skill trees removed above: drop their items and the nodes no other tree uses
    removed_sets = {r["key"] for r in removed_skill_sets}
    drop("character_skill_node_set_items_tables", lambda r: r["set"] in removed_sets, "skill trees of Chaos Dwarf heroes")
    used_nodes = {r["item"] for r in rows("character_skill_node_set_items_tables")}
    drop("character_skill_nodes_tables", lambda r: r["key"] not in used_nodes, "skill trees of Chaos Dwarf heroes")

    vanilla_keys = {}

    def known_values(table, field):
        k = (table, field)
        if k not in vanilla_keys:
            vals = {r[field] for r in vanilla(table) if field in r} if table in game_index else set()
            vals |= EXTERNAL.get(k, set())
            vanilla_keys[k] = vals
        mod = {r[field] for r in tables[table]["rows"] if field in r} if table in tables else set()
        return vanilla_keys[k] | mod

    while True:
        removed = {}
        for t, d in tables.items():
            for name, _, _, ref in fields(t):
                if not ref or (ref[0] not in tables and ref[0] not in game_index) or ref[0] not in schema:
                    continue
                known = known_values(*ref)
                before = len(d["rows"])
                bad = [r for r in d["rows"] if r.get(name) and r[name] not in known]
                for r in bad[:3]:
                    print("    broken %s.%s = %s -> %s.%s" % (t, name, r[name], ref[0], ref[1]))
                d["rows"] = [r for r in d["rows"] if not r.get(name) or r[name] in known]
                if len(d["rows"]) != before:
                    removed[t] = removed.get(t, 0) + before - len(d["rows"])
        if not removed:
            break
        for t, n in removed.items():
            why = "broken reference after conversion: " + t
            dropped[why] = dropped.get(why, 0) + n
    for k, v in sorted(dropped.items()):
        print("dropped %5d rows: %s" % (v, k))

    # ---------------------------------------------------------------- 8. write db
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    for t, d in sorted(tables.items()):
        if not d["rows"]:
            continue
        fl = [(n, ty) for n, ty, _, _ in fields(t)]
        out = os.path.join(a.out, "db", t, os.path.basename(d["path"]) + ".tsv")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        write_tsv(out, t, d["version"], d["path"], d["rows"], fl)

    # ---------------------------------------------------------------- 9. loc, scripts, other files
    for name, data in raw_files.items():
        if name.startswith("text/") and name.endswith(".loc"):
            loc = packlib.decode_loc(data)
            loc += [dict(r, key=r["key"].replace(CLONE_FROM, CLONE_TO)) for r in loc if CLONE_FROM in r["key"]]
            data = packlib.encode_loc([{"key": r["key"].replace(OLD_FACTION, NEW_FACTION),
                                        "text": r["text"].replace("\n", "\\n").replace("\t", "\\t"),
                                        "tooltip": "true" if r["tooltip"] else "false"} for r in loc])
        elif name.endswith(".lua"):
            data = patch_lua(name, data.decode("utf-8")).encode("utf-8")
        out = os.path.join(a.out, name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(data)
    with open(os.path.join(a.out, "_external_keys.tsv"), "w", encoding="utf-8") as f:
        for (t, k), vs in sorted(EXTERNAL.items()):
            for v in sorted(vs):
                f.write("%s\t%s\t%s\n" % (t, k, v))
    report(tables)


def header_version(data):
    r = packlib.Reader(data)
    if data[:4] == packlib.GUID_MARKER:
        r.take(4)
        r.str_u16()
    if data[r.p:r.p + 4] == packlib.VERSION_MARKER:
        r.take(4)
        return r.i32()
    return 0


UNIT_WORD = re.compile(r"\b(%s)\b" % "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True)))
QUOTED = re.compile(r"""(["'])([A-Za-z0-9_]+)\1""")

CONFIG_POST_RAW = r"""
-- ===== Dwarf conversion (generated by converters/iron_caravan_dwf/convert.py) =====
-- Unit compatibility: nothing is blocked by list. A dwarf faction cannot recruit other races anyway,
-- and units added by other mods to dwarf buildings must stay available.
C.blocked_units = {}
-- Chaos Dwarf units keep their caps; extra allowance is bought with Oathgold (C.armaments below).
-- The starting army is dwarf.
do
  local map = {%s}
  for i, key in ipairs(C.starting_army) do C.starting_army[i] = map[key] or key end
end
-- Chaos Dwarf resources that dwarfs do not have.
C.removed_resources = {}
-- Dwarf runesmiths, runelords and other dwarf heroes are part of the faction, not foreign casters.
do
  local keep = {}
  for _, key in ipairs(C.caster_subtypes or {}) do
    if not string.find(key, "_dwf_", 1, true) then keep[#keep + 1] = key end
  end
  C.caster_subtypes = keep
end
C.materials = "gold"
C.armaments = "dwf_oathgold"
C.initial_raw = 0
return C
"""


CONFIG_POST = CONFIG_POST_RAW.replace("%s", ",".join('["%s"]="%s"' % kv for kv in sorted(UNITS.items())), 1)


def patch_lua(name, src):
    crlf = "\r\n" in src
    src = patch_lua_lf(name, src.replace("\r\n", "\n"))
    return src.replace("\n", "\r\n") if crlf else src


def patch_lua_lf(name, src):
    def sub_quoted(m):
        v = m.group(2)
        return m.group(1) + VALUE_MAP.get(v, v) + m.group(1)
    src = QUOTED.sub(sub_quoted, src)
    if name == "script/iron_caravan/campaign.lua":
        # commissioned convoys: comma-joined unit lists -> dwarf units
        src = UNIT_WORD.sub(lambda m: UNITS[m.group(0)], src)
    if name == "script/iron_caravan/hero_services_config.lua":
        src = must_replace(src, '["subtypes"]={', '["subtypes"]={' + "".join(
            '["%s"]="%s",' % (dw, kind) for chd, dw in sorted(HERO_TWINS.items())
            for kind in [re.search(r'\["%s"\]="([a-z_]+)"' % chd, src).group(1)]))
    src = src.replace("wh3_dlc23_chd_conclave", EMPLOYER)
    src = src.replace(CHD_SC, DWF_SC)
    base = name.split("/")[-1]
    if name == "script/iron_caravan/config.lua":
        assert src.startswith("return {"), "config.lua layout changed"
        src = "local C=" + src[len("return "):] + "\n" + CONFIG_POST
        src = src.replace('"opening_employer"]="wh3_dlc23_chd_legion_of_azgorh"', '"opening_employer"]="%s"' % EMPLOYER)
    if name == "script/iron_caravan/ui.lua":
        src = must_replace(src, "{'arms','Armaments','icon_chd_armaments.png'},{'raw','Raw Materials','icon_chd_raw_materials.png'}",
                           "{'arms','Oathgold','icon_oathgold.png'},{'raw','Gold (materials)','icon_income.png'}")
    if base == "campaign.lua" and name.startswith("script/iron_caravan/"):
        src = must_replace(src, "local function ensure_rykarth_mount(character)\n",
                           "local function ensure_rykarth_mount(character)\n    do return end -- dwarf conversion: no Skullcannon\n")
        src = must_replace(src, "local function pooled(key)\n",
                           "local function pooled(key)\n    if key=='gold' then return faction():treasury() end\n")
        src = must_replace(src, "local function transact(key,factor,amount) if amount~=0 then cm:faction_add_pooled_resource(C.faction,key,factor,amount) end end",
                           "local function transact(key,factor,amount) if amount~=0 then if key=='gold' then cm:treasury_mod(C.faction,amount) "
                           "else cm:faction_add_pooled_resource(C.faction,key,factor,amount) end end end")
        src = must_replace(src, "        transact(C.materials,'ic_industry',C.initial_raw-pooled(C.materials))\n",
                           "        if C.materials~='gold' then transact(C.materials,'ic_industry',C.initial_raw-pooled(C.materials)) end\n")
    return src


def must_replace(src, old, new):
    if src.count(old) != 1:
        sys.exit("patch target not found exactly once: %r" % old[:80])
    return src.replace(old, new)


def report(tables):
    pat = re.compile(r"chd|lost_slavers|424817151|skullcannon")
    left = {}
    for t, d in tables.items():
        for r in d["rows"]:
            for k, v in r.items():
                if pat.search(v):
                    left.setdefault((t, k), set()).add(v)
    print("\nremaining Chaos Dwarf references (vanilla records used as is):")
    for (t, k), vs in sorted(left.items()):
        print("  %-58s %-28s %4d e.g. %s" % (t, k, len(vs), sorted(vs)[0][:70]))


if __name__ == "__main__":
    main()
