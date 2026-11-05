-- Offline test of he_faction_setup.lua. Run: lua5.1 tests/test_hero_empire_setup.lua
local passed, failures = 0, 0
local function check(c, m) if c then passed = passed + 1 else failures = failures + 1; print("FAIL: " .. m) end end

local bundles, ticks, listeners, callbacks = {}, {}, {}, {}
local FK = "wh2_main_dwf_spine_of_sotek_dwarfs"
local faction = {
    is_null_interface = function() return false end, is_dead = function() return false end,
    name = function() return FK end,
    has_effect_bundle = function(_, b) return bundles[b] ~= nil end,
}
_G.out = function() end
_G.core = { add_listener = function(_, n, ev, cond, cb) listeners[#listeners + 1] = { ev = ev, cond = cond, cb = cb } end }
_G.cm = {
    add_first_tick_callback = function(_, f) ticks[#ticks + 1] = f end,
    get_faction = function(_, k) return k == FK and faction or nil end,
    apply_effect_bundle = function(_, b, f, t) bundles[b] = t end,
    remove_effect_bundle = function(_, b, f) bundles[b] = nil end,
    callback = function(_, f) callbacks[#callbacks + 1] = f end,
    get_local_faction_name = function() return FK end,
    repeat_callback = function(_, f, t, name) repeating = { f = f, t = t, name = name } end,
}
local holder = { visible = true }
function holder:Visible() return self.visible end
function holder:SetVisible(v) self.visible = v end
_G.find_uicomponent = function(root, name) if name == "grudge_cycles_holder" then return holder end end
core.get_ui_root = function() return {} end
_G.grudge_cycle = { faction_times = { [FK] = 7 } }
bundles["wh3_dlc25_grudge_cycle_2"] = 10   -- era bundle given by CA's script

assert(loadfile("mods/hero_empire_sotek/script/campaign/mod/he_faction_setup.lua"))()
ticks[1]()
check(bundles["he_bundle_faction_identity"] == 0, "identity bundle applied permanently")
check(bundles["wh3_dlc25_grudge_cycle_2"] == nil, "era bundle removed")
check(grudge_cycle.faction_times[FK] == 0, "cycle timer reset")
bundles["wh3_dlc25_grudge_cycle_0"] = 10
for _, f in ipairs(callbacks) do f() end
check(bundles["wh3_dlc25_grudge_cycle_0"] == nil, "delayed pass removes a late era bundle")
local l = listeners[1]
check(l.ev == "FactionTurnStart" and l.cond({ faction = function() return faction end }), "turn-start listener for our faction")
check(not l.cond({ faction = function() return { name = function() return "wh_main_dwf_dwarfs" end } end }), "other dwarfs untouched")

check(holder.visible == false, "era indicator hidden")
check(repeating and repeating.t == 1 and repeating.name == "he_hide_reckoning_ui", "indicator re-hidden every second")
holder.visible = true; repeating.f()
check(holder.visible == false, "repeat callback hides a recreated indicator")

print(string.format("%d passed, %d failed", passed, failures))
if failures > 0 then os.exit(1) end
