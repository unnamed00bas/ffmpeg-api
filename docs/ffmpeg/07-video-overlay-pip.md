# 07. Picture‑in‑Picture — `VideoOverlay`

> **Источник:** `app/processors/video_overlay.py`, `app/schemas/video_overlay.py`,
> `app/queue/tasks.py:video_overlay_task`, `app/api/v1/tasks.py:create_video_overlay_task`.

## 7.1 Назначение

Наложить **второе видео** поверх основного (классическая «картинка в
картинке»). Поддерживаются:

- Произвольная позиция (`x`, `y`, в пикселях).
- Произвольный размер: либо фиксированный (`width`/`height`), либо
  относительный масштаб (`scale`, доля от исходных размеров overlay).
- Форма: **прямоугольник**, **круг**, **скругленный прямоугольник**.
- Прозрачность общая (`opacity`).
- Рамка (border): включаемая, ширина и цвет.
- Тень (shadow): offset/blur/цвет.

Видео всегда **перекодируется** (libx264, preset `fast`, CRF 23), аудио →
AAC 128 kb/s.

## 7.2 Эндпоинт API

```
POST /api/v1/tasks/video-overlay
{
  "base_video_file_id":    123,
  "overlay_video_file_id": 456,
  "config": {
    "x": 10, "y": 10,
    "width": null, "height": null,
    "scale": 0.25,
    "opacity": 1.0,
    "shape": "rounded",          // "rectangle" | "circle" | "rounded"
    "border_radius": 16          // только для "rounded"
  },
  "border": {"enabled": true,  "width": 2, "color": "#FFFFFF"},
  "shadow": {"enabled": true,  "offset_x": 4, "offset_y": 4, "blur": 6, "color": "#000000"},
  "output_filename": "pip.mp4"
}
```

## 7.3 Pydantic‑схема

```python
class OverlayShapeType(str, Enum):
    RECTANGLE = "rectangle"
    CIRCLE    = "circle"
    ROUNDED   = "rounded"

class OverlayConfig(BaseModel):
    x: int   = 10               # ≥ 0
    y: int   = 10
    width:  int | None = None   # > 0 (если задан) — фикс. ширина в px
    height: int | None = None
    scale:  float = 0.2         # 0 < scale ≤ 1 — доля от размеров overlay
    opacity: float = 1.0        # 0..1
    shape:   OverlayShapeType = RECTANGLE
    border_radius: int = 0      # только для ROUNDED

class BorderStyle(BaseModel):
    enabled: bool = False
    width:   int  = 2           # ≥ 0
    color:   str  = "black"     # ^#[0-9A-Fa-f]{6}$

class ShadowStyle(BaseModel):
    enabled:  bool  = False
    offset_x: int   = 2         # -50..50
    offset_y: int   = 2
    blur:     int   = 2         # 0..20
    color:    str   = "black"

class VideoOverlayRequest(BaseModel):
    base_video_file_id:    FileSource
    overlay_video_file_id: FileSource
    config: OverlayConfig = OverlayConfig()
    border: BorderStyle   = BorderStyle()
    shadow: ShadowStyle   = ShadowStyle()
    output_filename: str | None = None

    def to_dict(self) -> dict:
        return {
            "base_video_file_id":    self.base_video_file_id,
            "overlay_video_file_id": self.overlay_video_file_id,
            "config": self.config.model_dump(),
            "border": self.border.model_dump(),
            "shadow": self.shadow.model_dump(),
            "output_filename": self.output_filename,
        }
```

`border_radius > 0` валидируется: разрешено только для `shape=rounded`,
иначе ValidationError.

## 7.4 Конфигурация процессора

```python
config = {
    "base_file_path":    "/tmp/.../base.mp4",       # обязательно
    "overlay_file_path": "/tmp/.../overlay.mp4",     # обязательно
    "output_path":       "/tmp/.../pip.mp4",         # опционально
    "config":            {x, y, width, height, scale, opacity, shape, border_radius},
    "border":            {enabled, width, color},
    "shadow":            {enabled, offset_x, offset_y, blur, color},
    "timeout":            3600,
    # Информационные:
    "base_video_file_id":    int,                   # для логов/результата
    "overlay_video_file_id": int,
}
```

## 7.5 Валидация

`validate_input()`:
1. Оба пути обязательны и существуют как файлы.
2. ffprobe возвращает корректные `width`/`height` для каждого.
3. `duration > 0` для обоих.

`base_info` и `overlay_info` сохраняются в `self.config["base_info"]` /
`["overlay_info"]` и используются дальше для расчета размера и прогресса.

## 7.6 Расчет размера overlay (`_calculate_overlay_size`)

```python
if config.width and config.height:
    return config.width, config.height
return int(overlay_w * scale), int(overlay_h * scale)
```

Приоритет: явные `width`/`height` → масштаб `scale` (по умолчанию 0.2 = 20%).

