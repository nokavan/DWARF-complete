--[[
    Древние Родословные Гномов (Dwarf Ancient Lineages)
    Total War: WARHAMMER III, кампания (Immortal Empires / Realm of Chaos)

    Аналог механики родословных вампиров, но для гномов:
      * 5 родословных Предков (Гримнир, Валайя, Грунгни, Моргрим, Тунгни);
      * каждую можно прокачивать БЕСКОНЕЧНО;
      * плата — Клятвенное Золото (Oathgold) вместо крови;
      * цена растёт с каждым уровнем;
      * бонусы выдаются кастомным эффект-бандлом, значения пересчитываются под уровень;
      * каждые N уровней — «Веха рода» с дополнительным усилением.

    Открытие меню — кнопка в интерфейсе кампании (или авто-напоминание в начале хода).
    Выбор делается через динамическую дилемму: в ней видно цену и бонусы следующего уровня.
    Совместимо с мультиплеером (клик проходит через UITriggerScriptEvent).
]]

local MOD = "dwf_al"

----------------------------------------------------------------------------------------
-- НАСТРОЙКИ (можно менять)
----------------------------------------------------------------------------------------
local CONFIG = {
    culture = "wh_main_dwf_dwarfs",

    -- Ключ ресурса Клятвенного Золота. Скрипт пробует ключи по порядку и берёт первый,
    -- который есть у фракции. ВАЖНО: первый ключ должен совпадать с ключом в
    -- таблице pooled_resource_factor_junctions этого мода (rpfm_tsv/...junctions.tsv).
    oathgold_keys = { "dwf_oathgold", "wh3_dlc25_dwf_oathgold", "wh3_main_dwf_oathgold" },

    -- Фактор, через который списывается золото (определён в БД мода)
    factor_key = "dwf_al_lineages",

    -- Цена уровня: base + step * текущий_уровень + quad * уровень^2
    -- (уровень 0 -> 1 = «Пробуждение рода», у него отдельная цена)
    awaken_cost = 80, 
    cost_base   = 60,
    cost_step   = 30,
    cost_quad   = 0,

    -- Каждые столько уровней — «Веха рода»: все эффекты рода усиливаются на milestone_bonus
    milestone_every = 5,
    milestone_bonus = 0.10,   -- +10% к эффектам рода за каждую веху

    -- Напоминание в начале хода: "never" | "when_affordable" | "no_button"
    -- no_button — показывать дилемму только если кнопку создать не удалось
    auto_prompt = "no_button",

    -- Пусть ИИ-гномы тоже тратят Клятвенное Золото на родословные
    ai_enabled = false,
    ai_keep_reserve = 150,     -- ИИ не тратит, если останется меньше

    debug = false,
}

--[[
    РОДОСЛОВНЫЕ И ИХ ЭФФЕКТЫ

    mode = "linear" -> значение = per_level * уровень                (растёт бесконечно)
    mode = "soft"   -> значение = cap * (1 - (1 - per_level/cap)^уровень)
                       (растёт бесконечно, но асимптотически стремится к cap —
                        чтобы, например, содержание не ушло в -100% и игра не сломалась)

    Ключи эффектов — стандартные ключи из таблицы effects игры. Если после патча
    какой-то ключ переименован, скрипт пропустит его и напишет предупреждение в лог.
]]
local LINEAGES = {
    {
        id = "grimnir",
        bundle = "dwf_al_bundle_grimnir",
        effects = {
            { key = "wh_main_effect_force_stat_melee_attack", scope = "faction_to_force_own", per_level = 1, mode = "linear" },
            { key = "wh_main_effect_force_stat_charge_bonus", scope = "faction_to_force_own", per_level = 2, mode = "linear" },
        },
    },
    {
        id = "valaya",
        bundle = "dwf_al_bundle_valaya",
        effects = {
            { key = "wh_main_effect_force_stat_melee_defence", scope = "faction_to_force_own",    per_level = 1, mode = "linear" },
            { key = "wh_main_effect_public_order_global",      scope = "faction_to_province_own", per_level = 1, mode = "soft", cap = 30 },
        },
    },
    {
        id = "grungni",
        bundle = "dwf_al_bundle_grungni",
        effects = {
            { key = "wh_main_effect_economy_gdp_mod_all",          scope = "faction_to_region_own", per_level = 3,  mode = "linear" },
            { key = "wh_main_effect_building_construction_cost_mod", scope = "faction_to_region_own", per_level = -2, mode = "soft", cap = -60 },
        },
    },
    {
        id = "morgrim",
        bundle = "dwf_al_bundle_morgrim",
        effects = {
            { key = "wh_main_effect_force_all_campaign_upkeep",               scope = "faction_to_force_own", per_level = -2, mode = "soft", cap = -60 },
            { key = "wh_main_effect_force_all_campaign_recruitment_cost_all", scope = "faction_to_force_own", per_level = -2, mode = "soft", cap = -60 },
        },
    },
    {
        id = "thungni",
        bundle = "dwf_al_bundle_thungni",
        effects = {
            { key = "wh_main_effect_force_stat_leadership", scope = "faction_to_force_own", per_level = 2, mode = "linear" },
            { key = "wh_main_effect_force_stat_armour",     scope = "faction_to_force_own", per_level = 2, mode = "linear" },
        },
    },
}

