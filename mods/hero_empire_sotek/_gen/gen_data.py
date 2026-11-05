#!/usr/bin/env python3
"""
Generates the DB/loc TSVs of the "Подворье" (allied foreign-slot compound) prototype.
Run from repo root:  python3 mods/hero_empire_sotek/_gen/gen_data.py

Table versions are the ones used by working WH3 mod packs (verified byte-for-byte
against RPFM output). Effect keys + effect scopes are only pairs seen in working packs.
"""
import os

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "hero_empire_sotek"
FACTION = "wh2_main_dwf_spine_of_sotek_dwarfs"

SLOT_TEMPLATE = "he_pod_slot"
SLOT_SET = "he_slot_set_podvorye"
CHAIN_SET = "he_pod_chain_set"
AVAIL_SET = "he_bas_hero_empire"   # culture building set, defined by gen_culture.py
SLOT_COUNT = 5
# slot_set_types (vanilla): VAMPIRE_COVEN is the type of Neferata's covens, which also live in allied regions.
SLOT_SET_TYPE = "VAMPIRE_COVEN"
ALLIED = "CovenRegionOwnerAllied"   # vanilla context expression (used by covens)

LEVEL_COST = [600, 1200, 2000]
LEVEL_TIME = [2, 3, 4]

# (effect, scope, [v1, v2, v3], context)
HOST_REGION = "foreign_building_to_region_own_visible"
HOST_PROVINCE = "foreign_building_to_province_unseen"
HOST_ARMIES = "foreign_building_to_host_faction_armies"
SELF_BUILDING = "foreign_building_to_foreign_building_own"
SELF_REGION_DIPLO = "foreign_building_to_region_own"

