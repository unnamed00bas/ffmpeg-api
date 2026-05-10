# 06. Субтитры — `SubtitleProcessor`

> **Источник:** `app/processors/subtitle_processor.py`,
> `app/utils/subtitle_parsers.py`, `app/schemas/subtitle.py`,
> `app/queue/tasks.py:subtitle_task`, `app/api/v1/tasks.py:create_subtitle_task`.

## 6.1 Назначение

Прожечь субтитры в видео (hard‑subtitles). Поддерживаются 4 формата:
**SRT**, **VTT**, **ASS**, **SSA**. Источник субтитров — либо файл, либо
**массив реплик** прямо в JSON‑запросе (тогда внутри генерируется временный
SRT и подаётся в FFmpeg).

Все 4 формата обрабатываются одним фильтром FFmpeg — **`subtitles`** (он
же `subtitles=...`, бэкенд — libass).

## 6.2 Эндпоинт API

```
POST /api/v1/tasks/subtitles
{
  "video_file_id": 123,
  "subtitle_file_id": 456,            // ИЛИ subtitle_text
  "subtitle_text": [
    {"start": 0.0,  "end": 2.5, "text": "Hello"},
    {"start": 3.0,  "end": 6.0, "text": "World"}
  ],
  "format": "SRT",                    // "SRT" | "VTT" | "ASS" | "SSA"
  "style": {
    "font_name":     "Arial",
    "font_size":     20,
    "primary_color": "&H00FFFFFF",
    "outline_color": "&H00000000",
    "back_color":    "&H80000000",
    "bold":   false,
    "italic": false,
    "outline": 2.0,
    "shadow":  2.0,
    "alignment": 2,
    "margin_l": 10, "margin_r": 10, "margin_v": 10
  },
  "position": {"position": "bottom", "margin_y": 10},
  "output_filename": "out.mp4"
}
```

Должен быть указан **либо** `subtitle_file_id`, **либо** `subtitle_text`.
В коде это проверяется и в схеме, и в процессоре.

## 6.3 Pydantic‑схемы

```python
class SubtitleFormat(str, Enum):
    SRT = "SRT"; VTT = "VTT"; ASS = "ASS"; SSA = "SSA"

class SubtitleStyle(BaseModel):
    font_name:     str   = "Arial"
    font_size:     int   = 20    # 10..72

    primary_color:   str = "&H00FFFFFF"   # &HAABBGGRR
    secondary_color: str = "&H000000FF"
    outline_color:   str = "&H00000000"
    back_color:      str = "&H80000000"

    bold:      bool = False
    italic:    bool = False
    underline: bool = False
    strikeout: bool = False

    scale_x: float = 1.0   # 0..10
    scale_y: float = 1.0
    spacing: float = 0.0   # межсимвольный интервал
    angle:   float = 0.0   # -360..360

    border_style: int = 1  # 0..4 (1 — outline+drop shadow, 3 — opaque box)
    outline:      float = 2.0
    shadow:       float = 2.0

    alignment: int = 2     # 1..9 (как Numpad: 1=BL, 2=BC, ..., 9=TR)
    margin_l:  int = 10
    margin_r:  int = 10
    margin_v:  int = 10
    encoding:  int = 1     # 0..255

class SubtitlePosition(BaseModel):
    position: Optional[str] = None    # "top" | "center" | "bottom"
    margin_x: int = 10
    margin_y: int = 10

class SubtitleRequest(BaseModel):
    video_file_id:    FileSource
    subtitle_file_id: Optional[FileSource] = None
    subtitle_text:    Optional[List[Dict[str, Any]]] = None    # [{start, end, text}, ...]
    format:    SubtitleFormat   = SubtitleFormat.SRT
    style:     SubtitleStyle    = SubtitleStyle()
    position:  SubtitlePosition = SubtitlePosition()
    output_filename: Optional[str] = None
```

> Цвет в схеме — формат **ASS** (`&HAABBGGRR`, **8 hex‑символов**), не
> `#RRGGBB`. Так его понимает libass без дополнительной конвертации.
> Коды компонентов идут в порядке alpha → blue → green → red.
> В ASS значение alpha **0 = непрозрачно**, **255 = полностью прозрачно**.

## 6.4 Конфигурация процессора

```python
config = {
    "video_path":         "/tmp/.../video.mp4",
    "subtitle_file_path": "/tmp/.../subs.srt",   # один из двух
    "subtitle_text":      [{...}, {...}],         # один из двух
    "format":             SubtitleFormat.SRT,     # либо строка "SRT"
    "style":              SubtitleStyle(...),     # объект (не dict)
    "position":           SubtitlePosition(...),
    "output_path":        "/tmp/.../out.mp4",
    "timeout":            3600,
}
```

В Celery‑задаче (`subtitle_task`) словари `style`/`position` из JSON
конвертируются обратно в Pydantic‑объекты:

```python
if isinstance(style,    dict): style    = SubtitleStyle(**style)
if isinstance(position, dict): position = SubtitlePosition(**position)
```

## 6.5 Валидация

