--[[
  Offline test of the campaign script with a stubbed game API.
  Run:  lua5.1 tools/test_mod.lua
  This checks the script's own logic (levels, costs, payloads, dilemma flow, caps).
  It cannot check the real game: effect keys, UI templates, etc.
]]
local SCRIPT = "mod/script/campaign/mod/dwf_ancient_lineages.lua"
local unpack = unpack or table.unpack
_G.unpack = unpack

local failures, passed = 0, 0
local function check(cond, msg)
    if cond then passed = passed + 1 else failures = failures + 1; print("FAIL: " .. msg) end
end

------------------------------------------------------------------ stubs
local null = { is_null_interface = function() return true end }
local saved, listeners, first_tick, callbacks = {}, {}, {}, {}
local applied = {}      -- bundle key -> effects table
local launched = {}     -- list of {key=, payloads=}
local gold = { value = 0 }
local transactions = {}

local function make_bundle(key)
    local b = { key = key, effects = {}, duration = nil }
    function b:is_null_interface() return false end
    function b:add_effect(k, scope, v) self.effects[k] = v end
    function b:set_duration(d) self.duration = d end
    return b
end

local faction = {}
function faction:is_null_interface() return false end
function faction:name() return "wh_main_dwf_dwarfs" end
function faction:culture() return "wh_main_dwf_dwarfs" end
function faction:is_dead() return false end
function faction:is_human() return true end
function faction:command_queue_index() return 7 end
function faction:pooled_resource_manager()
    return { resource = function(_, k)
        if k ~= "dwf_oathgold" then return null end
        return { is_null_interface = function() return false end, value = function() return gold.value end }
    end }
end

_G.out = function(s) if os.getenv("VERBOSE") then print(s) end end
_G.model_pairs = function(list) local i = 0; return function() i = i + 1; if list[i] then return i, list[i] end end end
_G.find_uicomponent = function() return nil end
_G.UIComponent = function(c) return c end
_G.CampaignUI = { TriggerCampaignScriptEvent = function() end }