CHAINS = [
    {
        "id": "trade", "icon": "dwarf_guild_worshops",
        "name": "Торговый двор", "levels": ["Торговый двор", "Торговая гильдия", "Подгорная биржа"],
        "lore": "Купцы Хребта Сотека ведут дела в городе союзника — и обе стороны богатеют.",
        "short": ["Доход региона союзника +10%%, рост провинции +5. Нам: +100 золота за ход, отношения с союзником растут.",
                  "Доход региона союзника +20%%, рост +10. Нам: +250 золота и 5%% дохода региона.",
                  "Доход региона союзника +30%%, рост +15. Нам: +400 золота и 10%% дохода региона."],
        "effects": [
            ("wh_main_effect_economy_gdp_mod_all", HOST_REGION, [10, 20, 30], ""),
            ("wh_main_effect_province_growth_building", HOST_PROVINCE, [5, 10, 15], ""),
            ("wh_main_effect_economy_gdp_other", SELF_BUILDING, [100, 250, 400], ""),
            ("wh2_dlc11_effect_percentage_region_income", SELF_BUILDING, [0, 5, 10], ""),
            ("wh3_main_effect_foreign_slot_diplomatic_change_positive", SELF_REGION_DIPLO, [2, 3, 4], ""),
        ],
    },
    {
        "id": "bastion", "icon": "chd_tower_ballistics",
        "name": "Бастион", "levels": ["Сторожевой пост", "Бастион", "Подгорная цитадель"],
        "lore": "Гномьи наставники учат ополчение союзника держать стены.",
        "short": ["Порядок в провинции союзника +3, очки найма +1. Наши герои действуют успешнее (+10%%).",
                  "Порядок +6, очки найма +1, нанятые отряды союзника получают +1 ранг. Успех героев +15%%.",
                  "Порядок +10, очки найма +2, отряды союзника +2 ранга. Успех героев +20%%."],
        "effects": [
            ("wh_main_effect_public_order_base", HOST_PROVINCE, [3, 6, 10], ""),
            ("wh_main_effect_unit_recruitment_points", HOST_PROVINCE, [1, 1, 2], ""),
            ("wh3_dlc29_effect_force_recruit_rank_all_including_merc", HOST_PROVINCE, [0, 1, 2], ""),
            ("wh_main_effect_agent_action_success_chance", "foreign_building_to_character_own", [10, 15, 20], ""),
        ],
    },
    {
        "id": "trail", "icon": "wood_elves_temple_waystones",
        "name": "Застава троп", "levels": ["Застава троп", "Тропяная станция", "Узел подгорных троп"],
        "lore": "Тайные тропы связывают подворья с Хребтом Сотека.",
        "short": ["Армии союзника: дальность хода +5%%. Наши армии в регионе: +10%%.",
                  "Армии союзника: +10%%. Наши армии в регионе: +20%%, пополнение на чужой земле.",
                  "Армии союзника: +15%% и пополнение на чужой земле. Наши армии в регионе: +30%%."],
        "effects": [
            ("wh_main_effect_force_all_campaign_movement_range", HOST_ARMIES, [5, 10, 15], ALLIED),
            ("wh2_main_effect_force_own_campaign_movement_range", "foreign_building_to_force_own_regionwide", [10, 20, 30], ""),
            ("wh_main_effect_force_army_campaign_enable_replenishment_in_foreign_territory", "foreign_building_to_force_own_regionwide", [0, 1, 1], ""),
            ("wh_main_effect_force_army_campaign_enable_replenishment_in_foreign_territory", HOST_ARMIES, [0, 0, 1], ALLIED),
        ],
    },
    {
        "id": "infirmary", "icon": "dwarf_engineering",
        "name": "Лазарет", "levels": ["Лазарет", "Госпиталь Валайи", "Чертоги исцеления"],
        "lore": "Жрицы Валайи лечат раненых — своих и союзных.",
        "short": ["Армии союзника: пополнение +5%%. Наши герои: время ранения −1 ход.",
                  "Армии союзника: пополнение +10%%, найм −5%%. Раны героев −2 хода.",
                  "Армии союзника: пополнение +15%%, найм −10%%. Раны героев −3 хода."],
        "effects": [
            ("wh_main_effect_force_all_campaign_replenishment_rate", HOST_ARMIES, [5, 10, 15], ALLIED),
            ("wh_main_effect_force_all_campaign_recruitment_cost_all", HOST_ARMIES, [0, -5, -10], ALLIED),
            ("wh_main_effect_character_wound_recovery_time_mod", "foreign_building_to_character_own_any", [-1, -2, -3], ""),
        ],
    },
    {
        "id": "heroes", "icon": "dwarf_guild_worshops",
        "name": "Зал героев", "levels": ["Зал героев", "Зал Ветеранов", "Зал Легенд"],
        "lore": "Здесь герои Хребта Сотека учатся бок о бок с союзными воинами.",
        "short": ["Наши герои: +100 опыта за ход. Армии союзника: опыт отрядов +5%%. Исследования +5%%.",
                  "Наши герои: +200 опыта. Опыт отрядов союзника +10%%. Исследования +10%%.",
                  "Наши герои: +300 опыта. Опыт отрядов союзника +15%%. Исследования +15%%."],
        "effects": [
            ("wh3_main_effect_character_experience_per_turn", "foreign_building_to_character_own_any", [100, 200, 300], ""),
            ("wh3_dlc20_effect_xp_gain_all_units", HOST_ARMIES, [5, 10, 15], ALLIED),
            ("wh_main_effect_technology_research_rate_mod", "foreign_building_to_faction_own_unseen", [5, 10, 15], ""),
        ],
    },
]

DILEMMA = "he_dilemma_found_podvorye"
ACTION = "he_agent_action_engineer_hinder_settlement_found_podvorye"
ACTION_RESULT = "he_agent_action_hinder_settlement_success_found_podvorye"
ENABLE_EFFECT = "he_effect_agent_action_enable_engineer_found_podvorye"
FEATURE_BUNDLE = "he_bundle_podvorye_feature"
IDENTITY_BUNDLE = "he_bundle_faction_identity"
FOUND_COST = 1500


