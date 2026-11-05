--[[
    Империя героев (Хребет Сотека) — РУНЫ ГЕРОЕВ (свои сочетания эффектов)

    У каждого персонажа фракции (лорды и герои) три рунных места: оружие, доспех, талисман.
    В каждое место вставляется одна руна (3 вида на место, 3 уровня). Повторная вставка той же руны
    поднимает уровень; другая руна заменяет прежнюю. Три руны одной школы дают бонус комплекта.
    Все руны героя собираются в ОДИН набор эффектов на персонаже (custom effect bundle "he_bundle_runes"),
    значения пересчитываются при каждом изменении.

    Управление: выделите героя или лорда и нажмите кнопку рун на панели фракции -> окно «Руны героя».
    Цена: Клятвенное Золото; недоступные по цене руны игра сама показывает неактивными
    (faction_pooled_resource_transaction с required = true).

    Данные рун: he_runes_data.lua (генерируется из _gen/runes_data.py).
    Функции движка: см. tools/wh3_api_names.json (проверяется в CI).
]]

local FACTION = "wh2_main_dwf_spine_of_sotek_dwarfs"
local P = "he_runes_"
local BUTTON_ID = "he_runes_button"
local BUTTON_ICON = "ui/he_runes/icon_runes.png"
local UI_EVENT = "he_runes"

local function log(msg) out("[HE Runes] " .. tostring(msg)) end
local function D() return HE_RUNES_DATA end

----------------------------------------------------------------- данные героя
local function slot_key(cqi, slot) return P .. cqi .. "_" .. slot end

local function rune_def(slot_id, rune_id)
    for _, s in ipairs(D().slots) do
        if s.id == slot_id then
            for _, r in ipairs(s.runes) do
                if r.id == rune_id then return r end
            end
        end
    end
    return nil
end

local function get_slot(cqi, slot_id)
    local v = cm:get_saved_value(slot_key(cqi, slot_id))
    if type(v) ~= "string" then return nil end
    local id, lvl = string.match(v, "^([%w_]+):(%d+)$")
    if not id or not rune_def(slot_id, id) then return nil end
    return { id = id, level = tonumber(lvl) }
end

local function set_slot(cqi, slot_id, rune_id, level)
    cm:set_saved_value(slot_key(cqi, slot_id), rune_id .. ":" .. level)
end

local function get_runes(cqi)
    local t = {}
    for _, s in ipairs(D().slots) do t[s.id] = get_slot(cqi, s.id) end
    return t
end

-- школа комплекта, если во ВСЕХ местах руны одной школы
local function set_school(runes)
    local school
    for _, s in ipairs(D().slots) do
        local r = runes[s.id]
        if not r then return nil end
        local def = rune_def(s.id, r.id)
        if school and def.school ~= school then return nil end
        school = def.school
    end
    return school
end