_G.core = {
    add_listener = function(_, name, event, cond, cb, persist)
        listeners[#listeners + 1] = { name = name, event = event, cond = cond, cb = cb }
    end,
    trigger_event = function() end,
    get_ui_root = function() return nil end,
    get_screen_resolution = function() return 1920, 1080 end,
}

_G.cm = {
    add_first_tick_callback = function(_, f) first_tick[#first_tick + 1] = f end,
    get_saved_value = function(_, k) return saved[k] end,
    set_saved_value = function(_, k, v) saved[k] = v end,
    get_faction = function(_, k) return faction end,
    get_local_faction_name = function() return faction:name() end,
    is_local_players_turn = function() return true end,
    model = function() return {
        world = function() return { faction_list = function() return { faction } end } end,
        faction_for_command_queue_index = function() return faction end,
    } end,
    create_new_custom_effect_bundle = function(_, key) return make_bundle(key) end,
    apply_custom_effect_bundle_to_faction = function(_, b, f) applied[b.key] = b.effects end,
    faction_add_pooled_resource = function(_, fk, res, factor, amount)
        transactions[#transactions + 1] = { res = res, factor = factor, amount = amount }
        gold.value = gold.value + amount
    end,
    create_dilemma_builder = function(_, key)
        local d = { key = key, payloads = {} }
        function d:add_choice_payload(choice, p) self.payloads[choice] = p end
        return d
    end,
    create_payload = function()
        local p = { cost = nil, bundle = nil }
        function p:faction_pooled_resource_transaction(res, factor, amount) self.cost = -amount; self.res = res; self.factor = factor end
        function p:effect_bundle_to_faction(b) self.bundle = b end
        return p
    end,
    launch_custom_dilemma_from_builder = function(_, d, f) launched[#launched + 1] = d end,
    callback = function(_, f) callbacks[#callbacks + 1] = f end,
}

local function fire(event, ctx)
    for _, l in ipairs(listeners) do
        if l.event == event and l.cond(ctx) then l.cb(ctx) end
    end
end
local function run_callbacks()
    local c = callbacks; callbacks = {}
    for _, f in ipairs(c) do f() end
end

-- simulate the payload being applied by the game when a choice is picked
local function choose(dilemma, idx)
    local d = launched[#launched]
    local p = d.payloads[({ "FIRST", "SECOND", "THIRD", "FOURTH" })[idx + 1]]
    if p and p.cost then gold.value = gold.value - p.cost end
    if p and p.bundle then applied[p.bundle.key] = p.bundle.effects end
    fire("DilemmaChoiceMadeEvent", {
        dilemma = function() return dilemma end,
        choice = function() return idx end,
        faction = function() return faction end,
    })
    run_callbacks()
end

------------------------------------------------------------------ load
local chunk = assert(loadfile(SCRIPT))
chunk()
check(#first_tick == 1, "first tick callback registered")
first_tick[1]()
local api = _G.dwf_ancient_lineages
check(api ~= nil, "API exported")

------------------------------------------------------------------ tests
-- costs
check(api.cost_for(0) == 80, "awaken cost 80")
check(api.cost_for(1) == 90, "lvl1->2 cost 90")
check(api.cost_for(10) == 360, "lvl10->11 cost 360")

-- open menu with no gold
gold.value = 50
fire("UITriggerScriptEvent", { trigger = function() return "dwf_al_open" end, faction_cqi = function() return 7 end })
check(#launched == 1 and launched[1].key == "dwf_al_dilemma_page_1", "page 1 launched on button event")
check(launched[1].payloads.FIRST.cost == nil, "unaffordable choice has no cost payload")
check(launched[1].payloads.FIRST.bundle.key == "dwf_al_bundle_locked", "unaffordable choice shows locked bundle")
choose("dwf_al_dilemma_page_1", 0)
check(api.get_level("wh_main_dwf_dwarfs", "grimnir") == 0, "no level-up without gold")
check(gold.value == 50, "gold untouched when unaffordable")

-- buy Grimnir 1
gold.value = 1000
fire("UITriggerScriptEvent", { trigger = function() return "dwf_al_open" end, faction_cqi = function() return 7 end })
local p = launched[#launched].payloads.FIRST
check(p.cost == 80 and p.res == "dwf_oathgold" and p.factor == "dwf_al_lineages", "payload charges 80 oathgold via own factor")
check(p.bundle.key == "dwf_al_bundle_grimnir" and p.bundle.effects["wh_main_effect_force_stat_melee_attack"] == 1, "payload previews level 1 bundle")
choose("dwf_al_dilemma_page_1", 0)
check(api.get_level("wh_main_dwf_dwarfs", "grimnir") == 1, "grimnir level 1")
check(gold.value == 920, "80 gold spent exactly once (got " .. gold.value .. ")")
check(launched[#launched].key == "dwf_al_dilemma_page_1", "page re-opened after purchase")

-- buy Grimnir again (level 2, cost 90)
choose("dwf_al_dilemma_page_1", 0)
check(api.get_level("wh_main_dwf_dwarfs", "grimnir") == 2 and gold.value == 830, "grimnir level 2 for 90")
check(applied["dwf_al_bundle_grimnir"]["wh_main_effect_force_stat_charge_bonus"] == 4, "charge +4 at level 2")

-- navigation
choose("dwf_al_dilemma_page_1", 3)
check(launched[#launched].key == "dwf_al_dilemma_page_2", "next -> page 2")
choose("dwf_al_dilemma_page_2", 1)
check(api.get_level("wh_main_dwf_dwarfs", "thungni") == 1, "thungni bought on page 2")
local n = #launched
choose("dwf_al_dilemma_page_2", 3)
check(#launched == n, "close does not reopen")

-- infinite levels + soft cap + milestones
for _ = 1, 300 do api.level_up(faction, "morgrim", false) end
check(api.get_level("wh_main_dwf_dwarfs", "morgrim") == 300, "level 300 reachable")
local up = applied["dwf_al_bundle_morgrim"]["wh_main_effect_force_all_campaign_upkeep"]
check(up == -60, "upkeep soft-capped at -60 (got " .. tostring(up) .. ")")
for _ = 1, 8 do api.level_up(faction, "grimnir", false) end -- -> level 10
check(applied["dwf_al_bundle_grimnir"]["wh_main_effect_force_stat_melee_attack"] == 12, "lvl10 melee = 10 * 1.2 milestones")

-- paid level_up (AI path)
gold.value = 0
check(api.level_up(faction, "valaya", true) == false, "paid level_up refuses without gold")
gold.value = 80
check(api.level_up(faction, "valaya", true) == true and gold.value == 0, "paid level_up spends gold")
check(transactions[#transactions].amount == -80 and transactions[#transactions].res == "dwf_oathgold", "spend uses pooled resource transaction")

-- reload re-applies bundles
applied = {}
first_tick[1]()
check(applied["dwf_al_bundle_grimnir"] ~= nil and applied["dwf_al_bundle_morgrim"] ~= nil, "bundles re-applied on load")

print(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then os.exit(1) end
