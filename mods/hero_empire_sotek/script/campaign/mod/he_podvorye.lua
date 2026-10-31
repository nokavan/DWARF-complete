--[[
    Империя героев (Хребет Сотека) — ПОДВОРЬЯ
    Подгород в землях союзника: наш герой основывает его в регионе союзника или вассала.
    Здания подворья усиливают город союзника (экономика, оборона, мобильность, снабжение армий)
    и дают нам доход, опыт героев и узел сети троп.

    Механика движка — "чужие слоты" (foreign slots), как у ковенов Нефераты и подгородов скавенов.
    Все функции движка ниже взяты из скриптов Creative Assembly:
      cm:add_foreign_slot_set_to_region_for_faction, cm:remove_faction_foreign_slots_from_region,
      region:foreign_slot_manager_for_faction, faction:foreign_slot_managers, cm:char_is_agent,
      cm:trigger_dilemma_with_targets, cm:treasury_mod, cm:make_region_visible_in_shroud,
      cm:apply_dilemma_diplomatic_bonus, faction:allied_with, faction:is_vassal_of.

    Цикл:
      1) В начале хода скрипт ищет нашего героя (не лорда) в регионе союзника/вассала без подворья.
      2) Игроку приходит дилемма «Основать подворье» (с героем и регионом на карте); ИИ решает сам.
      3) Подворье живёт, пока владелец региона — союзник/вассал. Если союз разорван,
         эффекты для союзника выключаются условием в БД, а через N ходов подворье сносится.
]]

local CONFIG = {
    factions = { ["wh2_main_dwf_spine_of_sotek_dwarfs"] = true },
    slot_set = "he_slot_set_podvorye",
    dilemma = "he_dilemma_found_podvorye",
    found_cost = 1500,          -- должно совпадать с текстом дилеммы (_gen/gen_data.py)
    max_podvorye = 6,           -- лимит подворий (позже будет расти от столицы)
    hostile_grace_turns = 10,   -- сколько ходов подворье переживает разрыв союза
    decline_cooldown = 5,       -- через сколько ходов повторить предложение после «Не сейчас»
    ai_enabled = true,
    ai_chance = 25,             -- % шанс за ход, что ИИ основывает подворье при возможности
    ai_gold_reserve = 3000,
    diplomatic_bonus = 1,       -- разовый плюс к отношениям с союзником при основании
    debug = false,
}

local P = "he_pod_"

local function log(msg) out("[HE Podvorye] " .. tostring(msg)) end
local function dlog(msg) if CONFIG.debug then log(msg) end end

----------------------------------------------------------------- сохранение (только строки и числа)
local function list_key(fk) return P .. "list_" .. fk end

