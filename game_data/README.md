# Файлы игры для разработки

Оригинальные `.pack` игры лежат **не в git**, а в приватном релизе **`game-data`** этого репозитория.
Обычная папка в git не подходит: GitHub не принимает файлы больше 100 МБ. В релиз можно загрузить файлы до 2 ГБ каждый.

> ⚠ Файлы игры защищены авторским правом. Держите репозиторий **приватным**, пока они здесь лежат.

## Как создать релиз и загрузить файлы (один раз)

1. Откройте репозиторий на GitHub → справа **Releases** → **Draft a new release**.
2. **Choose a tag** → введите `game-data` → **Create new tag: game-data on publish**.
3. Название любое, например «Файлы игры».
4. Перетащите файлы в поле **Attach binaries by dropping them here** (до 2 ГБ на файл).
5. Поставьте галочку **Set as a pre-release** и нажмите **Publish release**.

Добавлять файлы позже: откройте релиз → ✏️ **Edit** → перетащите файлы → **Update release**.

## Какие файлы нужны

Папка `…/steamapps/common/Total War WARHAMMER III/data/`:

| Файл | Зачем |
|---|---|
| пак с папкой `db/`: `db.pack`, если он есть, иначе `data.pack` | все таблицы игры |
| `local_ru.pack` (или `local_en.pack`) | тексты, названия, описания |

Как понять, где лежат таблицы: откройте пак в RPFM. Если внутри есть папка `db`, это нужный пак.
Если какой-то файл больше 2 ГБ, напишите: придумаем другой способ.

## Как я с ними работаю

`tools/game_data.py` скачивает файлы релиза и читает таблицы прямо из паков. Пак целиком в память не загружается, поэтому большие паки читаются без проблем.

```bash
python3 tools/game_data.py download --cache /путь/к/кэшу
python3 tools/game_data.py find  db.pack --schema schema_wh3.ron wh2_main_dwf_spine_of_sotek_dwarfs
python3 tools/game_data.py dump  db.pack --schema schema_wh3.ron --out out/ factions slot_sets
python3 tools/game_data.py loc   local_ru.pack "Хребет Сотека"
```

Схема `schema_wh3.ron` берётся из [rpfm-schemas](https://github.com/Frodo45127/rpfm-schemas).