-- Дилеммы-«страницы» (по 4 варианта на дилемму — ограничение движка)
local DILEMMA_PAGE_1 = "dwf_al_dilemma_page_1"   -- Гримнир, Валайя, Грунгни, «Далее»
local DILEMMA_PAGE_2 = "dwf_al_dilemma_page_2"   -- Моргрим, Тунгни, «Назад», «Закрыть»
local LOCKED_BUNDLE  = "dwf_al_bundle_locked"     -- показывается на недоступном варианте

local PAGES = {
    [DILEMMA_PAGE_1] = { "grimnir", "valaya", "grungni", "next" },
    [DILEMMA_PAGE_2] = { "morgrim", "thungni", "back", "close" },
}
local CHOICE_KEYS = { "FIRST", "SECOND", "THIRD", "FOURTH" }

local BUTTON_ID   = "dwf_al_button"
local BUTTON_ICON = "ui/dwf_ancient_lineages/icon_lineages.png"
local UI_EVENT_OPEN = "dwf_al_open"

----------------------------------------------------------------------------------------
-- УТИЛИТЫ
----------------------------------------------------------------------------------------
local function log(msg)
    out("[DWF Ancient Lineages] " .. tostring(msg))
end
local function dlog(msg)
    if CONFIG.debug then log(msg) end
end

local lineage_by_id = {}
for _, l in ipairs(LINEAGES) do lineage_by_id[l.id] = l end

local function is_dwarf(faction)
    return faction and not faction:is_null_interface() and faction:culture() == CONFIG.culture
        and not faction:is_dead()
end

local function level_key(faction_key, lineage_id)
    return MOD .. "_lvl_" .. faction_key .. "_" .. lineage_id
end

local function get_level(faction_key, lineage_id)
    return cm:get_saved_value(level_key(faction_key, lineage_id)) or 0
end

local function set_level(faction_key, lineage_id, lvl)
    cm:set_saved_value(level_key(faction_key, lineage_id), lvl)
end

local function cost_for(level)
    -- level = текущий уровень; возвращает цену перехода на level+1
    if level <= 0 then return CONFIG.awaken_cost end
    return math.floor(CONFIG.cost_base + CONFIG.cost_step * level + CONFIG.cost_quad * level * level)
end

local resolved_oathgold_key = nil
local function oathgold_key(faction)
    if resolved_oathgold_key then return resolved_oathgold_key end
    local prm = faction:pooled_resource_manager()
    for _, k in ipairs(CONFIG.oathgold_keys) do
        local ok, res = pcall(function() return prm:resource(k) end)
        if ok and res and not res:is_null_interface() then
            resolved_oathgold_key = k
            log("Ресурс Клятвенного Золота найден: " .. k)
            return k
        end
    end
    return nil
end

local function get_oathgold(faction)
    local key = oathgold_key(faction)
    if not key then return 0 end
    return faction:pooled_resource_manager():resource(key):value()
end

