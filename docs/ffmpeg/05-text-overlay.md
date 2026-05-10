# 05. Наложение текста — `TextOverlay`

> **Источник:** `app/processors/text_overlay.py`, `app/schemas/text_overlay.py`,
> `app/queue/tasks.py:text_overlay_task`, `app/api/v1/tasks.py:create_text_overlay_task`.

Самый «богатый» процессор: использует фильтр `drawtext` с большим набором
параметров — позиция (абсолют/относ), стиль шрифта, фон, рамка, тень,
прозрачность, поворот и **9 типов анимаций** (fade/slide/zoom).

## 5.1 Эндпоинт API

```
POST /api/v1/tasks/text-overlay
{
  "video_file_id": 123,
  "text": "Hello World",

  "position": {
    "type": "relative",          // "absolute" | "relative"
    "position": "bottom-center", // (для relative) одно из 9 значений
    "margin_x": 20,
    "margin_y": 20,
    "x": 100, "y": 50            // (для absolute) — целые px
  },
  "style": {
    "font_family": "Arial",
    "font_size":   48,
    "font_weight": "bold",       // "normal" | "bold" | "100"..."900"
    "color":       "#FFFFFF",
    "alpha":       1.0
  },
  "background": {
    "enabled": true,
    "color":   "#000000",
    "alpha":   0.5,
    "padding": 10,
    "border_radius": 5
  },
  "border": {
    "enabled": false,
    "width":   2,
    "color":   "#000000"
  },
  "shadow": {
    "enabled":  false,
    "offset_x": 2,
    "offset_y": 2,
    "blur":     2,
    "color":    "#000000"
  },
  "animation": {
    "type":     "fade_in",       // см. ниже
    "duration": 1.0,
    "delay":    0.0
  },
  "rotation": 0,                 // -360..360
  "opacity":  1.0,                // 0..1 (общий)
  "start_time": 0.0,
  "end_time":   5.0,             // null = до конца видео

  "output_filename": "out.mp4"
}
```

## 5.2 Pydantic‑схемы

```python
class TextPositionType(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"

class TextPosition(BaseModel):
    type: TextPositionType = TextPositionType.RELATIVE
    x: int | None = None                    # для absolute
    y: int | None = None
    position: str | None = "center"         # для relative — 9 значений (см. ниже)
    margin_x: int = 10                      # ≥ 0
    margin_y: int = 10                      # ≥ 0

class TextStyle(BaseModel):
    font_family: str   = "Arial"
    font_size:   int   = 24                  # 8..200
    font_weight: str   = "normal"            # regex ^(normal|bold|100|...|900)$
    color:       str   = "white"             # regex ^#[0-9A-Fa-f]{6}$
    alpha:       float = 1.0                 # 0..1

class TextBackground(BaseModel):
    enabled: bool  = False
    color:   str   = "black"                  # ^#[0-9A-Fa-f]{6}$
    alpha:   float = 0.5
    padding: int   = 10
    border_radius: int = 5

class TextBorder(BaseModel):
    enabled: bool = False
    width:   int  = 2
    color:   str  = "black"

class TextShadow(BaseModel):
    enabled: bool  = False
    offset_x: int  = 2                        # -50..50
    offset_y: int  = 2
    blur:     int  = 2                        # 0..20
    color:    str  = "black"

class TextAnimationType(str, Enum):
    NONE = "none"; FADE_IN = "fade_in"; FADE_OUT = "fade_out"; FADE = "fade"
    SLIDE_LEFT = "slide_left"; SLIDE_RIGHT = "slide_right"
    SLIDE_UP   = "slide_up";   SLIDE_DOWN  = "slide_down"
    ZOOM_IN    = "zoom_in";    ZOOM_OUT    = "zoom_out"

class TextAnimation(BaseModel):
    type: TextAnimationType = TextAnimationType.NONE
    duration: float = 1.0
    delay:    float = 0.0

class TextOverlayRequest(BaseModel):
    video_file_id: FileSource
    text: str = Field(..., min_length=1, max_length=1000)
    position:   TextPosition   = TextPosition()
    style:      TextStyle      = TextStyle()
    background: TextBackground = TextBackground()
    border:     TextBorder     = TextBorder()
    shadow:     TextShadow     = TextShadow()
    animation:  TextAnimation  = TextAnimation()
    rotation:   int   = 0          # -360..360
    opacity:    float = 1.0        # 0..1
    start_time: float = 0.0
    end_time:   float | None = None
    output_filename: str | None = None
```

