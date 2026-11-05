#!/usr/bin/env python3
"""
Generates the separate faction "Империя героев" from the ORIGINAL game data (db.pack + local_ru.pack).

  python3 -I mods/hero_empire/_gen/gen_faction.py --db db.pack --loc local_ru.pack --schema schema_wh3.ron

What it builds (all files are  db/<table>/!he_faction.tsv  and  text/db/!he_faction.loc.tsv):
  * culture he_hero_empire + subculture he_sc_hero_empire, based on the Empire (wh_main_emp_empire):
    every row granting something to the Empire culture/subculture is cloned for the new culture
    (campaign-group members are cloned, never modified, so the vanilla Empire is untouched);
  * own building set (copy of the Empire set) and own tech tree (deep copy of the Empire node set);
    the tech tree is assigned to the faction when the startpos is built in the Assembly Kit;
  * the faction he_faction_hero_empire (row based on Reikland, flag of Spine of Sotek);
  * heroes: every generic hero of the game (auto-generated, recruitable, no cap, can equip items)
    whose skill tree is not bound to another subculture -> faction_agent_permitted_subtypes;
    generic Empire lords; agent type UI rows for the culture;
  * "Зал героев" (Hall of Heroes) building chain: unlocks recruitment of all those heroes and raises
    the hero caps per agent type;
  * rune slots: 3 arcane items (runes) per character for the faction, like dwarf factions.

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
from game_data import Pack, load_meta, load_schema  # noqa: E402

MOD = os.path.join(ROOT, "mods", "hero_empire")
FILE = "!he_faction"

FACTION = "he_faction_hero_empire"
TEMPLATE_FACTION = "wh_main_emp_empire"                  # Reikland
FLAG_FROM = "ui\\flags\\wh2_main_dwf_spine_of_sotek_dwarfs"  # the mountain flag
OLD_CUL, OLD_SUB = "wh_main_emp_empire", "wh_main_sc_emp_empire"
NEW_CUL, NEW_SUB = "he_hero_empire", "he_sc_hero_empire"
SUFFIX = "_he"
NAME = "Империя героев"
ADJ = "героический"

AVAIL_SET = "he_bas_hero_empire"
HALL = "he_hall_of_heroes"
HALL_LEVELS = [("Зал героев", 1500, 4, 1), ("Чертог героев", 3000, 6, 2), ("Пантеон героев", 6000, 8, 3)]  # name, cost, turns, cap+

SKIP = {
    # map / startpos content, quest battles, narrative UI
    "start_pos_regions_tables", "battles_tables", "battle_set_pieces_tables", "narrative_viewer_tabs_tables",
    "prefab_types_tables", "intrigue_actions_incidents_junctions_tables", "subculture_conditions_tables",
    # built explicitly
    "factions_tables", "cultures_tables", "cultures_subcultures_tables", "campaign_group_members_tables",
    "frontend_factions_tables", "building_chain_availabilities_tables", "technology_node_sets_tables",
    "faction_agent_permitted_subtypes_tables",
    # event conditions: a second GEN_CND_(SUB)CULTURE row may AND with the Empire one and break Empire events
    "cdir_events_incident_option_junctions_tables", "cdir_events_dilemma_option_junctions_tables",
    "cdir_events_mission_option_junctions_tables", "cdir_event_option_set_items_tables",
    # a cloned art set id would have no character arts behind it (hero art sets are culture-free anyway)
    "campaign_character_art_sets_tables",
    "character_skill_nodes_tables",
}
CRITERIA_PREFIX = "campaign_group_member_criteria_"
HERO_AGENTS = ("champion", "dignitary", "engineer", "runesmith", "spy", "wizard")


def culture_refs(meta, t, v):
    return {n for n, ty, k, ref in meta[t][str(v)]["fields"] if ref == ("cultures_tables", "key")}


def sub_row(row, crefs):
    """Subculture key is unique -> replaced anywhere. The culture key equals a FACTION key
    (wh_main_emp_empire = Reikland), so it is replaced only in fields referencing cultures."""
    out = {}
    for k, v in row.items():
        if v == OLD_SUB:
            out[k] = NEW_SUB
        elif v == OLD_CUL and k in crefs:
            out[k] = NEW_CUL
        else:
            out[k] = v
    return out


def touches(row, crefs):
    return any(v == OLD_SUB or (v == OLD_CUL and k in crefs) for k, v in row.items())


def new_int(seed, existing):
    n = int(hashlib.sha1(seed.encode()).hexdigest()[:7], 16) + 100000000
    while str(n) in existing:
        n += 1
    existing.add(str(n))
    return str(n)


class Out:
    def __init__(self):
        self.tables, self.loc = {}, {}

    def add(self, t, version, header, row):
        self.tables.setdefault(t, (version, header, []))[2].append(row)

    def write(self):
        dbdir = os.path.join(MOD, "db")
        if os.path.isdir(dbdir):
            for d in os.listdir(dbdir):
                p = os.path.join(dbdir, d, FILE + ".tsv")
                if os.path.exists(p):
                    os.remove(p)
                if not os.listdir(os.path.join(dbdir, d)):
                    shutil.rmtree(os.path.join(dbdir, d))
        for t, (version, header, rows) in sorted(self.tables.items()):
            d = os.path.join(dbdir, t)
            os.makedirs(d, exist_ok=True)
            seen = set()
            with open(os.path.join(d, FILE + ".tsv"), "w", encoding="utf-8") as f:
                f.write("\t".join(header) + "\n#%s;%d;db/%s/%s\n" % (t, version, t, FILE))
                for r in rows:
                    line = "\t".join(str(r[h]).replace("\t", "\\t").replace("\n", "\\n") for h in header)
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
    schema, meta = load_schema(a.schema), load_meta(a.schema)

    pack = Pack(a.db)
    tables = {}
    for e in pack.entries:
        parts = e[0].split("/")
        if len(parts) == 3 and parts[0] == "db":
            try:
                _, v, rows = packlib.decode_db(pack.read(e), parts[1], schema)
            except Exception:
                continue
            tables.setdefault(parts[1], {"version": v, "rows": []})["rows"] += rows
    loc = {}
    lp = Pack(a.loc)
    for e in lp.entries:
        if e[0].endswith(".loc"):
            for r in packlib.decode_loc(lp.read(e)):
                loc[r["key"]] = r["text"]

    out, stats = Out(), {}

    def F(t):
        return meta[t][str(tables[t]["version"])]["fields"]

    def hdr(t):
        return [n for n, _, _, _ in F(t)]

    def add(t, row):
        out.add(t, tables[t]["version"], hdr(t), row)
        stats[t] = stats.get(t, 0) + 1

    def loc_copy(t, old_row, new_row):
        lf = meta[t][str(tables[t]["version"])]["loc"]
        keys = [n for n, _, k, _ in F(t) if k]
        base = t[:-len("_tables")]
        ok_, nk_ = "".join(old_row[k] for k in keys), "".join(new_row[k] for k in keys)
        for name in lf:
            old = "%s_%s_%s" % (base, name, ok_)
            if old in loc:
                out.loc["%s_%s_%s" % (base, name, nk_)] = loc[old]

    # ---------------------------------------------------------------- 1. culture + subculture
    for t, src, field, new_key in (("cultures_tables", OLD_CUL, "key", NEW_CUL),
                                   ("cultures_subcultures_tables", OLD_SUB, "subculture", NEW_SUB)):
        rows = tables[t]["rows"]
        old = next(r for r in rows if r[field] == src)
        new = dict(old)
        new[field] = new_key
        if t == "cultures_subcultures_tables":
            new["culture"] = NEW_CUL
        new["index"] = new_int(t + new_key, {r["index"] for r in rows})
        add(t, new)
    out.loc["cultures_name_" + NEW_CUL] = NAME
    out.loc["cultures_subcultures_name_" + NEW_SUB] = NAME
    for k, v in loc.items():
        for old, new in ((OLD_SUB, NEW_SUB), (OLD_CUL, NEW_CUL)):
            if k.startswith(("cultures_", "cultures_subcultures_")) and k.endswith("_" + old):
                out.loc.setdefault(k[: -len(old)] + new, v)

    # ---------------------------------------------------------------- 2. faction
    t = "factions_tables"
    tpl = next(r for r in tables[t]["rows"] if r["key"] == TEMPLATE_FACTION)
    spine = next(r for r in tables[t]["rows"] if r["key"] == "wh2_main_dwf_spine_of_sotek_dwarfs")
    row = dict(tpl)
    row.update({"key": FACTION, "subculture": NEW_SUB, "flags_path": FLAG_FROM,
                "index": new_int(t + FACTION, {r["index"] for r in tables[t]["rows"]})})
    for k in ("primary_colour_r", "primary_colour_g", "primary_colour_b", "secondary_colour_r", "secondary_colour_g",
              "secondary_colour_b", "uniform_colour_primary", "uniform_colour_secondary", "uniform_colour_tertiary",
              "banner_colour_primary", "banner_colour_secondary", "banner_colour_tertiary", "primary_colour"):
        if k in spine:
            row[k] = spine[k]
    add(t, row)
    out.loc.update({"factions_screen_name_" + FACTION: NAME, "factions_screen_name_when_rebels_" + FACTION: "Мятежники Империи героев",
                    "factions_screen_adjective_" + FACTION: ADJ, "factions_attack_desc_" + FACTION: "",
                    "factions_defend_desc_" + FACTION: ""})

    # ---------------------------------------------------------------- 3. campaign-group members (clone, never modify)
    crit = [t for t in tables if t.startswith(CRITERIA_PREFIX)]
    members = set()
    for t in crit:
        cr = culture_refs(meta, t, tables[t]["version"])
        for r in tables[t]["rows"]:
            if touches(r, cr):
                members.add(r["member"])
    for r in tables[CRITERIA_PREFIX + "factions_tables"]["rows"]:   # bound to another specific faction -> never ours
        if r["member"] in members and r["context"] == "ACTOR":
            members.discard(r["member"])
    for t in crit:
        cr = culture_refs(meta, t, tables[t]["version"])
        for r in tables[t]["rows"]:
            if r["member"] in members:
                nr = sub_row(r, cr)
                nr["member"] = r["member"] + SUFFIX
                add(t, nr)
    for r in tables["campaign_group_members_tables"]["rows"]:
        if r["id"] in members:
            nr = dict(r)
            nr["id"] = r["id"] + SUFFIX
            add("campaign_group_members_tables", nr)

    # ---------------------------------------------------------------- 4. generic clone of every other Empire row
    for t, data in sorted(tables.items()):
        if t in SKIP or t.startswith(CRITERIA_PREFIX):
            continue
        cr = culture_refs(meta, t, data["version"])
        keyf = [(n, ty) for n, ty, k, _ in F(t) if k]
        existing = {tuple(r[n] for n, _ in keyf) for r in data["rows"]}
        for r in data["rows"]:
            if not touches(r, cr):
                continue
            nr = sub_row(r, cr)
            nk = tuple(nr[n] for n, _ in keyf)
            if keyf and nk in existing:
                n0, ty0 = keyf[0]
                nr[n0] = new_int(t + "|".join(r[n] for n, _ in keyf), {x[0] for x in existing}) if ty0.startswith("I") else r[n0] + SUFFIX
                nk = tuple(nr[n] for n, _ in keyf)
            existing.add(nk)
            add(t, nr)
            loc_copy(t, r, nr)

    # ---------------------------------------------------------------- 5. building set: copy of the Empire set + Hall of Heroes
    emp_set = next(r["set_id"] for r in tables["building_chain_availabilities_tables"]["rows"]
                   if r["culture"] == OLD_CUL and r["sub_culture"] == OLD_SUB and not r["faction"] and not r["campaign"])
    add("building_chain_availability_set_ids_tables", {"id": AVAIL_SET})
    add("building_chain_availabilities_tables", {"set_id": AVAIL_SET, "culture": NEW_CUL, "faction": "", "id": AVAIL_SET,
                                                 "sub_culture": NEW_SUB, "campaign": ""})
    for r in tables["building_chain_availability_sets_tables"]["rows"]:
        if r["id"] == emp_set:
            add("building_chain_availability_sets_tables", {"building_chain": r["building_chain"], "id": AVAIL_SET})
    add("building_chain_availability_sets_tables", {"building_chain": HALL, "id": AVAIL_SET})

    # ---------------------------------------------------------------- 6. tech tree: deep copy of the Empire node set
    sets = [r for r in tables["technology_node_sets_tables"]["rows"]
            if r["culture"] == OLD_CUL and not r["faction_key"] and not r["campaign_key"]]
    set_map = {}
    for r in sets:
        nr = dict(r)
        nr.update({"culture": NEW_CUL, "subculture": NEW_SUB, "key": r["key"] + SUFFIX})
        set_map[r["key"]] = nr["key"]
        add("technology_node_sets_tables", nr)
    node_map = {r["key"]: r["key"] + SUFFIX for r in tables["technology_nodes_tables"]["rows"] if r["technology_node_set"] in set_map}
    refmaps = {"technology_nodes_tables": node_map, "technology_node_sets_tables": set_map}
    for t, data in sorted(tables.items()):
        rf = [(n, ref[0]) for n, _, _, ref in F(t) if ref and ref[0] in refmaps and ref[1] == "key"]
        if not rf:
            continue
        for r in data["rows"]:
            if not any(r[n] in refmaps[rt] for n, rt in rf) and not (t == "technology_nodes_tables" and r["key"] in node_map):
                continue
            nr = dict(r)
            for n, rt in rf:
                nr[n] = refmaps[rt].get(r[n], r[n])
            if t == "technology_nodes_tables":
                nr["key"] = node_map[r["key"]]
            add(t, nr)
            loc_copy(t, r, nr)

    # ---------------------------------------------------------------- 7. heroes and lords
    subs = {r["key"]: r for r in tables["agent_subtypes_tables"]["rows"]}
    restricted = {}
    for r in tables["character_skill_node_sets_tables"]["rows"]:
        restricted.setdefault(r["agent_subtype_key"], []).append(bool(r["subculture"] or r["faction_key"]))
    hero_types = {}
    for r in tables["faction_agent_permitted_subtypes_tables"]["rows"]:
        if r["agent"] in HERO_AGENTS:
            hero_types.setdefault(r["subtype"], set()).add(r["agent"])

    def generic(s):
        x = subs.get(s)
        return (x and x["auto_generate"] == "true" and x["recruitable"] == "true" and x["cap"] == "-1"
                and x["can_equip_ancillaries"] == "true" and s in restricted and not all(restricted[s]))

    heroes = sorted(s for s in hero_types if generic(s))
    skipped = sorted(s for s in hero_types if not generic(s))
    for s in heroes:
        for agent in sorted(hero_types[s]):
            add("faction_agent_permitted_subtypes_tables", {"agent": agent, "faction": FACTION, "subtype": s, "mod_disabled": "false"})
    lords = sorted({r["subtype"] for r in tables["faction_agent_permitted_subtypes_tables"]["rows"]
                    if r["faction"] == TEMPLATE_FACTION and r["agent"] in ("general", "colonel", "minister")
                    and subs.get(r["subtype"], {}).get("auto_generate") == "true" and subs[r["subtype"]]["cap"] == "-1"})
    for r in tables["faction_agent_permitted_subtypes_tables"]["rows"]:
        if r["faction"] == TEMPLATE_FACTION and r["subtype"] in lords and r["agent"] in ("general", "colonel", "minister"):
            add("faction_agent_permitted_subtypes_tables", dict(r, faction=FACTION))

    # availability effect per hero: the one most used by vanilla buildings
    av = {}
    for r in tables["effect_bonus_value_agent_subtype_junctions_tables"]["rows"]:
        if r["bonus_value_id"] == "availability":
            av.setdefault(r["subtype"], []).append(r["effect"])
    usage = {}
    for r in tables["building_effects_junction_tables"]["rows"]:
        usage[r["effect"]] = usage.get(r["effect"], 0) + 1
    hero_effects = {}
    for s in heroes:
        if s in av:
            hero_effects[s] = max(av[s], key=lambda e: (usage.get(e, 0), "hidden" not in e, e))

    # ---------------------------------------------------------------- 8. Hall of Heroes
    cap_effects = {}
    for agent in HERO_AGENTS:
        eff = "he_effect_agent_cap_increase_" + agent
        cap_effects[agent] = eff
        add("effects_tables", {"effect": eff, "icon": agent + ".png", "priority": "102", "icon_negative": agent + ".png",
                               "category": "campaign", "is_positive_value_good": "true"})
        add("effect_bonus_value_agent_junction_tables", {"effect": eff, "bonus_value_id": "cap", "agent": agent})
        out.loc["effects_description_" + eff] = "Лимит героев (%s): %%+n" % agent
    add("building_superchains_tables", {"key": "he_sch_" + HALL})
    add("building_chains_tables", {"key": HALL, "tech_category_tab": "", "tech_category_position": "", "chain_category": "military",
                                   "in_encyclopedia": "false", "building_superchain": "he_sch_" + HALL, "optional_tier_icon": "",
                                   "optional_sort_order": "90", "optional_required_horde_commander": "", "can_be_dismantled": "true",
                                   "is_foreign_slot_chain": "false"})
    add("building_instances_tables", {"key": HALL, "num_instances": "1"})
    for i, (lname, cost, turns, cap) in enumerate(HALL_LEVELS):
        lvl = "%s_%d" % (HALL, i + 1)
        tpl_level = next(r for r in tables["building_levels_tables"]["rows"])
        lv = {k: "" for k in tpl_level}
        lv.update({"level_name": lvl, "chain": HALL, "level": str(i), "create_time": str(turns), "create_cost": str(cost),
                   "upkeep_cost": "0", "only_in_capital": "true", "faction_unique": "true", "can_convert": "true",
                   "building_instance_key": HALL, "should_show_building_level_in_ui_for_technology": "false",
                   "health_override": "0.0", "development_point_cost": "0", "can_be_damaged": "true",
                   "primary_slot_building_building_level_requirement": "0", "visible_in_ui": "true", "food_cost": "0",
                   "slave_cap_contribution": "0", "additional_loot_value": "0", "split_chain_sort_order": "-1",
                   "override_startpos_settlement_display_building": "false"})
        add("building_levels_tables", lv)
        if i:
            add("building_upgrades_junction_tables", {"from": "%s_%d" % (HALL, i), "to": lvl})
        add("building_culture_variants_tables", {"building": lvl, "culture": NEW_CUL, "description": "wh_main_PLACEHOLDER",
                                                 "icon": "dwarf_guild_worshops", "subculture": "", "faction": "", "disables": "false",
                                                 "short_description": lvl, "display_tooltip": "true", "building_frame_override": ""})
        for s, eff in sorted(hero_effects.items()):
            add("building_effects_junction_tables", {"building": lvl, "effect": eff, "effect_scope": "province_to_province_own_unseen",
                                                     "value": "1.0", "value_damaged": "1.0", "value_ruined": "0.0", "context_requirement": ""})
        for agent, eff in cap_effects.items():
            add("building_effects_junction_tables", {"building": lvl, "effect": eff, "effect_scope": "faction_to_faction_own_unseen",
                                                     "value": "%.1f" % cap, "value_damaged": "%.1f" % cap, "value_ruined": "0.0",
                                                     "context_requirement": ""})
        out.loc["building_culture_variants_name_%s%s" % (lvl, NEW_CUL)] = lname
        out.loc["building_short_description_texts_text_" + lvl] = (
            "Открывает найм всех героев Империи героев (%d видов) в провинции столицы. Лимит героев каждого типа +%d. "
            "Стоимость: %d золота." % (len(hero_effects), cap, cost))
    out.loc["building_chains_chain_tooltip_" + HALL] = "Зал героев"
    out.loc["building_chains_encyclopedia_name_" + HALL] = "Зал героев"
    out.loc["building_chains_encyclopedia_description_" + HALL] = "Сюда стекаются герои со всего света, чтобы служить Империи героев."

    # ---------------------------------------------------------------- 9. rune slots, like dwarf factions
    t = "ancillaries_categories_faction_junctions_tables"
    for r in tables[t]["rows"]:
        if r["faction"] == "wh2_main_dwf_spine_of_sotek_dwarfs":
            add(t, dict(r, faction=FACTION))

    # ---------------------------------------------------------------- 10. campaign selection screen
    add("frontend_factions_tables", {"faction": FACTION, "video": "test_movie_warhammer", "sort_order": "1711"})
    add("frontend_faction_groups_to_factions_tables", {"faction_group": "order", "faction_key": FACTION, "is_major_faction": "true",
                                                       "sort_order": "1711", "show_in_frontend": "true"})
    leader = {k: "" for k in hdr("frontend_faction_leaders_tables")}
    leader.update({"uniform": "composite_scene\\lord_selection\\empire_provinces\\emperor_karl_franz.csc", "x_offset": "0.0",
                   "y_offset": "0.0", "key": "he_leader_hero_empire", "character_image": FLAG_FROM + "\\mon_256.png",
                   "video": "Front_end_selection_movies/franz_front_end", "loading_screen_image": "ui/loading_ui/load_images/campaign_empire1.png",
                   "override_force_location_x": "-1.0", "override_force_location_y": "-1.0", "voiceover": "wh_main_vo_actor_Empire_KarlFranz",
                   "show_full_intro_option": "false", "difficulty": "normal", "startpos_map": "default",
                   "agent_subtype_record": "wh_main_emp_lord", "faction": FACTION})
    add("frontend_faction_leaders_tables", leader)
    for fld in meta["frontend_faction_leaders_tables"][str(tables["frontend_faction_leaders_tables"]["version"])]["loc"]:
        out.loc["frontend_faction_leaders_%s_he_leader_hero_empire" % fld] = NAME

    out.write()
    for t, n in sorted(stats.items(), key=lambda x: -x[1])[:25]:
        print("%6d %s" % (n, t))
    print("tables: %d, rows: %d, loc: %d" % (len(out.tables), sum(stats.values()), len(out.loc)))
    print("heroes: %d (with recruitment effect: %d), skipped hero types: %d, lords: %s" %
          (len(heroes), len(hero_effects), len(skipped), ", ".join(lords)))


if __name__ == "__main__":
    main()