local function effect_value(eff, level)
    if level <= 0 then return 0 end
    local milestones = math.floor(level / CONFIG.milestone_every)
    local mult = 1 + milestones * CONFIG.milestone_bonus
    local v
    if eff.mode == "soft" and eff.cap and eff.cap ~= 0 then
        local ratio = eff.per_level / eff.cap          -- доля капа за 1 уровень
        if ratio >= 1 then ratio = 0.99 end
        v = eff.cap * (1 - (1 - ratio) ^ level)
        -- вехи в soft-режиме приближают к капу, но не превышают его
        v = v * mult
        if math.abs(v) > math.abs(eff.cap) then v = eff.cap end
    else
        v = eff.per_level * level * mult
    end
    -- округление к целому (эффекты в игре целочисленные)
    if v >= 0 then return math.floor(v + 0.5) else return -math.floor(-v + 0.5) end
end

-- Строит кастомный бандл для родословной на заданном уровне
local function build_bundle(lineage, level)
    local bundle = cm:create_new_custom_effect_bundle(lineage.bundle)
    if not bundle or bundle:is_null_interface() then
        log("ОШИБКА: не найден эффект-бандл " .. lineage.bundle .. " (проверьте БД мода)")
        return nil
    end
    for _, eff in ipairs(lineage.effects) do
        local v = effect_value(eff, level)
        if v ~= 0 then
            local ok, err = pcall(function() bundle:add_effect(eff.key, eff.scope, v) end)
            if not ok then
                log("ПРЕДУПРЕЖДЕНИЕ: эффект " .. eff.key .. " не добавлен: " .. tostring(err))
            end
        end
    end
    bundle:set_duration(0) -- бессрочно
    return bundle
end

local function apply_lineage(faction, lineage_id)
    local lineage = lineage_by_id[lineage_id]
    local level = get_level(faction:name(), lineage_id)
    if level <= 0 then return end
    local bundle = build_bundle(lineage, level)
    if bundle then
        cm:apply_custom_effect_bundle_to_faction(bundle, faction)
        dlog(faction:name() .. ": " .. lineage_id .. " -> уровень " .. level)
    end
end

local function reapply_all(faction)
    for _, l in ipairs(LINEAGES) do apply_lineage(faction, l.id) end
end

local function spend_oathgold(faction, amount)
    local key = oathgold_key(faction)
    if not key then return false end
    cm:faction_add_pooled_resource(faction:name(), key, CONFIG.factor_key, -amount)
    return true
end

-- Повышает уровень. pay = false, если золото уже списано payload'ом дилеммы.
local function level_up(faction, lineage_id, pay)
    local fk = faction:name()
    local level = get_level(fk, lineage_id)
    local cost = cost_for(level)
    if pay then
        if get_oathgold(faction) < cost then return false end
        spend_oathgold(faction, cost)
    end
    set_level(fk, lineage_id, level + 1)
    apply_lineage(faction, lineage_id)
    core:trigger_event("ScriptEventDwarfLineageLevelUp", faction, lineage_id, level + 1)
    log(fk .. ": род " .. lineage_id .. " поднят до уровня " .. (level + 1) .. " (цена " .. cost .. ")")
    return true
end

----------------------------------------------------------------------------------------
-- ДИЛЕММЫ
----------------------------------------------------------------------------------------
-- Какие варианты были оплачиваемы на момент показа (чтобы не повысить уровень
-- бесплатно, если игрок выбрал недоступный вариант)
local function affordable_key(faction_key, dilemma_key, idx)
    return MOD .. "_aff_" .. faction_key .. "_" .. dilemma_key .. "_" .. idx
end

local function launch_page(faction, dilemma_key)
    local key = oathgold_key(faction)
    if not key then
        log("ОШИБКА: у фракции " .. faction:name() .. " нет ресурса Клятвенного Золота. Проверьте CONFIG.oathgold_keys")
        return
    end

    local builder = cm:create_dilemma_builder(dilemma_key)
    local gold = get_oathgold(faction)

    for idx, entry in ipairs(PAGES[dilemma_key]) do
        local choice = CHOICE_KEYS[idx]
        local lineage = lineage_by_id[entry]
        local payload = cm:create_payload()

        if lineage then
            local level = get_level(faction:name(), entry)
            local cost = cost_for(level)
            local can = gold >= cost
            cm:set_saved_value(affordable_key(faction:name(), dilemma_key, idx), can)

            if can then
                -- цена (видна в окне дилеммы)
                payload:faction_pooled_resource_transaction(key, CONFIG.factor_key, -cost, false)
                -- бонусы следующего уровня (бандл заменит предыдущий того же рода)
                local bundle = build_bundle(lineage, level + 1)
                if bundle then payload:effect_bundle_to_faction(bundle) end
            else
                -- пустой информационный бандл «Недостаточно Клятвенного Золота» на 1 ход
                local locked = cm:create_new_custom_effect_bundle(LOCKED_BUNDLE)
                if locked and not locked:is_null_interface() then
                    locked:set_duration(1)
                    payload:effect_bundle_to_faction(locked)
                end
            end
        end
        builder:add_choice_payload(choice, payload)
    end

    cm:launch_custom_dilemma_from_builder(builder, faction)