## 5.3 Валидация

- `text.strip()` — не должен быть пустым.
- `video_path` существует и читается ffprobe.
- `start_time < video_duration`.
- `end_time` (если задан) `≤ video_duration`.
- `end_time > start_time` (если задан).

## 5.4 Команда FFmpeg (общая структура)

```
ffmpeg -y -i <video> \
  -vf "drawtext=<param1>:<param2>:..." \
  -c:a copy \
  <output>
```

- Аудио всегда **копируется** (`-c:a copy`).
- Видео **перекодируется** (по умолчанию `libx264` в выходном MP4 — драйвер
  `ffmpeg` сам выберет, если не указан `-c:v`).
- Все наложение происходит в **одном** `drawtext` фильтре. Если нужно
  несколько надписей, в текущей реализации **придется делать несколько задач**
  (или модифицировать процессор, см. 5.13).

## 5.5 Сборка `drawtext` параметров (`_build_drawtext_params`)

Параметры собираются в список и потом джойнятся через `:`. Порядок:

1. `text='<escaped>'`
2. `fontfile='<font_path>'`
3. `fontsize=<int>`
4. `fontcolor=<&HAABBGGRR&>`
5. `x=<expr>`
6. `y=<expr>`
7. (если background) `box=1`, `boxcolor=...`, `boxborderw=<padding>`,
   `boxradius=<radius>`
8. (если border) `borderw=<int>`, `bordercolor=<...>`
9. (если shadow) `shadowx=<int>`, `shadowy=<int>`, `shadowcolor=<...>`,
   опционально `shadoww=<blur>`
10. (если rotation ≠ 0) `rotation=<град>`
11. (если opacity < 1) `alpha='<value>'`
12. (если animation) — `enable='between(t,a,b)'` + специфичные параметры
    (см. 5.10).

## 5.6 Экранирование текста (`_escape_text`)

В `drawtext` спецсимволы должны быть экранированы. В коде применяется
последовательно:

```python
escaped = text
escaped = escaped.replace("'", "'\\''")   # одинарная кавычка → '\''
escaped = escaped.replace(":", "\\:")
escaped = escaped.replace("=", "\\=")
escaped = escaped.replace("#", "\\#")
escaped = escaped.replace("[", "\\[")
escaped = escaped.replace("]", "\\]")
escaped = escaped.replace("{", "\\{")
escaped = escaped.replace("}", "\\}")
escaped = escaped.replace("%", "\\%")
escaped = escaped.replace("\\", "\\\\")    # ← после остальных, иначе двойная экранировка
```

> ⚠️ В текущей реализации `\\` ставится **последним**, что технически неверно
> (правильнее экранировать backslash **первым**, иначе он удвоит уже
> экранированные `\:` → `\\:`). На практике в большинстве случаев работает,
> но при портировании имеет смысл переставить `\` в начало последовательности.

Для **многострочного текста** (с `\n`) drawtext поддерживает явный перенос
через `\n` в параметре `text=`, но в текущем коде преобразования нет — если
нужно разные строки, передавайте `\n` уже в исходном `text` (или
оборачивайте в HTML‑подобный синтаксис не получится — фильтр это не
поддерживает).

## 5.7 Конвертация цвета (`_color_to_hex`)

Вход: `#RRGGBB` (например `#FF8800`) и `alpha` (`0.0–1.0`).
Выход — формат `&HAABBGGRR&` (FFmpeg ASS‑совместимый):

```python
hex_color = color.lstrip("#")
r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
a = int(255 * alpha)                          # 0..255
return f"&H{a:02X}{b}{g}{r}&"                 # обратный порядок BGR + alpha
```

Пример: `#FF8800`, alpha=0.5 →
- `a = int(255*0.5) = 127 → 7F`
- `&H7F0088FF&`

> **Важно:** в ASS‑формате 0 — полностью непрозрачно, 255 — полностью
> прозрачно. Эта формула делает наоборот: alpha=1 → A=`FF`, alpha=0 → A=`00`.
> На практике для drawtext это ок, потому что drawtext интерпретирует это
> как «дополнительно к fontcolor». Если будете повторять для libass —
> значение alpha надо **инвертировать** (`int(255 * (1 - alpha))`).

## 5.8 Позиционирование

### Абсолютное (`type=absolute`)
```python
{"x": "<int>", "y": "<int>"}
```
Пиксельные координаты левого верхнего угла текста.