> Соотношение сторон **сохраняется только если** заданы обе размерности
> пропорционально, либо использован `scale`. При width+height разной
> пропорции — overlay будет растянут.

## 7.7 Граф фильтров (`_generate_ffmpeg_command`)

Состоит из **последовательной цепочки** фильтров, применяемых к overlay,
после чего overlay накладывается на base через фильтр `overlay`.

```
[1:v] scale=W:H            [scaled]
   ↓
   ── (опционально) shape filter (circle/rounded) → [shaped]
   ↓
   ── (опционально) shadow filter                  → [shadowed]
   ↓
   ── (опционально) border filter (drawbox)        → [bordered]
   ↓
   ── (опционально) opacity (colorchannelmixer)   → [final_overlay]
   ↓
[0:v][final_overlay] overlay=x:y
```

В коде:
```python
filters = []
filters.append(f"[1:v]scale={W}:{H}[scaled]")

shape = _apply_shape_filter(W, H)        # см. 7.8
if shape:    filters.append(f"[scaled]{shape}[shaped]");      cur = "[shaped]"
else:        cur = "[scaled]"

shadow = _apply_shadow_filter(W, H)      # см. 7.9
if shadow:   filters.append(f"{cur}{shadow}[shadowed]");      cur = "[shadowed]"

border = _apply_border_filter(W, H)      # см. 7.10
if border:   filters.append(f"{cur}{border}[bordered]");      cur = "[bordered]"

if opacity < 1.0:
    filters.append(f"{cur}format=alpha,colorchannelmixer=aa={opacity}[final_overlay]")
    cur = "[final_overlay]"
else:
    cur = f"{cur}[final_overlay]"

filter_complex = ";".join(filters) + f";[0:v]{cur}overlay={x}:{y}"
```

## 7.8 Формы (`_apply_shape_filter`)

### `rectangle` — пустая строка (без фильтра).

### `circle` — `geq` filter с булевой маской по радиусу:
```
format=alpha,
geq=lum='p(X,Y)':a='st(1,a)*st(1,b)*hypot(X-cx,Y-cy)<=r ? a : 0'
```
где `cx = W/2`, `cy = H/2`, `r = min(W,H)/2`.

> Это создает **бинарную** альфа‑маску (без anti‑aliasing): пиксели внутри
> круга — непрозрачные, снаружи — прозрачные. На границе будет «лесенка».
> Для сглаживания ввести «мягкую» маску: `a='clip(255*(r - hypot(X-cx,Y-cy)),0,255)'`.

### `rounded` — `geq` со скругленными углами:
```
format=alpha,
geq=lum='p(X,Y)':
    a='st(1,a)*st(1,b)*
       hypot(min(X,W-X),min(Y,H-Y)) >= radius ?
       (hypot(min(X,W-X),min(Y,H-Y)) - radius)*a : radius*a'
```
`radius = min(border_radius, min(W,H)/2)`.

> ⚠️ Формула в текущем коде **необычная** и, по сути, инвертирована —
> внутри радиуса возвращается константа `radius*a`, снаружи — линейный
> рост `(d - r)*a`. На большинстве случаев итог визуально похож на
> «скругленный прямоугольник», но для production имеет смысл переписать
> на корректную дистанцию до углового центра. Простой вариант:
> ```
> geq=a='if(
>   lt(min(X,W-X), r)*lt(min(Y,H-Y), r),
>   if(lte(hypot(min(X,W-X)-r, min(Y,H-Y)-r), r), 255, 0),
>   255
> )'
> ```

## 7.9 Shadow (`_apply_shadow_filter`)

```
shadow=<offset_x>:<offset_y>:<blur>:<color>
```

> ⚠️ Фильтр `shadow` **не входит** в стандартный FFmpeg и в большинстве
> сборок отсутствует. В этом коде он используется как «псевдо‑фильтр».
> Если запустить такой filter_complex на ванильном FFmpeg — будет ошибка
> `No such filter: 'shadow'`.
>
> Рекомендованная замена в реальной реализации — отдельный фильтр‑граф,
> который дублирует overlay с цветовым сдвигом и blur:
> ```
> [scaled]split=2[orig][shadow_src];
> [shadow_src]format=rgba,colorchannelmixer=aa=0.5,
>             gblur=sigma=<blur>[shadow];
> [shadow]pad=...padding..., overlay=<offset_x>:<offset_y>[shadowed_combo];
> [shadowed_combo][orig]overlay=0:0[shadowed]
> ```

## 7.10 Border (`_apply_border_filter`)

Простая обводка через `drawbox`:
```
drawbox=x=0:y=0:w=<W>:h=<H>:color=<0xRRGGBB>:t=<width>
```

`color` конвертируется из `#RRGGBB` → `0xRRGGBB` (`_color_to_hex`).

## 7.11 Opacity

```
format=alpha,colorchannelmixer=aa=<opacity>
```

- `format=alpha` гарантирует наличие альфа‑канала (без него
  `colorchannelmixer aa` ничего не сделает).