local function get_list(fk)
    local s = cm:get_saved_value(list_key(fk)) or ""
    local t = {}
    for k in string.gmatch(s, "[^,]+") do t[#t + 1] = k end
    return t
end

local function set_list(fk, t)
    cm:set_saved_value(list_key(fk), table.concat(t, ","))
end

local function in_list(t, key)
    for i, k in ipairs(t) do if k == key then return i end end
    return nil
end

local function hostile_key(fk, rk) return P .. "hostile_" .. fk .. "_" .. rk end
local function cooldown_key(fk, rk) return P .. "cd_" .. fk .. "_" .. rk end
local function pending_key(fk) return P .. "pending_" .. fk end

----------------------------------------------------------------- утилиты
local function is_our_faction(faction)
    return faction and not faction:is_null_interface() and CONFIG.factions[faction:name()] == true
end

local function is_friend(owner, faction)
    if not owner or owner:is_null_interface() then return false end
    if owner:name() == faction:name() then return false end
    return owner:allied_with(faction) or owner:is_vassal_of(faction)
end

local function has_podvorye(region, fk)
    local fsm = region:foreign_slot_manager_for_faction(fk)
    return fsm and not fsm:is_null_interface()
end

local function can_afford(faction, cost)
    local ok, gold = pcall(function() return faction:treasury() end)
    if not ok or type(gold) ~= "number" then return true end -- не удалось прочитать казну — не блокируем
    return gold >= cost
end

local function treasury_or_nil(faction)
    local ok, gold = pcall(function() return faction:treasury() end)
    if ok and type(gold) == "number" then return gold end
    return nil
end

----------------------------------------------------------------- основание / снос
local function found(faction, region)
    local fk, rk = faction:name(), region:name()
    local list = get_list(fk)
    if in_list(list, rk) or has_podvorye(region, fk) then return false end
    if #list >= CONFIG.max_podvorye then return false end
    if not can_afford(faction, CONFIG.found_cost) then
        log(fk .. ": не хватает золота на подворье в " .. rk)
        return false
    end

    cm:treasury_mod(fk, -CONFIG.found_cost)
    cm:add_foreign_slot_set_to_region_for_faction(faction:command_queue_index(), region:cqi(), CONFIG.slot_set)
    cm:make_region_visible_in_shroud(fk, rk)

    local owner = region:owning_faction()
    if CONFIG.diplomatic_bonus ~= 0 and owner and not owner:is_null_interface() then
        cm:apply_dilemma_diplomatic_bonus(fk, owner:name(), CONFIG.diplomatic_bonus)
    end

    list[#list + 1] = rk
    set_list(fk, list)
    cm:set_saved_value(hostile_key(fk, rk), 0)
    core:trigger_event("ScriptEventHePodvoryeFounded", faction, region)
    log(fk .. ": подворье основано в " .. rk)
    return true
end

local function remove(faction, region_key, region, reason)
    local fk = faction:name()
    if region and not region:is_null_interface() and has_podvorye(region, fk) then
        cm:remove_faction_foreign_slots_from_region(faction:command_queue_index(), region:cqi())
    end
    local list = get_list(fk)
    local i = in_list(list, region_key)
    if i then table.remove(list, i) end
    set_list(fk, list)
    cm:set_saved_value(hostile_key(fk, region_key), 0)
    log(fk .. ": подворье в " .. region_key .. " снесено (" .. reason .. ")")
end

----------------------------------------------------------------- ежеходное обслуживание
local function maintain(faction)
    local fk = faction:name()

    -- подхватить подворья, созданные не скриптом (на будущее: штатное действие героя)
    local list = get_list(fk)
    local fsms = faction:foreign_slot_managers()
    for i = 0, fsms:num_items() - 1 do
        local r = fsms:item_at(i):region()
        if r and not r:is_null_interface() and not in_list(list, r:name()) then
            list[#list + 1] = r:name()
        end
    end
    set_list(fk, list)

    local snapshot = get_list(fk)
    for _, rk in ipairs(snapshot) do
        local region = cm:get_region(rk)
        if not region or region:is_null_interface() then
            remove(faction, rk, nil, "регион не найден")
        elseif not has_podvorye(region, fk) then
            remove(faction, rk, region, "разрушено")
        elseif region:is_abandoned() then
            remove(faction, rk, region, "регион заброшен")
        else
            local owner = region:owning_faction()
            if owner and not owner:is_null_interface() and owner:name() == fk then
                remove(faction, rk, region, "регион стал нашим")
            elseif is_friend(owner, faction) then
                cm:set_saved_value(hostile_key(fk, rk), 0)
            else
                local n = (cm:get_saved_value(hostile_key(fk, rk)) or 0) + 1
                cm:set_saved_value(hostile_key(fk, rk), n)
                dlog(rk .. ": владелец не союзник, ход " .. n .. "/" .. CONFIG.hostile_grace_turns)
                if n > CONFIG.hostile_grace_turns then
                    remove(faction, rk, region, "союз не восстановлен")
                end
            end
        end
    end
end

----------------------------------------------------------------- поиск возможности основать
local function find_candidate(faction)
    local fk = faction:name()
    if #get_list(fk) >= CONFIG.max_podvorye then return nil end
    local turn = cm:turn_number()
    local chars = faction:character_list()
    for i = 0, chars:num_items() - 1 do
        local char = chars:item_at(i)
        if cm:char_is_agent(char) and char:has_region() then
            local region = char:region()
            if region and not region:is_null_interface() and not region:is_abandoned()
                and is_friend(region:owning_faction(), faction)
                and not has_podvorye(region, fk)
                and (cm:get_saved_value(cooldown_key(fk, region:name())) or 0) <= turn then
                return char, region
            end
        end
    end
    return nil
end

local function offer(faction)
    local fk = faction:name()
    local char, region = find_candidate(faction)
    if not char then return end

    if faction:is_human() then
        if cm:get_saved_value(pending_key(fk)) then return end
        if not can_afford(faction, CONFIG.found_cost) then return end
        cm:set_saved_value(pending_key(fk), region:name())
        local owner = region:owning_faction()
        cm:trigger_dilemma_with_targets(faction:command_queue_index(), CONFIG.dilemma,
            owner:command_queue_index(), 0, char:command_queue_index(), 0, region:cqi(), region:settlement():cqi())
        dlog("предложено подворье в " .. region:name())
    elseif CONFIG.ai_enabled then
        local gold = treasury_or_nil(faction)
        if gold and gold < CONFIG.found_cost + CONFIG.ai_gold_reserve then return end
        if cm:random_number(100) <= CONFIG.ai_chance then found(faction, region) end
    end
end

----------------------------------------------------------------- события
local function on_turn_start(context)
    local faction = context:faction()
    if not is_our_faction(faction) or faction:is_dead() then return end
    -- неотвеченная дилемма прошлого хода больше не актуальна
    cm:set_saved_value(pending_key(faction:name()), false)
    maintain(faction)
    offer(faction)
end

local function on_dilemma(context)
    local faction = context:faction()
    local fk = faction:name()
    local rk = cm:get_saved_value(pending_key(fk))
    cm:set_saved_value(pending_key(fk), false)
    if not rk then return end

    if context:choice() == 0 then
        local region = cm:get_region(rk)
        if region and not region:is_null_interface() and is_friend(region:owning_faction(), faction) then
            found(faction, region)
        end
    else
        cm:set_saved_value(cooldown_key(fk, rk), cm:turn_number() + CONFIG.decline_cooldown)
    end
end

cm:add_first_tick_callback(function()
    core:add_listener("he_podvorye_turn_start", "FactionTurnStart",
        function(context) return is_our_faction(context:faction()) end,
        function(context)
            local ok, err = pcall(on_turn_start, context)
            if not ok then log("ОШИБКА в начале хода: " .. tostring(err)) end
        end, true)

    core:add_listener("he_podvorye_dilemma", "DilemmaChoiceMadeEvent",
        function(context) return context:dilemma() == CONFIG.dilemma end,
        function(context)
            local ok, err = pcall(on_dilemma, context)
            if not ok then log("ОШИБКА в дилемме: " .. tostring(err)) end
        end, true)

    core:add_listener("he_podvorye_created", "ForeignSlotManagerCreatedEvent",
        function(context) return is_our_faction(context:requesting_faction()) end,
        function(context) log("подворье появилось в " .. context:region():name()) end, true)

    log("загружено")
end)

-- для других скриптов мода и для отладки
he_podvorye = {
    config = CONFIG,
    found = found,
    remove = remove,
    maintain = maintain,
    get_list = get_list,
}