end

local function open_menu(faction)
    if not is_dwarf(faction) then return end
    launch_page(faction, DILEMMA_PAGE_1)
end

local function on_dilemma_choice(context)
    local dilemma_key = context:dilemma()
    local page = PAGES[dilemma_key]
    if not page then return end

    local faction = context:faction()
    local idx = context:choice() + 1  -- choice() начинается с 0
    local entry = page[idx]
    if not entry then return end

    if lineage_by_id[entry] then
        local was_affordable = cm:get_saved_value(affordable_key(faction:name(), dilemma_key, idx))
        if was_affordable then
            -- золото уже списал payload; бандл уже применён payload'ом, но
            -- переприменяем на случай расхождений
            level_up(faction, entry, false)
        end
        -- после выбора — снова открыть ту же страницу, чтобы можно было качать дальше
        local fk = faction:name()
        cm:callback(function()
            local f = cm:get_faction(fk)
            if is_dwarf(f) and f:is_human() then launch_page(f, dilemma_key) end
        end, 0.3)
    elseif entry == "next" or entry == "back" then
        local target = (entry == "next") and DILEMMA_PAGE_2 or DILEMMA_PAGE_1
        local fk = faction:name()
        cm:callback(function()
            local f = cm:get_faction(fk)
            if is_dwarf(f) then launch_page(f, target) end
        end, 0.3)
    end
    -- "close" — ничего не делаем
end

----------------------------------------------------------------------------------------
-- КНОПКА В ИНТЕРФЕЙСЕ
----------------------------------------------------------------------------------------
local button_ok = false

local function build_tooltip(faction)
    local lines = { "[[col:yellow]]Древние Родословные[[/col]]",
                    "Клятвенное Золото: " .. tostring(get_oathgold(faction)), "" }
    local names = { grimnir = "Род Гримнира", valaya = "Род Валайи", grungni = "Род Грунгни",
                    morgrim = "Род Моргрима", thungni = "Род Тунгни" }
    for _, l in ipairs(LINEAGES) do
        local lvl = get_level(faction:name(), l.id)
        local status = (lvl > 0) and ("уровень " .. lvl) or "не пробуждён"
        table.insert(lines, names[l.id] .. ": " .. status .. "  (след.: " .. cost_for(lvl) .. ")")
    end
    return table.concat(lines, "\n")
end

local function update_button()
    local root = core:get_ui_root()
    local btn = root and find_uicomponent(root, BUTTON_ID)
    if not btn then return end
    local faction = cm:get_faction(cm:get_local_faction_name(true))
    if faction then btn:SetTooltipText(build_tooltip(faction), true) end
end

local function create_button()
    local root = core:get_ui_root()
    if not root then return false end
    if find_uicomponent(root, BUTTON_ID) then button_ok = true; return true end

    -- пробуем вставить кнопку рядом со стандартными кнопками фракции
    local parents = {
        { "hud_campaign", "faction_buttons_docker", "button_group_management" },
        { "hud_campaign", "faction_buttons_docker" },
        { "menu_bar", "buttongroup" },
    }
    local templates = { "ui/templates/round_medium_button", "ui/templates/round_small_button" }

    for _, path in ipairs(parents) do
        local parent = find_uicomponent(root, unpack(path))
        if parent then
            for _, tpl in ipairs(templates) do
                local ok, comp = pcall(function() return parent:CreateComponent(BUTTON_ID, tpl) end)
                if ok and comp then
                    local btn = UIComponent(comp)
                    btn:SetImagePath(BUTTON_ICON)
                    btn:SetVisible(true)
                    button_ok = true
                    update_button()
                    log("Кнопка создана в " .. table.concat(path, "/") .. " (" .. tpl .. ")")
                    return true
                end
            end
        end
    end

    -- запасной вариант: на корне интерфейса, в правом верхнем углу
    for _, tpl in ipairs(templates) do
        local ok, comp = pcall(function() return root:CreateComponent(BUTTON_ID, tpl) end)
        if ok and comp then
            local btn = UIComponent(comp)
            local sw, sh = core:get_screen_resolution()
            btn:MoveTo(sw - 420, 8)
            btn:SetImagePath(BUTTON_ICON)
            btn:SetVisible(true)
            button_ok = true
            update_button()
            log("Кнопка создана на корне интерфейса (" .. tpl .. ")")
            return true
        end
    end
    log("Не удалось создать кнопку — будет использоваться напоминание в начале хода")
    return false
