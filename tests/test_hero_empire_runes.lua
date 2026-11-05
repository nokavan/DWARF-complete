-- Offline test of he_runes.lua. Run: lua5.1 tests/test_hero_empire_runes.lua
local passed, failures = 0, 0
local function check(c, m) if c then passed = passed + 1 else failures = failures + 1; print("FAIL: " .. m) end end
_G.unpack = unpack or table.unpack

local saved, listeners, ticks, callbacks, launched = {}, {}, {}, {}, {}
local char_bundles = {}   -- cqi -> effects table
local FK = "wh2_main_dwf_spine_of_sotek_dwarfs"

local function mkfaction(key)
    return { name = function() return key end, is_null_interface = function() return false end,
             command_queue_index = function() return 7 end,
             character_list = function() return { num_items = function() return 0 end } end }
end
local our, other = mkfaction(FK), mkfaction("wh_main_dwf_dwarfs")
local chars = {}
local function mkchar(cqi, faction)
    local c = { cqi = cqi }
    function c:command_queue_index() return self.cqi end
    function c:is_null_interface() return false end
    function c:faction() return faction end
    function c:family_member() return {} end
    function c:has_effect_bundle(b) return char_bundles[self.cqi] ~= nil end
    chars[cqi] = c
    return c
end
local hero = mkchar(42, our)
local enemy_hero = mkchar(99, other)

_G.out = function(s) if os.getenv("VERBOSE") then print(s) end end
_G.find_uicomponent = function() return nil end
_G.UIComponent = function(c) return c end
_G.CampaignUI = { TriggerCampaignScriptEvent = function() end }
_G.core = {
    add_listener = function(_, n, ev, cond, cb) listeners[#listeners + 1] = { ev = ev, cond = cond, cb = cb } end,
    trigger_event = function() end, get_ui_root = function() return nil end,
}
_G.cm = {
    add_first_tick_callback = function(_, f) ticks[#ticks + 1] = f end,
    get_saved_value = function(_, k) return saved[k] end,
    set_saved_value = function(_, k, v) saved[k] = v end,
    get_faction = function(_, k) return k == FK and our or other end,
    get_local_faction_name = function() return FK end,
    is_local_players_turn = function() return true end,
    get_character_by_cqi = function(_, cqi) return chars[cqi] or false end,
    callback = function(_, f) callbacks[#callbacks + 1] = f end,
    create_new_custom_effect_bundle = function(_, key)
        local b = { key = key, effects = {} }
        function b:add_effect(k, scope, v) self.effects[k] = v; self.scope = scope end
        function b:set_duration(d) self.duration = d end
        return b
    end,
    apply_custom_effect_bundle_to_character = function(_, b, c) char_bundles[c.cqi] = b.effects end,
    remove_effect_bundle_from_character = function(_, key, c) char_bundles[c.cqi] = nil end,
    create_dilemma_builder = function(_, key)
        local d = { key = key, payloads = {} }
        function d:add_choice_payload(ch, p) self.payloads[ch] = p end
        function d:add_target() end
        return d
    end,
    create_payload = function()
        local p = {}
        function p:faction_pooled_resource_transaction(res, factor, amount, required)
            self.res, self.factor, self.cost, self.required = res, factor, -amount, required
        end
        function p:effect_bundle_to_character(c, b) self.preview = b.effects end
        return p
    end,
    launch_custom_dilemma_from_builder = function(_, d) launched[#launched + 1] = d end,
}

local function fire(ev, ctx) for _, l in ipairs(listeners) do if l.ev == ev and l.cond(ctx) then l.cb(ctx) end end end
local function run_callbacks() local c = callbacks; callbacks = {}; for _, f in ipairs(c) do f() end end
local function last() return launched[#launched] end
local function choose(idx)
    local d = last()
    fire("DilemmaChoiceMadeEvent", { dilemma = function() return d.key end, choice = function() return idx end })
    run_callbacks()
end
local function open(cqi)
    fire("UITrigger", { trigger = function() return "he_runes|" .. cqi end })
end

assert(loadfile("mods/hero_empire_sotek/script/campaign/mod/he_runes_data.lua"))()
assert(loadfile("mods/hero_empire_sotek/script/campaign/mod/he_runes.lua"))()
ticks[1]()

open(42)
check(last() and last().key == "he_dilemma_runes_slots", "slots page opens for our hero")
local n = #launched
open(99)
check(#launched == n, "other faction's character ignored")

choose(0) -- weapon
check(last().key == "he_dilemma_runes_weapon", "weapon page")
local p = last().payloads.FIRST
check(p.cost == 60 and p.required == true and p.res == "dwf_oathgold" and p.factor == "he_runes", "fury L1 costs 60 oathgold, required")
check(p.preview and p.preview["wh_main_effect_character_stat_melee_attack"] == 7, "preview shows melee attack +7")

choose(0) -- fury L1
check(saved["he_runes_42_weapon"] == "fury:1", "fury level 1 saved")
check(char_bundles[42]["wh_main_effect_character_stat_melee_attack"] == 7, "bundle applied: melee attack +7")
check(last().key == "he_dilemma_runes_weapon" and last().payloads.FIRST.cost == 120, "page reopened, next level costs 120")
choose(0); choose(0)
check(saved["he_runes_42_weapon"] == "fury:3" and char_bundles[42]["wh_main_effect_character_stat_melee_attack"] == 14, "fury level 3 = +14")
check(last().payloads.FIRST.cost == nil, "max level: no cost payload")
choose(0)
check(saved["he_runes_42_weapon"] == "fury:3", "max level stays")

choose(1) -- parry replaces fury
check(saved["he_runes_42_weapon"] == "parry:1", "parry replaces fury at level 1")
check(char_bundles[42]["wh_main_effect_character_stat_melee_attack"] == nil and char_bundles[42]["wh_main_effect_character_stat_melee_defence"] == 6, "effects recomputed")

choose(3) -- back
check(last().key == "he_dilemma_runes_slots", "back to slots")
choose(1); choose(1)       -- armour -> stone (endurance)
check(char_bundles[42]["wh_main_effect_character_stat_armour"] == 15, "stone armour +15")
choose(3); choose(2)       -- back -> talisman
local pv = last().payloads.SECOND.preview
check(pv and pv["wh_main_effect_character_stat_unit_health"] == 10, "preview shows the endurance set bonus before buying")
choose(1)                  -- warding (endurance) -> full endurance set
local e = char_bundles[42]
check(e["wh_main_effect_character_stat_ward_save"] == 10, "ward save +10")
check(e["wh_main_effect_character_stat_unit_health"] == 10 and e["wh_main_effect_character_stat_missile_resistance"] == 15, "endurance set bonus applied")
check(he_runes.set_school(he_runes.get_runes(42)) == "endurance", "set school endurance")

choose(0)                  -- courage (onslaught) breaks the set
check(char_bundles[42]["wh_main_effect_character_stat_unit_health"] == nil, "set bonus removed when the set breaks")

choose(3); choose(3)       -- back, close
local n2 = #launched
run_callbacks()
check(#launched == n2, "close does not reopen")

-- reload: bundles re-applied from saved runes
char_bundles[42] = nil
our.character_list = function() return { num_items = function() return 1 end, item_at = function() return hero end } end
ticks[1]()
check(char_bundles[42] and char_bundles[42]["wh_main_effect_character_stat_melee_defence"] == 6, "runes re-applied on load")

print(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then os.exit(1) end
