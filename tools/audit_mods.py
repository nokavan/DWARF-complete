#!/usr/bin/env python3
"""
Checks every mod in mods/ against the ORIGINAL game data (db.pack from the private "game-data" release).

  python3 tools/audit_mods.py DB_PACK SCHEMA_RON [MODS_ROOT ...]

Checks:
  * every mod table uses a version that the live game uses;
  * effect keys, effect scopes and context expressions used by buildings / effect bundles exist
    (in the game or in the mod itself);
  * effect keys/scopes written in Lua (`key = "...", scope = "..."`) exist;
  * slot set types, pooled resources, agent types, factions referenced by the mods exist.
Exit code 1 on any error.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packlib  # noqa: E402
from game_data import Pack, load_meta, load_schema  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    pack = Pack(sys.argv[1])
    schema = load_schema(sys.argv[2])
    meta = load_meta(sys.argv[2])
    versions, cache = {}, {}

    def header_version(data):
        r = packlib.Reader(data)
        if data[:4] == packlib.GUID_MARKER:
            r.take(4)
            r.str_u16()
        if data[r.p:r.p + 4] == packlib.VERSION_MARKER:
            r.take(4)
            return r.i32()
        return 0

    db = {}
    for e in pack.entries:
        parts = e[0].split("/")
        if len(parts) == 3 and parts[0] == "db":
            db.setdefault(parts[1], []).append(e)

    def game_rows(table):
        if table not in cache:
            rows = []
            for e in db.get(table, []):
                rows += packlib.decode_db(pack.read(e), table, schema)[2]
            cache[table] = rows
        return cache[table]

    def game_versions(table):
        if table not in versions:
            versions[table] = {header_version(pack.read(e)) for e in db.get(table, [])}
        return versions[table]

    errors, warnings = [], []
    roots = sys.argv[3:] or [os.path.join(ROOT, "mods")]
    mod_dirs = sorted(d for r in roots for d in glob.glob(os.path.join(r, "*")) if os.path.isdir(d))
    for mod_dir in mod_dirs:
        mod = os.path.basename(mod_dir)
        mod_rows = {}
        # records defined by required mods (e.g. MIXER): "table<TAB>field<TAB>value" lines
        external = {}
        ext_file = os.path.join(mod_dir, "_external_keys.tsv")
        if os.path.exists(ext_file):
            for line in open(ext_file, encoding="utf-8"):
                t, fld, val = line.rstrip("\n").split("\t")
                external.setdefault((t, fld), set()).add(val)
        for f in glob.glob(os.path.join(mod_dir, "db", "*", "*.tsv")):
            table, version, _, _, rows = packlib.read_tsv(f)
            mod_rows.setdefault(table, []).extend(rows)
            gv = game_versions(table)
            if not gv:
                errors.append("%s: table %s does not exist in the game" % (mod, table))
            elif version not in gv:
                errors.append("%s: %s is v%d, the game uses %s" % (mod, table, version, sorted(gv)))

        def keyset(table, field):
            return {r[field] for r in game_rows(table)} | {r[field] for r in mod_rows.get(table, [])}

        effects = keyset("effects_tables", "effect")
        scopes = keyset("campaign_effect_scopes_tables", "key")
        contexts = keyset("building_effect_context_expressions_tables", "key")

        def check_effect(where, eff, scope, ctx=""):
            if eff not in effects:
                errors.append("%s: %s: unknown effect %s" % (mod, where, eff))
            if scope not in scopes:
                errors.append("%s: %s: unknown effect scope %s" % (mod, where, scope))
            if ctx and ctx not in contexts:
                errors.append("%s: %s: unknown context expression %s" % (mod, where, ctx))

        for r in mod_rows.get("building_effects_junction_tables", []):
            check_effect(r["building"], r["effect"], r["effect_scope"], r["context_requirement"])
        for r in mod_rows.get("effect_bundles_to_effects_junctions_tables", []):
            check_effect(r["effect_bundle_key"], r["effect_key"], r["effect_scope"])
        for lua in glob.glob(os.path.join(mod_dir, "script", "**", "*.lua"), recursive=True):
            src = open(lua, encoding="utf-8").read()
            for eff, scope in re.findall(r'key\s*=\s*"([A-Za-z0-9_]+)",\s*scope\s*=\s*"([A-Za-z0-9_]+)"', src):
                check_effect(os.path.basename(lua), eff, scope)

        for r in mod_rows.get("slot_sets_tables", []):
            if r["type"] not in keyset("slot_set_types_tables", "key"):
                errors.append("%s: unknown slot set type %s" % (mod, r["type"]))
        for r in mod_rows.get("pooled_resource_factor_junctions_tables", []):
            if r["resource"] not in keyset("pooled_resources_tables", "key"):
                errors.append("%s: unknown pooled resource %s" % (mod, r["resource"]))
        factions = keyset("factions_tables", "key") | external.get(("factions_tables", "key"), set())
        for table, field in (("building_culture_variants_tables", "faction"), ("building_chain_availabilities_tables", "faction")):
            for r in mod_rows.get(table, []):
                if r[field] and r[field] not in factions:
                    errors.append("%s: %s: unknown faction %s" % (mod, table, r[field]))
        icons = {r["icon"] for r in game_rows("building_culture_variants_tables")}
        for r in mod_rows.get("building_culture_variants_tables", []):
            if r["icon"] and r["icon"] not in icons:
                warnings.append("%s: building icon %s is not used by any vanilla building" % (mod, r["icon"]))
        # a faction/culture building set REPLACES the broader one, so it must be a full set
        chains = {}
        for r in game_rows("building_chain_availability_sets_tables") + mod_rows.get("building_chain_availability_sets_tables", []):
            chains.setdefault(r["id"], set()).add(r["building_chain"])
        for r in mod_rows.get("building_chain_availabilities_tables", []):
            n = len(chains.get(r["set_id"], ()))
            if n < 50:
                errors.append("%s: building set %s has only %d chains but is assigned to %s - it would replace the "
                              "whole culture building set" % (mod, r["set_id"], n, r["faction"] or r["sub_culture"] or r["culture"]))
        # rune/item slots are per faction; a subtype override would cut them for new heroes
        overrides = {r["agent_subtype"] for r in game_rows("ancillaries_categories_agent_subtype_override_junctions_tables")
                     + mod_rows.get("ancillaries_categories_agent_subtype_override_junctions_tables", [])}
        for r in mod_rows.get("faction_agent_permitted_subtypes_tables", []):
            if r["subtype"] in overrides:
                errors.append("%s: hero %s has an ancillary category override - it would not get the faction's rune slots"
                              % (mod, r["subtype"]))
        agents = {r["agent"] for r in game_rows("faction_agent_permitted_subtypes_tables")}
        for r in mod_rows.get("agent_actions_tables", []):
            if r["agent"] not in agents:
                errors.append("%s: agent action %s: unknown agent type %s" % (mod, r["unique_id"], r["agent"]))
        # every reference field must point to an existing game or mod record
        mod_versions = {}
        for f in glob.glob(os.path.join(mod_dir, "db", "*", "*.tsv")):
            t, v, _, _, _ = packlib.read_tsv(f)
            mod_versions[t] = v
        ref_index = {}

        def ref_values(table, field):
            if (table, field) not in ref_index:
                vals = {r[field] for r in mod_rows.get(table, []) if field in r}
                if table in db:
                    vals |= {r[field] for r in game_rows(table) if field in r}
                ref_index[(table, field)] = vals | external.get((table, field), set())
            return ref_index[(table, field)]

        broken = 0
        for t, rows in mod_rows.items():
            for name, _, _, ref in meta[t][str(mod_versions[t])]["fields"]:
                if not ref or ref[0] not in schema or (ref[0] not in db and ref[0] not in mod_rows):
                    continue
                known = ref_values(*ref)
                for r in rows:
                    v = r.get(name, "")
                    if v and v not in known:
                        broken += 1
                        if broken <= 40:
                            errors.append("%s: %s.%s = %s -> no such %s.%s" % (mod, t, name, v, ref[0], ref[1]))
        if broken > 40:
            errors.append("%s: ... %d broken references in total" % (mod, broken))
        print("%-24s %3d tables checked" % (mod, len(mod_rows)))

    for w in sorted(set(warnings)):
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    print("audit: %d errors, %d warnings" % (len(errors), len(set(warnings))))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