- `aa=<opacity>` множит альфу на коэффициент.

## 7.12 Финальная команда (полный пример)

Запрос:
```json
{
  "base_video_file_id": 1,
  "overlay_video_file_id": 2,
  "config": {"x": 30, "y": 30, "scale": 0.25, "opacity": 0.85,
             "shape": "rounded", "border_radius": 16},
  "border": {"enabled": true, "width": 3, "color": "#FFFFFF"},
  "shadow": {"enabled": true, "offset_x": 4, "offset_y": 4, "blur": 6, "color": "#000000"}
}
```

Сгенерированная команда:

```
ffmpeg -y \
  -i base.mp4 \
  -i overlay.mp4 \
  -filter_complex "\
[1:v]scale=480:270[scaled];\
[scaled]format=alpha,geq=lum='p(X,Y)':a='st(1,a)*st(1,b)*\
hypot(min(X,W-X),min(Y,H-Y))>=16?(hypot(min(X,W-X),min(Y,H-Y))-16)*a:16*a'[shaped];\
[shaped]shadow=4:4:6:0x000000[shadowed];\
[shadowed]drawbox=x=0:y=0:w=480:h=270:color=0xFFFFFF:t=3[bordered];\
[bordered]format=alpha,colorchannelmixer=aa=0.85[final_overlay];\
[0:v][final_overlay]overlay=30:30" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -shortest \
  pip.mp4
```

> Размеры `480:270` берутся из исходного overlay 1920×1080 × 0.25.

## 7.13 Прогресс

`progress_callback` пересчитывается из stderr time против длительности
**базового** видео:

```python
total_duration = base_info["duration"]
update_progress(min(100, 100 * t / total_duration))
```

После завершения — `update_progress(100.0)`.

## 7.14 Что возвращает

```python
return {
    "output_path":       "/tmp/.../pip.mp4",
    "base_file_id":      <int>,
    "overlay_file_id":   <int>,
}
```

Дальше Celery‑задача (`video_overlay_task`) загружает файл в MinIO и
пишет результат в БД.

## 7.15 Edge cases

| Ситуация | Поведение / комментарий |
| -------- | ----------------------- |
| `shape=circle/rounded` + `shadow` | Тень рисуется ПО КВАДРАТУ исходного scaled, а не по форме. Чтобы сделать «правильно», надо рисовать тень **после** shape. В текущем коде так и сделано (shadow после shape), но фильтр `shadow` не существует в ванильном FFmpeg — см. 7.9. |
| `width`/`height` нарушают пропорции overlay | overlay будет растянут |
| `opacity < 1` | Применяется поверх всего — фактически финальный alpha multiply. |
| Overlay длиннее base | `-shortest` обрежет по base. Если хотите, чтобы overlay прокрутился до конца своей длины — уберите `-shortest`. |
| Overlay короче base | После окончания overlay в кадре остается base без overlay (FFmpeg использует последний доступный кадр overlay по умолчанию — но `-shortest` приведёт к обрезке. Если убрать `-shortest`, нужно ещё `eof_action=pass` в overlay фильтре). |
| Кодек overlay экзотический | FFmpeg сам декодирует, но если рендер очень медленный — стоит предварительно перекодировать overlay в H.264. |
| `border_radius > min(W,H)/2` | Обрезается до `min(W,H)/2` в `_apply_shape_filter`. |
| `opacity = 0` | Видео overlay полностью прозрачно — практически бесполезно, но не падает. |

## 7.16 Минимальная реализация на Python (без shape/shadow)

```python
async def pip(base, overlay, out, *, x=10, y=10, scale=0.25,
              opacity=1.0, ffmpeg="ffmpeg"):
    info = await FFmpegCommand.get_video_info(overlay)
    W, H = int(info["width"]*scale), int(info["height"]*scale)
    if opacity < 1.0:
        fc = (
            f"[1:v]scale={W}:{H}[s];"
            f"[s]format=yuva420p,colorchannelmixer=aa={opacity}[ov];"
            f"[0:v][ov]overlay={x}:{y}"
        )
    else:
        fc = f"[1:v]scale={W}:{H}[ov];[0:v][ov]overlay={x}:{y}"
    cmd = [
        ffmpeg, "-y",
        "-i", base, "-i", overlay,
        "-filter_complex", fc,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        out,
    ]
    await FFmpegCommand.run_command(cmd)
```

## 7.17 Чек‑лист при портировании

- [ ] Заменить псевдо‑фильтр `shadow` на корректный (split + gblur + overlay) или отказаться.
- [ ] Перепроверить формулу `rounded` — возможно, переписать на «корректное» расстояние до центра скругленного угла.
- [ ] Подумать про `eof_action` в `overlay` (если хотите overlay длиннее base).
- [ ] Учесть, что libx264 perf зависит от `-preset` — для real‑time можно `ultrafast`.
- [ ] Добавить (если нужно) HW‑accel: `-c:v h264_nvenc -preset p4` и т.п.