`validate_input()` бросает `FFmpegValidationError`, если:
1. Нет `video_path` или он не существует.
2. ffprobe не вернул признак видео (`info["has_video"]` — это значение
   ожидается, но в текущем `get_video_info` его нет; проверка по факту
   ловит исключение из `ffprobe`).
3. Не указан ни `subtitle_file_path`, ни `subtitle_text`.
4. Если указан `subtitle_file_path` — файл не существует.
5. Если `subtitle_file_path` указан, **не указан `format`** —
   выбрасывает «Subtitle format not specified».
6. Если `subtitle_text` — не список или пустой.
7. Каждая запись — `dict` с полями `start, end, text`, и `start < end`.

> Замечание: ключ `info["has_video"]` в `validate_input()` — артефакт прежней
> версии, в текущем `get_video_info` его нет. Проверка существования видео
> работает за счет того, что ffprobe бросит исключение, если файл нечитаем.
> При портировании сделайте проверку явной, например через
> `info.get("video_codec") is not None`.

## 6.6 Парсеры субтитров

Все 4 формата парсятся в **унифицированный список**:

```python
[
    {"start": float_seconds,
     "end":   float_seconds,
     "text":  str,
     # ASS дополнительно:
     "layer": int, "style": str, "name": str,
     "margin_l": int, "margin_r": int, "margin_v": int, "effect": str,
    },
    ...
]
```

### SRT — `parse_srt`

Формат:
```
1
00:00:01,000 --> 00:00:04,000
Hello World
```

Время — `HH:MM:SS,mmm` (запятая перед миллисекундами). Парсится регуляркой,
переводится в float (секунды). Многострочный текст склеивается через `\n`.

### VTT — `parse_vtt`

Формат:
```
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello World
```

Время — `HH:MM:SS.mmm` (точка). Заголовок `WEBVTT`, блоки `NOTE`/`STYLE`
пропускаются. Cue settings (`align:center`) после таймкода игнорируются.

### ASS — `parse_ass`

Формат:
```
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World
```

Поля разделены **запятыми**. Текст может содержать запятые (`split(",", 9)` —
максимум 10 частей, последняя — текст, в нем запятые сохраняются).
Время `H:MM:SS.cc` (двузначные «сотые», не миллисекунды).

ASS‑теги внутри текста (`{\b1}`, `{\i1}`, `{\c&H00FFFFFF&}`) **не разбираются** —
оставляются как есть. FFmpeg/libass поймет их при рендере.

### SSA — `parse_ssa`

```python
def parse_ssa(content): return parse_ass(content)
```

SSA — предшественник ASS, формат блоков `Dialogue:` идентичен.

## 6.7 Генерация SRT из `subtitle_text` массива

Если в запросе пришел `subtitle_text`, процессор генерирует временный SRT‑файл:

```python
def _format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# Каждая запись:
# 1
# 00:00:01,000 --> 00:00:04,000
# Hello world
```

Генерация всегда в SRT, **независимо от** запрошенного `format` (FFmpeg
позже сам разберется). Это упрощение — если нужен ASS‑файл с тегами,
надо собирать вручную (см. 6.9).

## 6.8 Команда FFmpeg

### Для SRT/VTT
```
ffmpeg -y -i <video> \
  -vf "subtitles='<subs>':force_style='<style_str>'" \
  -c:a copy \
  <output>
```

`force_style` — это **способ переопределить стили** для SRT/VTT, который
libass понимает. Поля те же, что в ASS: `Fontname`, `Fontsize`, `Bold`,
`Italic`, `PrimaryColour`, `OutlineColour`, `Outline`, `Shadow`, `Alignment`.
Несколько полей джойнятся через **запятую внутри одного `force_style`**, а
несколько фильтров (например `force_style` + `Alignment=6`) — через
**запятую** в значении.

В коде сборка `force_style` для SRT/VTT:

```python
style_parts = []
if style.font_name:    style_parts.append(f"Fontname={style.font_name}")
if style.font_size:    style_parts.append(f"Fontsize={style.font_size}")
if style.bold:         style_parts.append("Bold=1")
if style.italic:       style_parts.append("Italic=1")
if style.primary_color: style_parts.append(f"PrimaryColour={style.primary_color}")
if style.outline_color: style_parts.append(f"OutlineColour={style.outline_color}")
if style.outline:      style_parts.append(f"Outline={style.outline:.1f}")
if style.shadow:       style_parts.append(f"Shadow={style.shadow:.1f}")
if style.alignment:    style_parts.append(f"Alignment={style.alignment}")

style_str = ",".join(style_parts)
filter_opts.append(f"force_style='{style_str}'")
```

### Для ASS/SSA
```
ffmpeg -y -i <video> \
  -vf "subtitles='<subs>'" \
  -c:a copy \
  <output>
```

Стили из `SubtitleStyle` в текущей реализации применяются для ASS/SSA через
**модификацию ASS‑файла на лету**, а не через `force_style` (см. 6.9).

### Позиционирование (`position.position`)

Если задана `position` — добавляется в конец фильтра как `Alignment=N`:

| `position` | Alignment | Расположение |
| ---------- | --------- | ------------ |
| `top`      | `6`       | top‑center  |
| `center`   | `5`       | middle‑center |
| `bottom`   | `2`       | bottom‑center (default) |

Числовая семантика (libass / SSA NumPad):
```
7  8  9        top-left  top-center  top-right
4  5  6        mid-left  mid-center  mid-right
1  2  3        bot-left  bot-center  bot-right
```

В отдельных случаях (для SRT/VTT) опция оборачивается в `force_style='Alignment=N'`,
для ASS/SSA — просто `Alignment=N` после двоеточия в фильтре. Это
**не идентично**, см. код.

## 6.9 Inplace‑модификация ASS‑файла со стилем `Default`

Только для ASS/SSA. Перед запуском FFmpeg процессор:
1. Читает `subtitle_file_to_use` (UTF‑8, errors=ignore).
2. Если есть секция `[V4+ Styles]`:
   - Генерирует строку `Style: Default,...` из переданного `SubtitleStyle`
     (см. `_generate_ass_style`).
   - Если в файле уже есть `Style: Default,...` — **заменяет** ее регуляркой.
   - Если нет — **добавляет** сразу после заголовка `[V4+ Styles]`.
3. Записывает результат во **новый** временный файл (`styled_xxx.ass`),
   который потом подается в `subtitles=...` фильтр.

Формат `Style:` строки — стандартный ASS:

```
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,
       0,0,0,0,1.0,1.0,0.0,0.0,1,2.0,2.0,2,10,10,10,1
```

(в одну строку, без переноса).

## 6.10 Прогресс

В `subtitle_processor.py` прогресс масштабируется в диапазон **30–95%**
(чтобы 0–30% «зарезервировать» под загрузку и подготовку файлов):

```python
def progress_cb(p):
    if p is not None:
        scaled = 30.0 + (p / 100.0) * 65.0
        update_progress(scaled)
```

В начале `process()` явно ставится `update_progress(10.0)` (когда subtitle
файл создан/выбран) и `update_progress(30.0)` (после возможной модификации
ASS). После завершения — `update_progress(100.0)`.

## 6.11 Полный пример

Запрос:
```json
{
  "video_file_id": 1,
  "subtitle_text": [
    {"start": 1.0, "end": 4.0, "text": "Hello"},
    {"start": 5.0, "end": 8.0, "text": "World"}
  ],
  "format": "SRT",
  "style": {
    "font_name": "Arial", "font_size": 24, "bold": true,
    "primary_color": "&H00FFFFFF", "outline_color": "&H00000000",
    "outline": 2.0, "shadow": 1.0, "alignment": 2
  },
  "position": {"position": "bottom"}
}
```

1) В `/tmp/...subtitle_xxx.srt` будет:
```
1
00:00:01,000 --> 00:00:04,000
Hello

2
00:00:05,000 --> 00:00:08,000
World
```

2) Команда FFmpeg (примерно):
```
ffmpeg -y -i input.mp4 \
  -vf "subtitles='/tmp/...subtitle_xxx.srt':\
force_style='Fontname=Arial,Fontsize=24,Bold=1,PrimaryColour=&H00FFFFFF,\
OutlineColour=&H00000000,Outline=2.0,Shadow=1.0,Alignment=2'" \
  -c:a copy \
  output.mp4
```

## 6.12 Edge cases / частые проблемы

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| Субтитры не появляются | путь к файлу содержит `:` (Windows `C:\...`) — конфликт с разделителем фильтра | заворачивать путь в одинарные кавычки и/или использовать прямые слеши |
| Кракозябры | файл не UTF‑8 | конвертировать (`iconv -f cp1251 -t utf-8`) |
| Шрифт не применяется | `Arial` нет в системе — libass подставит fallback | установить пакет шрифтов (`fonts-liberation`, `fonts-dejavu`); либо передать `force_style='Fontname=DejaVu Sans'` |
| Цвет не такой | формат не `&HAABBGGRR` (alpha+BGR), а перепутан с `#RGB` | использовать ASS‑формат: `&H00FFFFFF` = непрозрачный белый |
| Позиция не меняется | для ASS — стили в самом файле перевешивают `force_style`; **в этом коде** для ASS позиция выставляется не через force_style, а как отдельный `Alignment=N` после двоеточия | для гарантии — модифицируйте ASS файл (см. 6.9) |
| Multiline в `subtitle_text` | переносы в `text` сохранятся как есть в SRT, libass их отрисует на нескольких строках | OK |
| Отрицательные `start`/`end` | SRT не поддерживает | проверить на стороне клиента |
| `start >= end` | валидируется, бросается `FFmpegValidationError` | — |

## 6.13 Минимальная реализация (для SRT)

```python
import asyncio, tempfile, os

async def burn_subs(video, srt_text_or_path, out, ffmpeg="ffmpeg"):
    if not os.path.isfile(srt_text_or_path):
        # Кладем текст во временный SRT
        fd, srt_path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_text_or_path)
    else:
        srt_path = srt_text_or_path
    cmd = [
        ffmpeg, "-y", "-i", video,
        "-vf", f"subtitles='{srt_path}'",
        "-c:a", "copy",
        out,
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
```