-- суммарные эффекты: effect_key -> value
local function total_effects(runes)
    local eff = {}
    for _, s in ipairs(D().slots) do
        local r = runes[s.id]
        if r then
            local def = rune_def(s.id, r.id)
            local v = def.values[math.min(r.level, #def.values)]
            eff[def.effect] = (eff[def.effect] or 0) + v
        end
    end
    local school = set_school(runes)
    if school then
        for _, b in ipairs(D().set_bonus[school] or {}) do
            eff[b.effect] = (eff[b.effect] or 0) + b.value
        end
    end
    return eff, school
end

local function build_bundle(runes)
    local eff = total_effects(runes)
    if next(eff) == nil then return nil end
    local bundle = cm:create_new_custom_effect_bundle(D().bundle)
    -- порядок эффектов фиксируем для стабильного отображения
    local keys = {}
    for k in pairs(eff) do keys[#keys + 1] = k end
    table.sort(keys)
    for _, k in ipairs(keys) do bundle:add_effect(k, D().scope, eff[k]) end
    bundle:set_duration(0)
    return bundle
end

local function apply_runes(character)
    local runes = get_runes(character:command_queue_index())
    local bundle = build_bundle(runes)
    if bundle then
        cm:apply_custom_effect_bundle_to_character(bundle, character)
    elseif character:has_effect_bundle(D().bundle) then
        cm:remove_effect_bundle_from_character(D().bundle, character)
    end
end

-- новое состояние места при выборе руны (nil = уже максимум)
local function next_state(cqi, slot_id, rune_id)
    local cur = get_slot(cqi, slot_id)
    if cur and cur.id == rune_id then
        if cur.level >= D().max_level then return nil end
        return { id = rune_id, level = cur.level + 1 }
    end
    return { id = rune_id, level = 1 }
end

----------------------------------------------------------------- окна (дилеммы)
local CHOICES = { "FIRST", "SECOND", "THIRD", "FOURTH" }
local pending_key = P .. "pending"   -- "cqi|page"

local function add_character_target(builder, character)
    pcall(function() builder:add_target("default", character:family_member()) end)
end

local function open_page(character, page)
    local faction = character:faction()
    local builder = cm:create_dilemma_builder(D().dilemmas[page])
    add_character_target(builder, character)
    local cqi = character:command_queue_index()

    if page ~= "slots" then
        local slot
        for _, s in ipairs(D().slots) do if s.id == page then slot = s end end
        for i, r in ipairs(slot.runes) do
            local payload = cm:create_payload()
            local st = next_state(cqi, page, r.id)
            if st then
                local runes = get_runes(cqi)
                runes[page] = st
                payload:faction_pooled_resource_transaction(D().resource, D().factor, -D().cost[st.level], true)
                local preview = build_bundle(runes)
                if preview then payload:effect_bundle_to_character(character, preview) end
            end
            builder:add_choice_payload(CHOICES[i], payload)
        end
        builder:add_choice_payload(CHOICES[4], cm:create_payload())
    else
        for i = 1, 4 do builder:add_choice_payload(CHOICES[i], cm:create_payload()) end
    end

    cm:set_saved_value(pending_key, cqi .. "|" .. page)
    cm:launch_custom_dilemma_from_builder(builder, faction)
end

local function page_of_dilemma(key)
    for page, k in pairs(D().dilemmas) do if k == key then return page end end
    return nil
end

local function reopen(cqi, page)
    cm:callback(function()
        local c = cm:get_character_by_cqi(cqi)
        if c and not c:is_null_interface() then open_page(c, page) end
    end, 0.3)
end

local function on_choice(context)
    local page = page_of_dilemma(context:dilemma())
    local pending = cm:get_saved_value(pending_key)
    cm:set_saved_value(pending_key, false)
    if not page or type(pending) ~= "string" then return end
    local cqi = tonumber(string.match(pending, "^(%d+)|"))
    local character = cqi and cm:get_character_by_cqi(cqi)
    if not character or character:is_null_interface() then return end
    local idx = context:choice() + 1

    if page == "slots" then
        if idx <= #D().slots then reopen(cqi, D().slots[idx].id) end
        return
    end
    if idx == 4 then reopen(cqi, "slots"); return end

    local slot
    for _, s in ipairs(D().slots) do if s.id == page then slot = s end end
    local rune = slot.runes[idx]
    local st = rune and next_state(cqi, page, rune.id)
    if st then
        -- золото уже списал payload (вариант был доступен только при достаточном запасе)
        set_slot(cqi, page, st.id, st.level)
        apply_runes(character)
        local _, school = total_effects(get_runes(cqi))
        log(string.format("%s: %s -> %s ур. %d%s", tostring(cqi), page, st.id, st.level,
            school and (", комплект " .. school) or ""))
        core:trigger_event("ScriptEventHeRuneInscribed", character, page, st.id, st.level)
    end
    reopen(cqi, page)
end

----------------------------------------------------------------- кнопка и выбор героя
local selected_cqi = nil

local function runes_tooltip(cqi)
    if not cqi then return "Руны героя\nВыделите героя или лорда, затем нажмите кнопку." end
    local runes = get_runes(cqi)
    local lines = { "Руны героя" }
    for _, s in ipairs(D().slots) do
        local r = runes[s.id]
        local def = r and rune_def(s.id, r.id)
        lines[#lines + 1] = s.title .. ": " .. (def and (def.name .. " ур. " .. r.level) or "пусто")
    end
    local _, school = total_effects(runes)
    if school then lines[#lines + 1] = "Комплект: " .. school end
    return table.concat(lines, "\n")
end

local function update_button()
    local root = core:get_ui_root()
    local btn = root and find_uicomponent(root, BUTTON_ID)
    if btn then btn:SetTooltipText(runes_tooltip(selected_cqi), true) end
end

local function create_button()
    local root = core:get_ui_root()
    if not root or find_uicomponent(root, BUTTON_ID) then return end
    local parents = {
        { "hud_campaign", "faction_buttons_docker", "button_group_management" },
        { "hud_campaign", "faction_buttons_docker" },
    }
    for _, path in ipairs(parents) do
        local parent = find_uicomponent(root, unpack(path))
        if parent then
            local ok, comp = pcall(function() return parent:CreateComponent(BUTTON_ID, "ui/templates/round_medium_button") end)
            if ok and comp then
                local btn = UIComponent(comp)
                btn:SetImagePath(BUTTON_ICON)
                btn:SetVisible(true)
                pcall(function() btn:AddScriptEventReporter() end)
                update_button()
                log("кнопка рун создана")
                return
            end
        end
    end
    log("кнопку рун создать не удалось")
end

----------------------------------------------------------------- запуск
cm:add_first_tick_callback(function()
    if not HE_RUNES_DATA then log("ОШИБКА: нет he_runes_data.lua"); return end

    -- переприменяем руны всем персонажам фракции (на случай изменения данных рун)
    local faction = cm:get_faction(FACTION)
    if faction and not faction:is_null_interface() then
        local chars = faction:character_list()
        for i = 0, chars:num_items() - 1 do
            local c = chars:item_at(i)
            pcall(apply_runes, c)
        end
    end

    local is_local = cm:get_local_faction_name(true) == FACTION
    if is_local then
        create_button()
        core:add_listener(P .. "selected", "CharacterSelected",
            function(context) return context:character():faction():name() == FACTION end,
            function(context) selected_cqi = context:character():command_queue_index(); update_button() end, true)
        core:add_listener(P .. "click", "ComponentLClickUp",
            function(context) return context.string == BUTTON_ID end,
            function()
                if not selected_cqi or not cm:is_local_players_turn() then update_button(); return end
                local f = cm:get_faction(FACTION)
                CampaignUI.TriggerCampaignScriptEvent(f:command_queue_index(), UI_EVENT .. "|" .. selected_cqi)
            end, true)
        core:add_listener(P .. "hover", "ComponentMouseOn",
            function(context) return context.string == BUTTON_ID end,
            function() update_button() end, true)
    end

    -- синхронизировано для мультиплеера
    core:add_listener(P .. "ui_trigger", "UITrigger",
        function(context) return string.match(context:trigger(), "^" .. UI_EVENT .. "|%d+$") ~= nil end,
        function(context)
            local cqi = tonumber(string.match(context:trigger(), "|(%d+)$"))
            local c = cm:get_character_by_cqi(cqi)
            if c and not c:is_null_interface() and c:faction():name() == FACTION then open_page(c, "slots") end
        end, true)

    core:add_listener(P .. "choice", "DilemmaChoiceMadeEvent",
        function(context) return page_of_dilemma(context:dilemma()) ~= nil end,
        function(context)
            local ok, err = pcall(on_choice, context)
            if not ok then log("ОШИБКА: " .. tostring(err)) end
        end, true)

    log("загружено")
end)

he_runes = {
    get_runes = get_runes, set_slot = set_slot, apply_runes = apply_runes, total_effects = total_effects,
    next_state = next_state, open_page = open_page, set_school = set_school,
}
