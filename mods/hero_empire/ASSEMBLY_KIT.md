# Сборка стартовой позиции в Assembly Kit

Нужна один раз, а потом после каждого изменения фракции, героев или стартовых данных.

## 1. Скачать правки

[hero_empire_ak_patch.zip](../../../releases/download/latest/hero_empire_ak_patch.zip) из релиза `latest`.
Архив делает CI из оригинальных данных Assembly Kit (`db.zip` в релизе `game-data`) и наших таблиц
(`_gen/gen_ak_patch.py`). Внутри лежит `PATCH_REPORT.txt` со списком изменений.

## 2. Сделать резервную копию

Скопируй папку `…/Total War WARHAMMER III/assembly_kit/raw_data/db` целиком куда-нибудь рядом, например в `db_backup`.
Правки заменяют 11 файлов в этой папке. Чтобы откатиться, верни копию.

## 3. Положить правки

Распакуй архив в папку `assembly_kit` так, чтобы файлы из `raw_data/db` архива заменили одноимённые файлы.

Что меняется (все остальные записи остаются байт в байт как были):

| Файл | Изменение |
|---|---|
| `cultures`, `cultures_subcultures`, `factions` | + культура, подкультура и фракция Империи героев |
| `technology_node_sets`, `technology_nodes`, `technology_node_links` | + дерево технологий Империи героев |
| `start_pos_factions` | запись Хребта Сотека → `he_faction_hero_empire`, играбельная, крупная |
| `start_pos_characters` | лидер → имперский лорд |
| `start_pos_land_units` | стартовая армия → имперские отряды |
| `start_pos_regions`, `start_pos_settlements` | Рудник Бородатых Черепов и Трижды Проклятый Пик → наши, имперские здания |

## 4. Собрать стартовую позицию

1. Запусти **BOB** (`assembly_kit/binaries/BOB.exe` или из лаунчера Assembly Kit).
2. Выбери кампанию `wh3_main_combi` (Immortal Empires) и процесс сборки стартовой позиции (**startpos**).
3. Нажми **Start** и дождись окончания. Если BOB покажет ошибки, сделай скриншот: они и есть то, что нужно поправить.
4. Готовый файл появится в `assembly_kit/retail/data/campaigns/wh3_main_combi/startpos.esf`.

## 5. Отправить результат

Запакуй `startpos.esf` в zip и загрузи в релиз `game-data` (поле **Attach binaries**).
Я проверю его разбором (`tools/esf_dump.py`) и положу в пак мода как `campaigns/wh3_main_combi/startpos.esf`.