### Относительное (`type=relative`)
9 предустановленных позиций. Формулы используют переменные drawtext:
- `w`, `h` — размеры **видео**;
- `tw`, `th` — размеры **рендеренной строки текста** («text width/height»).

| `position`         | x                   | y                   |
| ------------------ | ------------------- | ------------------- |
| `top-left`         | `{margin_x}`        | `{margin_y}`        |
| `top-center`       | `(w-tw)/2`          | `{margin_y}`        |
| `top-right`        | `w-tw-{margin_x}`   | `{margin_y}`        |
| `center-left`      | `{margin_x}`        | `(h-th)/2`          |
| `center`           | `(w-tw)/2`          | `(h-th)/2`          |
| `center-right`     | `w-tw-{margin_x}`   | `(h-th)/2`          |
| `bottom-left`      | `{margin_x}`        | `h-th-{margin_y}`   |
| `bottom-center`    | `(w-tw)/2`          | `h-th-{margin_y}`   |
| `bottom-right`     | `w-tw-{margin_x}`   | `h-th-{margin_y}`   |

`{margin_x}`/`{margin_y}` — целые числа из конфига.

Эти выражения подставляются в `x=...`/`y=...` параметры drawtext.

## 5.9 Фон / рамка / тень

### Background (`box`)
```
box=1
boxcolor=<color>
boxborderw=<padding>
boxradius=<border_radius>     # если > 0
```
> `boxradius` поддержан **не во всех** сборках FFmpeg (нужен патч/новая
> версия). Если нет — параметр будет проигнорирован FFmpeg.

### Border (обводка текста)
```
borderw=<width>
bordercolor=<color>
```

### Shadow
```
shadowx=<offset_x>
shadowy=<offset_y>
shadowcolor=<color>
shadoww=<blur>      # если > 0
```

> Параметр `shadoww` (для drawtext blur) — нестандартное имя, в реальности
> drawtext blur управляется иначе (через preprocess фильтры). При
> портировании можно либо опустить `shadoww`, либо реализовать blur
> отдельным `gblur=...` фильтром перед/после drawtext.

## 5.10 Анимации

В `_build_animation_params(...)` используются drawtext выражения с
переменной `t` (текущее время в секундах) и **функцией `enable`**, которая
включает текст только в нужном временном окне.

Базовые расчеты:

```python
actual_start = start_time + delay
actual_end   = end_time if end_time is not None else (actual_start + duration)
```

| Тип        | enable                          | Доп. параметры |
| ---------- | ------------------------------- | -------------- |
| `none`     | (не добавляется)                | — |
| `fade_in`  | `between(t,as,ae)`              | `alpha='((t-as)/duration)'` |
| `fade_out` | `between(t,as,ae)`              | `alpha='(1-((t-as)/duration))'` |
| `fade`     | `between(t,as,ae)`              | `alpha='if(lt(t,mid), ((t-as)/(d/2)), (1-((t-mid)/(d/2))))'` |
| `slide_left`  | `between(t,as,ae)`           | `x='(ae-t)*w/(duration*2)'` |
| `slide_right` | `between(t,as,ae)`           | `x='w-(ae-t)*w/(duration*2)'` |
| `slide_up`    | `between(t,as,ae)`           | `y='h-(ae-t)*h/(duration*2)'` |
| `slide_down`  | `between(t,as,ae)`           | `y='(ae-t)*h/(duration*2)'` |
| `zoom_in`     | `between(t,as,ae)`           | (только enable; масштабирование текста через drawtext без override scale не поддержано) |
| `zoom_out`    | `between(t,as,ae)`           | (то же) |

> **`fade`** для `as=0, ae=4, duration=4` → `mid=2`. До 2 c — нарастает
> alpha 0→1, после 2 c — затухает 1→0. Параметр **`duration`** — это полная
> длина анимации (in+out), а **не** только in или out.
>
> **slide_left** «уезжает справа налево» (текст движется к нулевой x).
> **slide_right** — наоборот.
> Имена `slide_*` означают **направление движения**, а не «откуда появляется».

> **zoom_in/out** в текущей реализации — **заглушка**: добавляется только
> `enable`, scale текста не реализован (`drawtext` не поддерживает scale
> напрямую). При портировании реализуйте через
> `fontsize=<константа> + scale` фильтр над всем drawtext, либо собирайте
> текст в отдельный `lavfi color` источник и накладывайте `overlay+scale`.

