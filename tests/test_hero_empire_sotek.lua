--[[
  Offline test of he_podvorye.lua with a stubbed game API.
  Run: lua5.1 tests/test_hero_empire_sotek.lua
]]
local SCRIPT = "mods/hero_empire_sotek/script/campaign/mod/he_podvorye.lua"
local passed, failures = 0, 0
local function check(c, m) if c then passed = passed + 1 else failures = failures + 1; print("FAIL: " .. m) end end

local NULL = { is_null_interface = function() return true end }
local saved, listeners, first_tick = {}, {}, {}
local turn, gold, rnd = 1, 10000, 1
local slots = {}            -- region_key -> faction_key holding foreign slots
local log_calls = { treasury = {}, dilemmas = {}, diplo = {} }

local factions, regions = {}, {}
local function mkfaction(key, human)
    local f = { key = key, human = human, allies = {}, vassal_of = {}, chars = {} }
    function f:is_null_interface() return false end
    function f:name() return self.key end
    function f:is_human() return self.human end
    function f:is_dead() return false end
    function f:command_queue_index() return #self.key end
    function f:allied_with(o) return self.allies[o:name()] == true end
    function f:is_vassal_of(o) return self.vassal_of[o:name()] == true end
    function f:treasury() return gold end
    function f:character_list()
        local l = self.chars
        return { num_items = function() return #l end, item_at = function(_, i) return l[i + 1] end }
    end
    function f:foreign_slot_managers()
        local l = {}
        for rk, fk in pairs(slots) do if fk == self.key then l[#l + 1] = { region = function() return regions[rk] end } end end
        return { num_items = function() return #l end, item_at = function(_, i) return l[i + 1] end }
    end
    factions[key] = f
    return f
end
local function mkregion(key, owner)
    local r = { key = key, owner = owner, abandoned = false }
    function r:is_null_interface() return false end
    function r:name() return self.key end
    function r:cqi() return 100 + #self.key end
    function r:is_abandoned() return self.abandoned end
    function r:owning_faction() return factions[self.owner] end
    function r:settlement() return { cqi = function() return 5 end } end
    function r:foreign_slot_manager_for_faction(fk)
        if slots[self.key] == fk then return { is_null_interface = function() return false end } end
        return NULL
    end
    regions[key] = r
    return r
end
local function mkagent(region_key, is_agent)
    local c = { rk = region_key, agent = is_agent }
    function c:has_region() return self.rk ~= nil end
    function c:region() return regions[self.rk] end
    function c:command_queue_index() return 42 end
    return c
end

local ME = "wh2_main_dwf_spine_of_sotek_dwarfs"
local me = mkfaction(ME, true)
local ally = mkfaction("ally_faction", false)
local enemy = mkfaction("enemy_faction", false)
ally.allies[ME] = true
mkregion("r_ally", "ally_faction")
mkregion("r_ally2", "ally_faction")
mkregion("r_enemy", "enemy_faction")

_G.out = function(s) if os.getenv("VERBOSE") then print(s) end end
_G.core = {
    add_listener = function(_, name, ev, cond, cb) listeners[#listeners + 1] = { ev = ev, cond = cond, cb = cb } end,
    trigger_event = function() end,
}
_G.cm = {
    add_first_tick_callback = function(_, f) first_tick[#first_tick + 1] = f end,
    get_saved_value = function(_, k) return saved[k] end,
    set_saved_value = function(_, k, v) saved[k] = v end,
    get_region = function(_, k) return regions[k] end,
    turn_number = function() return turn end,
    random_number = function() return rnd end,
    char_is_agent = function(_, c) return c.agent end,
    treasury_mod = function(_, fk, v) gold = gold + v; log_calls.treasury[#log_calls.treasury + 1] = v end,
    add_foreign_slot_set_to_region_for_faction = function(_, fcqi, rcqi, set)
        for rk, r in pairs(regions) do if r:cqi() == rcqi then slots[rk] = ME end end
    end,
    remove_faction_foreign_slots_from_region = function(_, fcqi, rcqi)
        for rk, r in pairs(regions) do if r:cqi() == rcqi then slots[rk] = nil end end
    end,
    make_region_visible_in_shroud = function() end,
    apply_dilemma_diplomatic_bonus = function(_, a, b, v) log_calls.diplo[#log_calls.diplo + 1] = b end,
    get_faction = function(_, k) return factions[k] end,
    apply_effect_bundle = function(_, key, fk, turns) log_calls.bundles = log_calls.bundles or {}; log_calls.bundles[#log_calls.bundles + 1] = key .. "|" .. fk .. "|" .. turns end,
    trigger_dilemma_with_targets = function(_, fcqi, key, ...) log_calls.dilemmas[#log_calls.dilemmas + 1] = { key = key, args = { ... } } end,
}

local function fire(ev, ctx) for _, l in ipairs(listeners) do if l.ev == ev and l.cond(ctx) then l.cb(ctx) end end end
local function turn_start(f) fire("FactionTurnStart", { faction = function() return f end }) end
local function choose(f, idx)
    fire("DilemmaChoiceMadeEvent", { dilemma = function() return "he_dilemma_found_podvorye" end,
        choice = function() return idx end, faction = function() return f end })
end

assert(loadfile(SCRIPT))()
first_tick[1]()
local api = _G.he_podvorye

-- нет героя -> нет предложения
turn_start(me)
check(#log_calls.dilemmas == 0, "no agent, no dilemma")

-- лорд (не агент) в регионе союзника -> нет предложения
me.chars = { mkagent("r_ally", false) }
turn_start(me)
check(#log_calls.dilemmas == 0, "general does not trigger")

-- герой во вражеском регионе -> нет
me.chars = { mkagent("r_enemy", true) }
turn_start(me)
check(#log_calls.dilemmas == 0, "enemy region does not trigger")

-- герой в регионе союзника -> дилемма с целями
me.chars = { mkagent("r_ally", true) }
turn_start(me)
check(#log_calls.dilemmas == 1 and log_calls.dilemmas[1].key == "he_dilemma_found_podvorye", "dilemma offered in allied region")
check(log_calls.dilemmas[1].args[3] == 42, "dilemma targets the hero")

-- «Не сейчас» -> кулдаун
choose(me, 1)
check(slots["r_ally"] == nil, "decline does not found")
turn = 2; turn_start(me)
check(#log_calls.dilemmas == 1, "cooldown blocks repeat offer")
turn = 7; turn_start(me)
check(#log_calls.dilemmas == 2, "offer repeats after cooldown")

-- «Основать»
local g0 = gold
choose(me, 0)
check(slots["r_ally"] == ME, "podvorye founded (foreign slots added)")
check(gold == g0 - 1500, "1500 gold spent")
check(api.get_list(ME)[1] == "r_ally", "saved in list")
check(log_calls.diplo[1] == "ally_faction", "diplomatic bonus with host")

-- повторно в том же регионе не предлагается
turn = 8; turn_start(me)
check(#log_calls.dilemmas == 2, "no offer where podvorye exists")

-- не хватает денег -> не предлагается
me.chars = { mkagent("r_ally2", true) }
gold = 100
turn = 9; turn_start(me)
check(#log_calls.dilemmas == 2, "no offer without gold")
gold = 10000

-- разрыв союза: 10 ходов терпения, потом снос
ally.allies[ME] = nil
me.chars = {}
for t = 10, 19 do turn = t; turn_start(me) end
check(slots["r_ally"] == ME, "survives grace period")
turn = 20; turn_start(me)
check(slots["r_ally"] == nil and #api.get_list(ME) == 0, "removed after grace period")

-- союз восстановлен до конца срока -> счётчик сбрасывается
ally.allies[ME] = true
api.found(me, regions["r_ally"])
ally.allies[ME] = nil
for t = 21, 25 do turn = t; turn_start(me) end
ally.allies[ME] = true
turn = 26; turn_start(me)
ally.allies[ME] = nil
for t = 27, 36 do turn = t; turn_start(me) end
check(slots["r_ally"] == ME, "counter resets when alliance restored")
ally.allies[ME] = true

-- регион захвачен нами -> подворье убирается
regions["r_ally"].owner = ME
turn = 37; turn_start(me)
check(slots["r_ally"] == nil, "removed when region becomes ours")
regions["r_ally"].owner = "ally_faction"

-- вассал тоже подходит
local vassal = mkfaction("vassal_faction", false)
vassal.vassal_of[ME] = true
mkregion("r_vassal", "vassal_faction")
check(api.found(me, regions["r_vassal"]) == true, "can found in vassal region")

-- лимит
gold = 1000000
for i = 1, 10 do mkregion("lim" .. i, "ally_faction"); api.found(me, regions["lim" .. i]) end
check(#api.get_list(ME) == 6, "max podvorye limit = 6")

-- подворье, уничтоженное игрой, удаляется из списка
slots["r_vassal"] = nil
turn = 38; turn_start(me)
check(#api.get_list(ME) == 5, "destroyed podvorye dropped from list")

-- ИИ-фракция
local ai = mkfaction("wh2_main_dwf_spine_of_sotek_dwarfs", false) -- same key, now AI
ai.chars = { mkagent("r_ally2", true) }
gold = 10000; rnd = 1
turn = 39; turn_start(ai)
check(slots["r_ally2"] == ME, "AI founds podvorye on its own")

-- набор эффектов, открывающий действие героя, применён бессрочно
check(log_calls.bundles and log_calls.bundles[1] == "he_bundle_podvorye_feature|wh2_main_dwf_spine_of_sotek_dwarfs|0", "feature bundle applied permanently")

-- подворье, созданное штатным действием героя
local function native(region_key)
    slots[region_key] = ME
    fire("ForeignSlotManagerCreatedEvent", { requesting_faction = function() return me end, region = function() return regions[region_key] end })
end
for _, rk in ipairs(api.get_list(ME)) do api.remove(me, rk, regions[rk], "test reset") end
mkregion("n_ally", "ally_faction")
native("n_ally")
check(api.get_list(ME)[1] == "n_ally" and slots["n_ally"] == ME, "native podvorye registered")
mkregion("n_enemy", "enemy_faction")
native("n_enemy")
check(slots["n_enemy"] == nil and #api.get_list(ME) == 1, "native podvorye in non-allied region removed")
for i = 1, 5 do mkregion("nl" .. i, "ally_faction"); native("nl" .. i) end
mkregion("nl_over", "ally_faction"); native("nl_over")
check(#api.get_list(ME) == 6 and slots["nl_over"] == nil, "native podvorye over limit removed")

-- дилемма-запасной путь выключается настройкой
api.config.dilemma_fallback = false
for _, rk in ipairs(api.get_list(ME)) do api.remove(me, rk, regions[rk], "test reset") end
me.chars = { mkagent("r_ally2", true) }
slots["r_ally2"] = nil
local n = #log_calls.dilemmas
turn = 60; turn_start(me)
check(#log_calls.dilemmas == n, "no dilemma when fallback disabled")

print(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then os.exit(1) end