end

----------------------------------------------------------------------------------------
-- ИИ
----------------------------------------------------------------------------------------
local function ai_spend(faction)
    if not CONFIG.ai_enabled then return end
    -- качаем самый дешёвый род, пока хватает золота сверх резерва (не больше 3 за ход)
    for _ = 1, 3 do
        local best, best_cost
        for _, l in ipairs(LINEAGES) do
            local c = cost_for(get_level(faction:name(), l.id))
            if not best_cost or c < best_cost then best, best_cost = l.id, c end
        end
        if get_oathgold(faction) - best_cost < CONFIG.ai_keep_reserve then return end
        level_up(faction, best, true)
    end
end

local function any_affordable(faction)
    local gold = get_oathgold(faction)
    for _, l in ipairs(LINEAGES) do
        if gold >= cost_for(get_level(faction:name(), l.id)) then return true end
    end
    return false
end

----------------------------------------------------------------------------------------
-- ИНИЦИАЛИЗАЦИЯ
----------------------------------------------------------------------------------------
local function init()
    log("Загрузка...")

    -- переприменяем бандлы при загрузке (на случай изменения настроек/эффектов)
    for _, faction in model_pairs(cm:model():world():faction_list()) do
        if is_dwarf(faction) then reapply_all(faction) end
    end

    local local_faction = cm:get_faction(cm:get_local_faction_name(true))
    local local_is_dwarf = is_dwarf(local_faction)

    if local_is_dwarf then
        create_button()

        core:add_listener(MOD .. "_button_click", "ComponentLClickUp",
            function(context) return context.string == BUTTON_ID end,
            function()
                if not cm:is_local_players_turn() then return end
                local f = cm:get_faction(cm:get_local_faction_name(true))
                CampaignUI.TriggerCampaignScriptEvent(f:command_queue_index(), UI_EVENT_OPEN)
            end, true)

        core:add_listener(MOD .. "_button_hover", "ComponentMouseOn",
            function(context) return context.string == BUTTON_ID end,
            function() update_button() end, true)
    end

    -- синхронизированное событие (MP-safe): открываем меню у нужной фракции
    core:add_listener(MOD .. "_ui_trigger", "UITriggerScriptEvent",
        function(context) return context:trigger() == UI_EVENT_OPEN end,
        function(context)
            local f = cm:model():faction_for_command_queue_index(context:faction_cqi())
            open_menu(f)
        end, true)

    core:add_listener(MOD .. "_dilemma_choice", "DilemmaChoiceMadeEvent",
        function(context) return PAGES[context:dilemma()] ~= nil end,
        on_dilemma_choice, true)

    core:add_listener(MOD .. "_turn_start", "FactionTurnStart",
        function(context) return is_dwarf(context:faction()) end,
        function(context)
            local f = context:faction()
            if f:is_human() then
                local mode = CONFIG.auto_prompt
                if (mode == "when_affordable" or (mode == "no_button" and not button_ok))
                    and any_affordable(f) then
                    open_menu(f)
                end
                if f:name() == cm:get_local_faction_name(true) then
                    if not button_ok then create_button() end
                    update_button()
                end
            else
                ai_spend(f)
            end
        end, true)

    log("Готово. Родословных: " .. #LINEAGES)
end

cm:add_first_tick_callback(function()
    local ok, err = pcall(init)
    if not ok then log("ОШИБКА инициализации: " .. tostring(err)) end
end)

-- Внешний API для других модов / консоли
dwf_ancient_lineages = {
    get_level = get_level,
    level_up = level_up,
    open_menu = open_menu,
    cost_for = cost_for,
    config = CONFIG,
    lineages = LINEAGES,
}
