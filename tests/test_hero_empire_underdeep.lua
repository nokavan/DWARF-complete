--[[
  Test of the patched CA Underdeep script (mods/hero_empire_sotek/script/campaign/wh3_campaign_underdeep.lua):
  the culture he_hero_empire must be treated like dwarfs, other cultures must not.
  Run: lua5.1 tests/test_hero_empire_underdeep.lua
]]
local SCRIPT = "mods/hero_empire_sotek/script/campaign/wh3_campaign_underdeep.lua"
local passed, failures = 0, 0
local function check(c, m) if c then passed = passed + 1 else failures = failures + 1; print("FAIL: " .. m) end end

-- permissive mock: any unknown method returns a mock; lists are empty
local function mock(fields)
    local o = fields or {}
    return setmetatable(o, { __index = function(t, k)
        if k == "is_null_interface" then return function() return false end end
        if k == "num_items" then return function() return 0 end end
        if k == "is_empty" then return function() return true end end
        return function() return mock() end
    end })
end
local function list(items)
    return mock({ num_items = function() return #items end, item_at = function(_, i) return items[i + 1] end,
                  is_empty = function() return #items == 0 end })
end

local resources = {}
local function mkfaction(key, culture)
    return mock({ name = function() return key end, culture = function() return culture end,
                  has_technology = function() return false end, region_list = function() return list({}) end,
                  foreign_slot_managers = function() return list({}) end, command_queue_index = function() return 1 end })
end
local he = mkfaction("wh2_main_dwf_spine_of_sotek_dwarfs", "he_hero_empire")
local dwf = mkfaction("wh_main_dwf_karak_kadrin", "wh_main_dwf_dwarfs")
local emp = mkfaction("wh_main_emp_empire", "wh_main_emp_empire")

local listeners = {}
_G.out = function() end
_G.core = { add_listener = function(_, name, ev, cond, cb) listeners[name] = { ev = ev, cond = cond } end }
_G.cm = mock({
    is_new_game = function() return true end,
    get_faction_list = function() return list({ he, dwf, emp }) end,
    faction_add_pooled_resource = function(_, fk, res, factor, v) resources[fk .. "|" .. res] = (resources[fk .. "|" .. res] or 0) + v end,
    model = function() return mock({ world = function() return mock({ region_manager = function()
        return mock({ region_list = function() return list({}) end }) end }) end }) end,
})

assert(loadfile(SCRIPT))()
check(type(add_underdeep_listeners) == "function", "add_underdeep_listeners defined")
add_underdeep_listeners()

check(resources["wh2_main_dwf_spine_of_sotek_dwarfs|dwf_underdeeps"] == 1, "Hero Empire gets 1 starting underdeep")
check(resources["wh_main_dwf_karak_kadrin|dwf_underdeeps"] == 1, "dwarfs still get their starting underdeep")
check(resources["wh_main_emp_empire|dwf_underdeeps"] == nil, "Empire gets nothing")

check(("he_hero_empire"):he_dwarfish() and ("wh_main_dwf_dwarfs"):he_dwarfish() and not ("wh_main_emp_empire"):he_dwarfish(),
      "string.he_dwarfish matches dwarfs + Hero Empire only")

local l = listeners["UnderdeepFactionTurnStart"]
check(l and l.ev == "FactionTurnStart", "turn-start listener registered")
local function ctx(f) return { faction = function() return mock({ foreign_slot_managers = function() return list({ 1 }) end, culture = f.culture }) end } end
check(l.cond(ctx(he)) == true, "turn-start listener applies to Hero Empire")
check(l.cond(ctx(dwf)) == true, "turn-start listener applies to dwarfs")
check(l.cond(ctx(emp)) == false, "turn-start listener ignores Empire")

print(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then os.exit(1) end
