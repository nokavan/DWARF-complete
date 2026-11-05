"""
Rune definitions for "Руны героев" — the single source of truth.
gen_data.py turns this into DB/loc rows and into script/campaign/mod/he_runes_data.lua.

Effect keys: character stats confirmed in the game's effects table; values calibrated on vanilla skills
(level 1 ~ median of vanilla skill values, level 3 ~ 90th percentile). Scope: character_to_character_own.
"""

SCOPE = "character_to_character_own"
COST = [60, 120, 200]           # Oathgold per level (replacing a rune costs level 1 again)
MAX_LEVEL = 3

SCHOOLS = {
    "onslaught": "Натиск",
    "endurance": "Стойкость",
    "mastery": "Мастерство",
}

# slot -> list of runes (order = dilemma choice order FIRST, SECOND, THIRD)
SLOTS = [
    ("weapon", "Оружие", [
        ("fury", "Руна Ярости", "onslaught", "wh_main_effect_character_stat_melee_attack", [7, 10, 14], "Атака в ближнем бою"),
        ("parry", "Руна Парирования", "endurance", "wh_main_effect_character_stat_melee_defence", [6, 9, 12], "Защита в ближнем бою"),
        ("might", "Руна Мощи", "mastery", "wh_main_effect_character_stat_weapon_strength", [10, 20, 30], "Сила оружия"),
    ]),
    ("armour", "Доспех", [
        ("swiftness", "Руна Стремительности", "onslaught", "wh_main_effect_character_stat_speed", [10, 15, 20], "Скорость"),
        ("stone", "Руна Камня", "endurance", "wh_main_effect_character_stat_armour", [15, 20, 25], "Броня"),
        ("resilience", "Руна Сопротивления", "mastery", "wh_main_effect_character_stat_physical_resistance", [10, 15, 20], "Сопротивление физическому урону"),
    ]),
    ("talisman", "Талисман", [
        ("courage", "Руна Отваги", "onslaught", "wh_main_effect_character_stat_leadership", [8, 12, 15], "Боевой дух"),
        ("warding", "Руна Оберега", "endurance", "wh_main_effect_character_stat_ward_save", [10, 12, 15], "Сопротивление всему урону"),
        ("spellbreak", "Руна Разрушения чар", "mastery", "wh_main_effect_character_stat_magic_resistance", [15, 18, 20], "Сопротивление магии"),
    ]),
]

# all three slots with runes of the same school -> set bonus (added to the same character bundle)
SET_BONUS = {
    "onslaught": [("wh_main_effect_character_stat_charge_bonus_add", 20, "Натиск +20"),
                  ("wh_main_effect_character_stat_bonus_vs_large", 12, "Бонус против больших +12")],
    "endurance": [("wh_main_effect_character_stat_unit_health", 10, "Здоровье +10%"),
                  ("wh_main_effect_character_stat_missile_resistance", 15, "Сопротивление стрелковому урону +15%")],
    "mastery":   [("wh_main_effect_character_stat_ap_damage", 50, "Бронебойный урон +50"),
                  ("wh_main_effect_character_stat_fire_resistance", 20, "Сопротивление огню +20%")],
}
