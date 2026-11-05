--[[
    Империя героев (Хребет Сотека) — базовая настройка фракции.

    1) Отключает «Эру Возмездия» (циклы Книги Обид, wh3_dlc25_grudge_cycles.lua).
       Используется штатный выключатель CA: эффект wh3_dlc25_effect_dwf_book_of_grudges_disable даёт бонус
       dwf_grudge_feature_off, при котором таймер цикла не идёт. Дополнительно, как делает сам CA при
       отключении (wh3_campaign_underdeep.lua), обнуляется таймер и снимаются наборы эффектов эпохи.
]]

local CONFIG = {
    faction = "wh2_main_dwf_spine_of_sotek_dwarfs",
    identity_bundle = "he_bundle_faction_identity",
    grudge_cycle_bundle_prefix = "wh3_dlc25_grudge_cycle_",   -- 0..5, как в скрипте CA
}

local function log(msg) out("[HE Setup] " .. tostring(msg)) end

local function disable_era_of_reckoning()
    local faction = cm:get_faction(CONFIG.faction)
    if not faction or faction:is_null_interface() or faction:is_dead() then return end
    local fk = faction:name()

    if not faction:has_effect_bundle(CONFIG.identity_bundle) then
        cm:apply_effect_bundle(CONFIG.identity_bundle, fk, 0)
        log("Эра Возмездия отключена")
    end
    if grudge_cycle and type(grudge_cycle.faction_times) == "table" then
        grudge_cycle.faction_times[fk] = 0
    end
    for i = 0, 5 do
        local b = CONFIG.grudge_cycle_bundle_prefix .. i
        if faction:has_effect_bundle(b) then cm:remove_effect_bundle(b, fk) end
    end
end

cm:add_first_tick_callback(function()
    disable_era_of_reckoning()
    -- скрипт CA выдаёт стартовый набор эпохи тоже на первом тике: повторяем чуть позже
    cm:callback(disable_era_of_reckoning, 1)

    core:add_listener("he_setup_turn_start", "FactionTurnStart",
        function(context) return context:faction():name() == CONFIG.faction end,
        function() disable_era_of_reckoning() end, true)
end)

he_faction_setup = { config = CONFIG, disable_era_of_reckoning = disable_era_of_reckoning }