## 5.11 Шрифты (`_get_font_path`)

```python
def _get_font_path(self, font_family: str) -> str:
    return font_family
```

Текущая реализация **возвращает имя шрифта как есть** (полагается на
fontconfig в системе). Для drawtext правильнее передавать `fontfile=`:

- На Linux + fontconfig: можно `font='Arial'` (но `drawtext` любит
  именно `fontfile=...`).
- В контейнере должен быть установлен пакет шрифтов
  (`fonts-dejavu`, `fonts-liberation` и т.п.).
- Для гарантированного воспроизведения шрифта храните `.ttf`/`.otf` рядом
  с приложением и передавайте абсолютный путь.

## 5.12 Полный пример сгенерированной команды

Запрос:
```json
{
  "video_file_id": 1,
  "text": "Привет, мир!",
  "position": {"type": "relative", "position": "bottom-center", "margin_y": 30},
  "style":    {"font_family": "Arial", "font_size": 48, "color": "#FFFFFF", "alpha": 1.0},
  "background": {"enabled": true, "color": "#000000", "alpha": 0.5, "padding": 10},
  "animation":  {"type": "fade_in", "duration": 1.0, "delay": 0.0},
  "start_time": 0,
  "end_time":   5
}
```

Сгенерированная команда (упрощенно, для читаемости):

```
ffmpeg -y -i input.mp4 \
  -vf "drawtext=text='Привет, мир!':\
fontfile='Arial':\
fontsize=48:\
fontcolor=&HFFFFFFFF&:\
x=(w-tw)/2:\
y=h-th-30:\
box=1:\
boxcolor=&H7F000000&:\
boxborderw=10:\
enable='between(t,0,5)':\
alpha='((t-0)/1.0)'" \
  -c:a copy \
  output.mp4
```

(Двоеточия в реальной команде **не** разделены переносом — для удобства
показаны по одному параметру на строку. В коде они собираются через
`":".join(params)`.)

## 5.13 Edge cases

| Ситуация | Поведение |
| -------- | --------- |
| Многострочный текст | передавайте `\n` в `text` (drawtext поддерживает) |
| Кириллица в тексте | работает, нужен Unicode‑шрифт (DejaVu, Liberation, Noto) |
| Спецсимвол `'` в тексте | экранируется автоматически (см. 5.6) |
| Двоеточие `:` | экранируется (`\:`) |
| Несколько надписей | в текущей реализации **не поддержано** — нужно либо несколько последовательных drawtext в одном `-vf`, либо несколько задач |
| `border_radius > 0` | работает только если FFmpeg собран с поддержкой `boxradius` |
| `zoom_in/zoom_out` | по сути **no‑op** в текущей реализации |
| `end_time` не задан в `fade*` | `actual_end = actual_start + duration` |
| `opacity` (общая) и `style.alpha` — что важнее? | Применяются оба: `style.alpha` входит в `fontcolor` (через формулу), `opacity` идёт в `alpha='<value>'`. Они **умножаются** drawtext. |

## 5.14 Минимальная реализация на Python (без расширенных стилей)

```python
def make_drawtext(text, *, font="DejaVuSans-Bold.ttf",
                  size=48, color="white",
                  x="(w-tw)/2", y="h-th-30",
                  start=0, end=None,
                  fade_in=0.0):
    esc = (text.replace("\\", "\\\\")     # ← BACKSLASH ПЕРВЫМ
                .replace("'", "'\\''")
                .replace(":", "\\:")
                .replace("=", "\\=")
                .replace("[", "\\[").replace("]", "\\]")
                .replace("{", "\\{").replace("}", "\\}")
                .replace("%", "\\%").replace("#", "\\#"))
    parts = [
        f"text='{esc}'",
        f"fontfile='{font}'",
        f"fontsize={size}",
        f"fontcolor={color}",
        f"x={x}", f"y={y}",
    ]
    if end is None:
        parts.append(f"enable='gte(t,{start})'")
    else:
        parts.append(f"enable='between(t,{start},{end})'")
    if fade_in > 0:
        parts.append(f"alpha='if(lt(t,{start+fade_in}),(t-{start})/{fade_in},1)'")
    return "drawtext=" + ":".join(parts)

cmd = ["ffmpeg", "-y", "-i", "in.mp4",
       "-vf", make_drawtext("Hello, world!", start=0, end=5, fade_in=1.0),
       "-c:a", "copy", "out.mp4"]
```