def tsv(rel, table, version, header, rows):
    path = os.path.join(MOD, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pack_path = rel[:-4] if rel.startswith("db/") else rel[:-4]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        f.write("#%s;%d;%s\n" % (table, version, pack_path))
        for r in rows:
            f.write("\t".join(str(c) for c in r) + "\n")


def db(table, version, header, rows, name=NAME):
    tsv("db/%s/%s.tsv" % (table, name), table, version, header, rows)


def main():
    loc = []
    lvl = lambda c, i: "he_pod_%s_%d" % (c["id"], i + 1)
    chain = lambda c: "he_pod_%s" % c["id"]

    db("slot_templates_tables", 0, ["key", "resource"], [[SLOT_TEMPLATE, ""]])
    db("slot_sets_tables", 1, ["key", "composite_scene", "type", "non_owner_composite_scene"],
       [[SLOT_SET, "", SLOT_SET_TYPE, ""]])
    db("slot_set_items_tables", 2, ["id", "slot_template", "slot_type", "slot_set", "building_level"],
       [[730100001 + i, SLOT_TEMPLATE, "foreign", SLOT_SET, ""] for i in range(SLOT_COUNT)])
    db("slot_template_permitted_building_chains_tables", 0, ["chain", "chain_set", "remove", "slot_template", "super_chain"],
       [["", CHAIN_SET, "false", SLOT_TEMPLATE, ""]])
    db("building_chain_sets_tables", 0, ["key", "parent_set"], [[CHAIN_SET, ""]])
    db("building_chain_set_items_tables", 0, ["chain", "remove", "set", "super_chain"],
       [[chain(c), "false", CHAIN_SET, ""] for c in CHAINS])
    db("building_superchains_tables", 0, ["key"], [["he_sch_pod_" + c["id"]] for c in CHAINS])
    db("building_chains_tables", 10,
       ["key", "tech_category_tab", "tech_category_position", "chain_category", "in_encyclopedia", "building_superchain",
        "optional_tier_icon", "optional_sort_order", "optional_required_horde_commander", "can_be_dismantled", "is_foreign_slot_chain"],
       [[chain(c), "", "", "military", "false", "he_sch_pod_" + c["id"], "", 80 + i, "", "true", "true"] for i, c in enumerate(CHAINS)])
    levels, upgrades, variants, effects = [], [], [], []
    for c in CHAINS:
        for i in range(3):
            levels.append([lvl(c, i), chain(c), i, LEVEL_TIME[i], LEVEL_COST[i], 0, "", "false", "false", "", "", "true", chain(c),
                           "false", "0.0", 0, "true", 0, "", "true", 0, 0, "", 0, "", -1, "false"])
            if i < 2:
                upgrades.append([lvl(c, i), lvl(c, i + 1)])
            variants.append([lvl(c, i), "", "wh_main_PLACEHOLDER", c["icon"], "", FACTION, "false", lvl(c, i), "true", ""])
            for eff, scope, vals, ctx in c["effects"]:
                if vals[i] != 0:
                    v = "%.1f" % vals[i]
                    effects.append([lvl(c, i), eff, scope, v, v, v, ctx])
            loc.append(("building_culture_variants_name_%s%s" % (lvl(c, i), FACTION), c["levels"][i]))
            loc.append(("building_short_description_texts_text_%s" % lvl(c, i),
                        (c["short"][i] % ()) + " Стоимость: %d золота." % LEVEL_COST[i]))
        loc.append(("building_chains_chain_tooltip_%s" % chain(c), c["name"]))
        loc.append(("building_chains_encyclopedia_name_%s" % chain(c), c["name"]))
        loc.append(("building_chains_encyclopedia_description_%s" % chain(c), c["lore"]))
    db("building_levels_tables", 3,
       ["level_name", "chain", "level", "create_time", "create_cost", "upkeep_cost", "commodity", "only_in_capital", "faction_unique",
        "first_in_world_bundle", "resource_requirement", "can_convert", "building_instance_key",
        "should_show_building_level_in_ui_for_technology", "health_override", "development_point_cost", "can_be_damaged",
        "primary_slot_building_building_level_requirement", "audio_building_type", "visible_in_ui", "food_cost",
        "slave_cap_contribution", "resource_cost", "additional_loot_value", "resource_transaction_on_complete",
        "split_chain_sort_order", "override_startpos_settlement_display_building"], levels)
    db("building_upgrades_junction_tables", 0, ["from", "to"], upgrades)
    db("building_instances_tables", 0, ["key", "num_instances"], [[chain(c), 1] for c in CHAINS])
    db("building_culture_variants_tables", 5,
       ["building", "culture", "description", "icon", "subculture", "faction", "disables", "short_description",
        "display_tooltip", "building_frame_override"], variants)
    db("building_effects_junction_tables", 0,
       ["building", "effect", "effect_scope", "value", "value_damaged", "value_ruined", "context_requirement"], effects)
    db("building_chain_availability_sets_tables", 0, ["building_chain", "id"], [[chain(c), AVAIL_SET] for c in CHAINS])

    # founding dilemma
    db("dilemmas_tables", 3,
       ["generate", "key", "localised_description", "localised_title", "ui_image", "prioritized", "event_category",
        "sound_popup_override", "sound_click_override", "override_icon", "is_large_dilemma"],
       [["false", DILEMMA, "", "", "", "true", "", "", "", "", "false"]])

    # native hero action "Основать подворье" — copied from vanilla wh3_dlc29 "establish coven" chain
    db("agent_actions_tables", 12,
       ["ability", "agent", "attribute", "cannot_fail", "critical_failure", "critical_success", "failure", "opportune_failure",
        "success", "localised_action_name", "localised_action_description", "unique_id", "target_attribute",
        "critical_success_proportion_modifier", "opportune_failure_proportion_modifier", "critical_failure_proportion_modifier",
        "chance_of_success", "voiceover", "icon_path", "show_action_info_in_ui", "subculture", "succeed_always_override", "order"],
       [["hinder_settlement", "engineer", "authority"] + [ACTION_RESULT] * 6 +
        ["", "", ACTION, "authority", "0.0", "0.0", "0.0", 100, "vo_campaign_action_enemy_settlement",
         "ui/campaign ui/effect_bundles/he_podvorye.png", "true", "", "false", 0]])
    db("action_results_tables", 1,
       ["actor_effect_bundle", "key", "target_effect_bundle", "actor_effect_bundle_turns", "target_effect_bundle_turns"],
       [["wh_main_bundle_dummy_character", ACTION_RESULT, "wh_main_bundle_agent_action_spy_hinder_settlement_success_target", 1, 1]])
    db("action_results_additional_outcomes_tables", 6,
       ["outcome", "action_result_key", "value", "effect_record", "effect_scope_record", "key", "FIXME",
        "opportune_failure_weighting", "affects_target", "advancement_stage", "create_foreign_slot_set", "sort_order"],
       [["establish_foreign_slots_province_capital_only", ACTION_RESULT, "1.0", "", "", ACTION_RESULT, "true", 0, "true",
         "start_round_completed", SLOT_SET, 0]])
    db("effects_tables", 0, ["effect", "icon", "priority", "icon_negative", "category", "is_positive_value_good"],
       [[ENABLE_EFFECT, "agent.png", 1, "agent.png", "campaign", "true"]])
    db("effect_bonus_value_agent_action_record_junctions_tables", 0, ["bonus_value_id", "effect", "agent_action_record"],
       [["active", ENABLE_EFFECT, ACTION]])
    db("effect_bundles_tables", 4,
       ["key", "localised_description", "localised_title", "bundle_target", "priority", "ui_icon", "is_global_effect",
        "show_in_3d_space", "owner_only"],
       [[FEATURE_BUNDLE, "", "", "faction", 1, "he_podvorye.png", "false", "false", "true"],
        [IDENTITY_BUNDLE, "", "", "faction", 1, "he_podvorye.png", "false", "false", "true"]])
    db("effect_bundles_to_effects_junctions_tables", 3,
       ["effect_bundle_key", "effect_key", "effect_scope", "value", "advancement_stage"],
       [[FEATURE_BUNDLE, ENABLE_EFFECT, "faction_to_character_own", "1.0", "start_turn_completed"],
        # CA's own switch (used by the Underdeep building "grudges_2_a"): bonus value dwf_grudge_feature_off
        # stops the Grudge cycle timer -> no "Era of Reckoning" (Эра Возмездия)
        [IDENTITY_BUNDLE, "wh3_dlc25_effect_dwf_book_of_grudges_disable", "faction_to_faction_own_unseen", "1.0",
         "start_turn_completed"]])
    loc += [
        ("agent_actions_localised_action_name_" + ACTION, "Основать подворье"),
        ("agent_actions_localised_action_description_" + ACTION,
         "[[col:yellow]]Основывает подворье Хребта Сотека в столице провинции союзника или вассала.[[/col]]\\n"
         "Подворье усиливает город союзника и даёт нам доход, опыт героев и узел сети троп. "
         "В регионах, которые не принадлежат союзнику, подворье не удержится."),
        ("effects_description_" + ENABLE_EFFECT, "Мастер-инженеры могут основывать [[col:yellow]]подворья[[/col]] в городах союзников"),
        ("effect_bundles_localised_title_" + FEATURE_BUNDLE, "Подворья Хребта Сотека"),
        ("effect_bundles_localised_title_" + IDENTITY_BUNDLE, "Империя героев"),
        ("effect_bundles_localised_description_" + IDENTITY_BUNDLE,
         "Империя героев не ведёт счёт эпохам Возмездия: циклы Книги Обид для неё не действуют."),
        ("effect_bundles_localised_description_" + FEATURE_BUNDLE,
         "Мастер-инженеры основывают подворья — подгорода в столицах провинций союзников и вассалов."),
    ]
    db("cdir_events_dilemma_choice_details_tables", 4, ["choice_key", "dilemma_key", "audio_event_hover", "audio_choice_vo"],
       [["FIRST", DILEMMA, "", ""], ["SECOND", DILEMMA, "", ""]])
    loc += [
        ("dilemmas_localised_title_" + DILEMMA, "Основать подворье"),
        ("dilemmas_localised_description_" + DILEMMA,
         "Наш герой пользуется доверием союзника и может основать здесь подворье — подгород Хребта Сотека.\\n\\n"
         "Подворье усиливает город союзника: экономику, оборону, мобильность и снабжение его армий, — "
         "а нам приносит доход, опыт героев и узел сети троп.\\n\\nСтоимость основания: %d золота." % FOUND_COST),
        ("cdir_events_dilemma_choice_details_localised_choice_title_%sFIRST" % DILEMMA, "Основать подворье"),
        ("cdir_events_dilemma_choice_details_localised_choice_label_%sFIRST" % DILEMMA, "Заплатить %d золота и открыть 5 слотов подворья." % FOUND_COST),
        ("cdir_events_dilemma_choice_details_localised_choice_title_%sSECOND" % DILEMMA, "Не сейчас"),
        ("cdir_events_dilemma_choice_details_localised_choice_label_%sSECOND" % DILEMMA, "Предложение повторится не раньше чем через 5 ходов."),
    ]
    gen_runes(loc)
    tsv("text/db/%s.loc.tsv" % NAME, "Loc", 1, ["key", "text", "tooltip"], [[k, v, "false"] for k, v in loc])
    print("generated: %d effects rows, %d loc rows" % (len(effects), len(loc)))


RUNE_DILEMMAS = {"slots": "he_dilemma_runes_slots"}
RUNE_BUNDLE = "he_bundle_runes"
RUNE_FACTOR = "he_runes"
OATHGOLD = "dwf_oathgold"
CHOICES = ["FIRST", "SECOND", "THIRD", "FOURTH"]


def gen_runes(loc):
    import json
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import runes_data as R

    dil_rows, choice_rows = [], []

    def dilemma(key, title, desc, choices):
        dil_rows.append(["false", key, "", "", "", "true", "", "", "", "", "false"])
        loc.append(("dilemmas_localised_title_" + key, title))
        loc.append(("dilemmas_localised_description_" + key, desc))
        for c, (ct, cl) in zip(CHOICES, choices):
            choice_rows.append([c, key, "", ""])
            loc.append(("cdir_events_dilemma_choice_details_localised_choice_title_%s%s" % (key, c), ct))
            loc.append(("cdir_events_dilemma_choice_details_localised_choice_label_%s%s" % (key, c), cl))

    costs = " / ".join(str(c) for c in R.COST)
    intro = ("Рунные мастера Хребта Сотека высекают руны на снаряжении героя. У каждого героя три рунных места: "
             "оружие, доспех и талисман.\\n\\nПовторная руна того же вида усиливает её (до %d уровня). Другая руна "
             "заменяет прежнюю. Три руны одной школы дают бонус комплекта.\\n\\nЦена: %s Клятвенного Золота за уровень."
             % (R.MAX_LEVEL, costs))
    sets = "\\n".join("%s: %s" % (R.SCHOOLS[k], ", ".join(t for _, _, t in v)) for k, v in R.SET_BONUS.items())
    dilemma(RUNE_DILEMMAS["slots"], "Руны героя", intro + "\\n\\nКомплекты (три руны одной школы):\\n" + sets,
            [(title, "Выбрать руну для места «%s»." % title) for _, title, _ in R.SLOTS] + [("Закрыть", "Вернуться к делам.")])
    for slot, title, runes in R.SLOTS:
        key = "he_dilemma_runes_" + slot
        RUNE_DILEMMAS[slot] = key
        ch = []
        for rid, name, school, eff, vals, stat in runes:
            ch.append(("%s (%s)" % (name, R.SCHOOLS[school]),
                       "%s: +%s / +%s / +%s по уровням." % (stat, vals[0], vals[1], vals[2])))
        ch.append(("← Назад", "К выбору рунного места."))
        dilemma(key, "Руны: %s" % title, intro, ch)

    db("dilemmas_tables", 3, ["generate", "key", "localised_description", "localised_title", "ui_image", "prioritized",
                              "event_category", "sound_popup_override", "sound_click_override", "override_icon", "is_large_dilemma"],
       dil_rows, name="he_runes")
    db("cdir_events_dilemma_choice_details_tables", 4, ["choice_key", "dilemma_key", "audio_event_hover", "audio_choice_vo"],
       choice_rows, name="he_runes")
    db("effect_bundles_tables", 4, ["key", "localised_description", "localised_title", "bundle_target", "priority", "ui_icon",
                                    "is_global_effect", "show_in_3d_space", "owner_only"],
       [[RUNE_BUNDLE, "", "", "character", 1, "he_runes.png", "false", "false", "true"]], name="he_runes")
    loc.append(("effect_bundles_localised_title_" + RUNE_BUNDLE, "Руны героя"))
    loc.append(("effect_bundles_localised_description_" + RUNE_BUNDLE, "Руны, высеченные на снаряжении героя рунными мастерами Хребта Сотека."))
    db("pooled_resource_factors_tables", 5, ["key", "is_hidden"], [[RUNE_FACTOR, "false"]], name="he_runes")
    db("pooled_resource_factor_junctions_tables", 3,
       ["unique_id", "factor", "resource", "minimum", "maximum", "specific_faction_set", "sort_order"],
       [["he_runes_oathgold", RUNE_FACTOR, OATHGOLD, -1000000, 1000000, "", 98]], name="he_runes")
    loc.append(("pooled_resource_factors_display_name_positive_" + RUNE_FACTOR, "Руны героев"))
    loc.append(("pooled_resource_factors_display_name_negative_" + RUNE_FACTOR, "Руны героев"))

    # Lua data module for the script
    data = {
        "scope": R.SCOPE, "cost": R.COST, "max_level": R.MAX_LEVEL, "bundle": RUNE_BUNDLE, "factor": RUNE_FACTOR,
        "resource": OATHGOLD, "dilemmas": RUNE_DILEMMAS,
        "slots": [{"id": s, "title": t, "runes": [{"id": r[0], "name": r[1], "school": r[2], "effect": r[3], "values": r[4]}
                                                for r in runes]} for s, t, runes in R.SLOTS],
        "set_bonus": {k: [{"effect": e, "value": v} for e, v, _ in lst] for k, lst in R.SET_BONUS.items()},
    }

    def lua(v, ind=""):
        if isinstance(v, dict):
            return "{\n" + "".join("%s    %s = %s,\n" % (ind, k, lua(x, ind + "    ")) for k, x in v.items()) + ind + "}"
        if isinstance(v, list):
            return "{ " + ", ".join(lua(x, ind) for x in v) + " }"
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        return str(v)
    path = os.path.join(MOD, "script", "campaign", "mod", "he_runes_data.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write("-- GENERATED by _gen/gen_data.py from _gen/runes_data.py - edit the generator, not this file.\n")
        f.write("HE_RUNES_DATA = " + lua(data) + "\n")


if __name__ == "__main__":
    main()
