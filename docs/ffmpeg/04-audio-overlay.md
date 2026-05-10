# 04. Аудио‑оверлей — `AudioOverlay`

> **Источник:** `app/processors/audio_overlay.py`, `app/schemas/audio_overlay.py`,
> `app/queue/tasks.py:audio_overlay_task`, `app/api/v1/tasks.py:create_audio_overlay_task`.

## 4.1 Назначение

Наложить **внешнюю аудиодорожку** на видео в одном из двух режимов:
- `replace` — полностью **заменить** оригинальное аудио.
- `mix` — **смешать** с оригинальным аудио (с раздельными уровнями громкости).

Видео при этом **не перекодируется** (`-c:v copy`), что быстро. Аудио всегда
кодируется в **AAC**.

## 4.2 Эндпоинт API

```
POST /api/v1/tasks/audio-overlay
{
  "video_file_id": 123,
  "audio_file_id": "https://example.com/track.mp3",
  "mode": "mix",                  // "replace" | "mix"  (default: replace)
  "offset": 0.0,                   // секунды, ≥ 0
  "duration": null,                // секунды или null (до конца аудио)
  "original_volume": 1.0,          // 0.0–2.0
  "overlay_volume":  1.0,          // 0.0–2.0
  "output_filename": "out.mp4"
}
```

## 4.3 Pydantic‑схема

```python
class AudioOverlayMode(str, Enum):
    REPLACE = "replace"
    MIX     = "mix"

class AudioOverlayRequest(BaseModel):
    video_file_id: FileSource          # int | HttpUrl
    audio_file_id: FileSource
    mode: AudioOverlayMode = AudioOverlayMode.REPLACE
    offset: float = 0.0                # ≥ 0
    duration: Optional[float] = None   # ≥ 0
    original_volume: float = 1.0       # 0..2
    overlay_volume:  float = 1.0       # 0..2
    output_filename: Optional[str] = None
```

## 4.4 Конфигурация процессора

`AudioOverlay(task_id, config, progress_callback=None)`:

```python
config = {
    "video_path":      "/tmp/.../video.mp4",   # обязательно
    "audio_path":      "/tmp/.../audio.mp3",   # обязательно
    "output_path":     "/tmp/.../out.mp4",     # опционально
    "mode":            "replace" | "mix",      # default: replace
    "offset":          0.0,                    # секунды
    "duration":        None | <float>,         # секунды
    "original_volume": 1.0,                    # для mix
    "overlay_volume":  1.0,                    # для mix
    "timeout":         3600,
}
```

## 4.5 Валидация — `validate_input()`

Бросает `FFmpegValidationError`, если:
1. Нет `video_path` или `audio_path`.
2. `ffprobe` не смог прочитать видео (повреждено / не видеофайл).
3. `ffprobe` не смог прочитать аудио.
4. `duration > audio_duration` (нельзя обрезать длиннее самого аудио).
5. `offset >= audio_duration` (когда `duration` не указан, оффсет за пределами).

## 4.6 Команда FFmpeg для `mode=replace`

```
ffmpeg -y \
  -i <video> \
  -i <audio> \
  -map 0:v:0 \
  -map 1:a:0 \
  -c:v copy \
  -c:a aac \
  -shortest \
  <output>
```

Расшифровка:

| Ключ            | Зачем |
| --------------- | ----- |
| `-i <video>`    | input #0 — оригинальное видео |
| `-i <audio>`    | input #1 — новый аудиотрек |
| `-map 0:v:0`    | взять видеопоток 0 из input #0 |
| `-map 1:a:0`    | взять аудиопоток 0 из input #1 (оригинальное аудио игнорируется) |
| `-c:v copy`     | видео не перекодировать |
| `-c:a aac`      | аудио → AAC (чтобы поместилось в MP4) |
| `-shortest`     | завершить по самому короткому потоку (видео или аудио) |

> `-shortest` важен: иначе длительность файла станет максимальной из
> двух потоков, и в видео либо появится «черный кадр» в конце,
> либо аудио оборвется без причины.

## 4.7 Команда FFmpeg для `mode=mix`

Здесь активно используется **filter_complex** (граф фильтров).

```
ffmpeg -y \
  -i <video> \
  -ss <offset> -i <audio> \
  -filter_complex \
    "[1:a]volume=<overlay_volume>[a1]; \
     [0:a]volume=<original_volume>[a0]; \
     [a0][a1]amix=inputs=2:duration=first:dropout_transition=2" \
  -c:v copy \
  -c:a aac \
  [-t <duration>] \
  <output>
```

Что происходит в графе:

1. `[0:a]` — аудиопоток оригинального видео.
2. `[1:a]` — внешнее аудио (с применённым `-ss <offset>` смещением, потому что
   `-ss` стоит **до** `-i <audio>`, то есть это **input‑seek**, FFmpeg сразу
   пропускает первые `offset` секунд исходного потока).
3. К каждому потоку применяется `volume=<gain>` (от 0.0 «mute» до 2.0
   «удвоить уровень»).
4. `amix=inputs=2:duration=first:dropout_transition=2` — реальный микс:
   - `inputs=2` — два потока,
   - `duration=first` — итог обрезается по длительности **первого**
     входа фильтра (`a0`, т.е. оригинальное аудио, т.е. длительности видео),
   - `dropout_transition=2` — плавный фейд за 2 секунды, когда один из потоков
     закончится раньше другого.
5. `-t <duration>` (если передан) дополнительно ограничивает длительность.

> В коде ветка `if duration is not None` создаёт **тот же** filter_complex, что
> и без неё — отличие только в добавлении `-t <duration>` к финальной команде.

## 4.8 Прогресс

```python
video_info = await FFmpegCommand.get_video_info(video_path)
total_duration = video_info["duration"]

def progress_cb(p):
    if total_duration > 0 and p is not None:
        update_progress(min(100, 100 * p / total_duration))
```

То есть прогресс считается относительно длительности **видео** (а не аудио).

## 4.9 Полный пример (replace)

```bash
ffmpeg -y \
  -i input.mp4 \
  -i voiceover.mp3 \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac \
  -shortest \
  output.mp4
```

## 4.10 Полный пример (mix)

```bash
ffmpeg -y \
  -i input.mp4 \
  -ss 5 -i music.mp3 \
  -filter_complex \
    "[1:a]volume=0.4[a1]; \
     [0:a]volume=1.0[a0]; \
     [a0][a1]amix=inputs=2:duration=first:dropout_transition=2" \
  -c:v copy -c:a aac \
  -t 30 \
  output.mp4
```

Здесь:
- Музыку начинаем с 5 секунды (`-ss 5` перед `-i music.mp3`).
- Музыку приглушаем до 40% (`volume=0.4`).
- Голос в видео оставляем как есть (`volume=1.0`).
- Результат обрезаем по 30 секундам (`-t 30`).

## 4.11 Edge cases

| Ситуация | Поведение |
| -------- | --------- |
| Видео без аудиодорожки (`mode=mix`) | `[0:a]` не существует → FFmpeg упадет. На уровне валидации это **не проверяется**. Безопаснее — детект через ffprobe, если нет audio stream → принудительно `mode=replace`. |
| Аудио длиннее видео, `mode=replace` | `-shortest` обрежет по видео — аудио не будет полностью. |
| Видео длиннее аудио, `mode=replace` | `-shortest` обрежет по аудио — будет потерян «хвост» видео. Если этого не хотят — нужно убрать `-shortest` и накладывать тишину. |
| `offset >= audio_duration` | Поднимется `FFmpegValidationError` ещё в `validate_input()`. |
| `original_volume=0` в `mix` | По сути эквивалент `replace` (но FFmpeg всё равно прогоняет через amix). |
| `overlay_volume > 1` | Возможно клиппирование, в коде нет ни лимитера, ни нормализации. |

## 4.12 Минимальная реализация на чистом Python

```python
async def replace_audio(video, audio, out, ffmpeg="ffmpeg"):
    cmd = [
        ffmpeg, "-y",
        "-i", video, "-i", audio,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        out,
    ]
    await FFmpegCommand.run_command(cmd)

async def mix_audio(video, audio, out, *,
                    offset=0.0, duration=None,
                    orig_vol=1.0, ovr_vol=1.0, ffmpeg="ffmpeg"):
    fc = (
        f"[1:a]volume={ovr_vol}[a1];"
        f"[0:a]volume={orig_vol}[a0];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2"
    )
    cmd = [
        ffmpeg, "-y",
        "-i", video,
        "-ss", str(offset), "-i", audio,
        "-filter_complex", fc,
        "-c:v", "copy", "-c:a", "aac",
    ]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd.append(out)
    await FFmpegCommand.run_command(cmd)
```

## 4.13 Расширения (что делает оригинал, чего не делает)

- ❌ Нет нормализации громкости (`loudnorm`/`dynaudnorm`).
- ❌ Нет fade in/out на самой дорожке (только `dropout_transition` в `amix`).
- ❌ Не поддержано несколько overlay‑дорожек одновременно.
- ❌ Нет sidechain ducking (приглушение оригинала, когда говорит overlay).

Если эти возможности нужны, добавляются в граф фильтров: `loudnorm`,
`afade=t=in:st=0:d=2`, `sidechaincompress`. Места — внутри
`_generate_ffmpeg_command_mix(...)`.
