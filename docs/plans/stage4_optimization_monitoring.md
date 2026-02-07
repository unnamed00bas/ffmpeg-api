# Этап 4: Оптимизация и мониторинг (Недели 9-10)

## Обзор этапа

Этап фокусируется на оптимизации производительности, улучшении надежности и расширении функциональности системы. Оптимизируется FFmpeg, реализуется кэширование для ускорения повторных операций, добавляется поддержка больших файлов через streaming, настраивается автоочистка, расширяется мониторинг и создаются user/admin endpoints.

---

## Подзадача 4.1: Оптимизация FFmpeg

### Задачи реализации

**Оптимизация FFmpeg команд в [app/ffmpeg/commands.py](app/ffmpeg/commands.py):**

```python
from enum import Enum

class FFmpegPreset(str, Enum):
    """FFmpeg encoding presets"""
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"

class FFmpegTune(str, Enum):
    """FFmpeg tuning parameters"""
    FILM = "film"
    ANIMATION = "animation"
    GRAIN = "grain"
    STILLIMAGE = "stillimage"
    FASTDECODE = "fastdecode"
    ZEROLATENCY = "zerolatency"

class FFmpegOptimizer:
    def __init__(
        self,
        preset: FFmpegPreset = FFmpegPreset.FAST,
        tune: Optional[FFmpegTune] = None,
        crf: Optional[int] = None,
        threads: Optional[int] = None
    ):
        self.preset = preset
        self.tune = tune
        self.crf = crf
        self.threads = threads
    
    def get_encoding_params(self) -> List[str]:
        """Получение параметров кодирования"""
        params = []
        
        # Preset
        params.extend(["-preset", self.preset.value])
        
        # Tune
        if self.tune:
            params.extend(["-tune", self.tune.value])
        
        # CRF (Constant Rate Factor)
        if self.crf is not None:
            params.extend(["-crf", str(self.crf)])
        
        # Threads
        if self.threads:
            params.extend(["-threads", str(self.threads)])
        
        return params
    
    def optimize_for_scenario(self, scenario: str) -> Dict[str, Any]:
        """Оптимизация для разных сценариев"""
        scenarios = {
            "fast": {
                "preset": FFmpegPreset.VERYFAST,
                "tune": FFmpegTune.FASTDECODE,
                "threads": 4
            },
            "balanced": {
                "preset": FFmpegPreset.FAST,
                "tune": FFmpegTune.FILM,
                "threads": 4
            },
            "quality": {
                "preset": FFmpegPreset.MEDIUM,
                "tune": FFmpegTune.FILM,
                "crf": 18,
                "threads": 4
            }
        }
        return scenarios.get(scenario, scenarios["balanced"])
```

**Hardware acceleration поддержка:**

```python
class HardwareAccelerator:
    @staticmethod
    def detect_available() -> List[str]:
        """Обнаружение доступного hardware acceleration"""
        available = []
        
        # NVENC (NVIDIA)
        try:
            # Проверка через nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                available.append("nvenc")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # QSV (Intel Quick Sync)
        try:
            # Проверка через VAAPI
            result = subprocess.run(
                ["vainfo"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                available.append("qsv")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # VAAPI (Linux)
        try:
            result = subprocess.run(
                ["vainfo"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                available.append("vaapi")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return available
    
    @staticmethod
    def get_hwaccel_params(accelerator: str) -> List[str]:
        """Получение параметров для hardware acceleration"""
        if accelerator == "nvenc":
            return [
                "-hwaccel", "cuda",
                "-c:v", "h264_nvenc"
            ]
        elif accelerator == "qsv":
            return [
                "-hwaccel", "qsv",
                "-c:v", "h264_qsv"
            ]
        elif accelerator == "vaapi":
            return [
                "-hwaccel", "vaapi",
                "-vaapi_device", "/dev/dri/renderD128",
                "-c:v", "h264_vaapi"
            ]
        return []
```

**Интеграция оптимизаций в процессоры:**

```python
# Добавить в каждый процессор (VideoJoiner, AudioOverlay, и т.д.)

def _generate_ffmpeg_command_with_optimization(
    self,
    input_file: str,
    output_file: str
) -> List[str]:
    """Генерация FFmpeg команды с оптимизациями"""
    
    # Получить настройки оптимизации из config или использовать дефолтные
    optimizer_config = self.config.get("optimization", {})
    preset = optimizer_config.get("preset", "fast")
    
    # Создать оптимизатор
    optimizer = FFmpegOptimizer()
    if preset == "fast":
        opt = optimizer.optimize_for_scenario("fast")
    elif preset == "quality":
        opt = optimizer.optimize_for_scenario("quality")
    else:
        opt = optimizer.optimize_for_scenario("balanced")
    
    # Получить параметры
    params = optimizer.get_encoding_params()
    
    # Проверить hardware acceleration
    if optimizer_config.get("hardware_acceleration"):
        available = HardwareAccelerator.detect_available()
        if available:
            hw_params = HardwareAccelerator.get_hwaccel_params(available[0])
            params.extend(hw_params)
    
    # Добавить параметры к команде
    command = [
        "ffmpeg",
        "-i", input_file,
    ]
    command.extend(params)
    command.append(output_file)
    
    return command
```

### Тестирование подзадачи 4.1

**Unit тесты FFmpegOptimizer:**
- get_encoding_params() возвращает корректные preset параметры
- get_encoding_params() возвращает корректные tune параметры
- get_encoding_params() возвращает корректные CRF параметры
- get_encoding_params() возвращает корректные threads параметры
- optimize_for_scenario("fast") возвращает VeryFast preset
- optimize_for_scenario("balanced") возвращает Fast preset
- optimize_for_scenario("quality") возвращает Medium preset + CRF 18

**Unit тесты HardwareAccelerator:**
- detect_available() обнаруживает NVENC если доступен
- detect_available() обнаруживает QSV если доступен
- detect_available() обнаруживает VAAPI если доступен
- detect_available() возвращает пустой список если ничего нет
- get_hwaccel_params("nvenc") возвращает корректные параметры
- get_hwaccel_params("qsv") возвращает корректные параметры
- get_hwaccel_params("vaapi") возвращает корректные параметры

**Performance тесты:**
- Сравнение скорости обработки с разными preset'ами:
  - UltraFast: максимальная скорость
  - VeryFast: быстрое кодирование
  - Fast: баланс скорости и качества
  - Medium: лучшее качество, медленнее
  - Slow: максимальное качество
- Сравнение качества с разными CRF значениями:
  - CRF 18: высокое качество
  - CRF 23: среднее качество (default)
  - CRF 28: низкое качество
- Измерение времени обработки:
  - CPU кодирование vs NVENC
  - CPU кодирование vs QSV
- Сравнение размера выходных файлов:
  - Разные CRF значения
  - Разные preset'ы

**Интеграционные тесты:**
- Hardware acceleration работает с VideoJoiner
- Hardware acceleration работает с TextOverlay
- Hardware acceleration работает с VideoOverlay
- Optimizer работает со всеми процессорами

**Regression тесты:**
- Гарантия качества при оптимизации
- Видео не повреждается при использовании разных preset'ов
- Аудио не теряется при оптимизации

---

## Подзадача 4.2: Кэширование

### Задачи реализации

**Cache service в [app/cache/cache_service.py](app/cache/cache_service.py):**

```python
from typing import Optional, Any, Dict
import json
import hashlib

class CacheService:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
        self.default_ttl = 3600  # 1 hour
    
    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            # Логирование ошибки
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Установка значения в кэш"""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            # Логирование ошибки
            return False
    
    async def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            return False
    
    async def clear(self) -> bool:
        """Очистка всего кэша"""
        try:
            self.redis.flushdb()
            return True
        except Exception as e:
            return False
    
    async def exists(self, key: str) -> bool:
        """Проверка существования ключа"""
        try:
            return self.redis.exists(key) > 0
        except Exception as e:
            return False
    
    @staticmethod
    def generate_key(prefix: str, **kwargs) -> str:
        """Генерация ключа кэша"""
        # Сортировка параметров для детерминированного ключа
        params = sorted(kwargs.items())
        params_str = "&".join(f"{k}={v}" for k, v in params)
        hash_str = hashlib.md5(params_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"

class VideoMetadataCache:
    """Кэш метаданных видео"""
    
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self.ttl = 86400  # 24 hours
    
    async def get_video_info(
        self,
        file_id: int,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Получение информации о видео из кэша"""
        key = self._generate_key(file_id, file_path)
        return await self.cache.get(key)
    
    async def set_video_info(
        self,
        file_id: int,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Сохранение информации о видео в кэш"""
        key = self._generate_key(file_id, file_path)
        return await self.cache.set(key, metadata, self.ttl)
    
    async def invalidate(self, file_id: int, file_path: str) -> bool:
        """Инвалидация кэша для видео"""
        key = self._generate_key(file_id, file_path)
        return await self.cache.delete(key)
    
    def _generate_key(self, file_id: int, file_path: str) -> str:
        """Генерация ключа для видео"""
        return f"video:info:{file_id}:{hashlib.md5(file_path.encode()).hexdigest()}"

class OperationResultCache:
    """Кэш результатов операций"""
    
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self.ttl = 604800  # 7 days
    
    async def get_result(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Получение результата операции из кэша"""
        key = self._generate_key(operation_type, input_file_ids, config)
        return await self.cache.get(key)
    
    async def set_result(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any],
        result: Dict[str, Any]
    ) -> bool:
        """Сохранение результата операции в кэш"""
        key = self._generate_key(operation_type, input_file_ids, config)
        return await self.cache.set(key, result, self.ttl)
    
    def _generate_key(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any]
    ) -> str:
        """Генерация ключа для операции"""
        return CacheService.generate_key(
            "operation:result",
            type=operation_type,
            files=",".join(str(f) for f in sorted(input_file_ids)),
            config=json.dumps(config, sort_keys=True)
        )
```

**Интеграция кэша в процессоры:**

```python
# Добавить в каждый процессор

class VideoJoiner(BaseProcessor):
    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
        cache_service: Optional[CacheService] = None
    ):
        super().__init__(task_id, config, progress_callback)
        self.cache_service = cache_service
        self.metadata_cache = VideoMetadataCache(cache_service) if cache_service else None
        self.result_cache = OperationResultCache(cache_service) if cache_service else None
    
    async def process(self) -> Dict[str, Any]:
        """Обработка с кэшированием"""
        
        # Проверка кэша результата
        if self.result_cache:
            cached_result = await self.result_cache.get_result(
                "join",
                self.config.get("file_ids", []),
                self.config
            )
            if cached_result:
                self.update_progress(100)
                return cached_result
        
        # Получение метаданных видео с кэшем
        file_metadata = []
        for file_id in self.config.get("file_ids", []):
            # Проверка кэша метаданных
            if self.metadata_cache:
                metadata = await self.metadata_cache.get_video_info(
                    file_id,
                    file_path
                )
                if metadata:
                    file_metadata.append(metadata)
                    continue
            
            # Получение метаданных через FFmpeg
            metadata = await get_video_info(file_path)
            file_metadata.append(metadata)
            
            # Сохранение в кэш
            if self.metadata_cache:
                await self.metadata_cache.set_video_info(
                    file_id,
                    file_path,
                    metadata
                )
        
        # Выполнение операции
        result = await self._process_join(file_metadata)
        
        # Сохранение результата в кэш
        if self.result_cache:
            await self.result_cache.set_result(
                "join",
                self.config.get("file_ids", []),
                self.config,
                result
            )
        
        return result
```

### Тестирование подзадачи 4.2

**Unit тесты CacheService:**
- get() возвращает значение из кэша
- get() возвращает None для несуществующего ключа
- set() сохраняет значение в кэш
- set() использует указанный TTL
- set() использует default TTL если не указан
- delete() удаляет значение из кэша
- delete() возвращает False для несуществующего ключа
- clear() удаляет все значения
- exists() возвращает True для существующего ключа
- exists() возвращает False для несуществующего ключа
- generate_key() генерирует детерминированные ключи
- generate_key() обрабатывает разные комбинации параметров

**Unit тесты VideoMetadataCache:**
- get_video_info() возвращает метаданные из кэша
- get_video_info() возвращает None для несуществующего видео
- set_video_info() сохраняет метаданные в кэш
- set_video_info() использует корректный TTL
- invalidate() удаляет метаданные из кэша
- _generate_key() генерирует корректные ключи

**Unit тесты OperationResultCache:**
- get_result() возвращает результат из кэша
- get_result() возвращает None для несуществующей операции
- set_result() сохраняет результат в кэш
- set_result() использует корректный TTL
- _generate_key() генерирует корректные ключи

**Интеграционные тесты Redis:**
- Запись/чтение из кэша работает
- TTL истекает через заданное время
- Кэш переживает рестарты Redis (при AOF)
- Кэш корректно работает с большими данными

**Performance тесты:**
- Сравнение времени с кэшем vs без кэша:
  - С кэшем: < 10ms
  - Без кэша: > 500ms (FFmpeg info)
- Hit rate измерение:
  - Повторные операции используют кэш
  - Hit rate > 50% для типичного использования
- Memory usage:
  - Кэш не занимает слишком много памяти
  - Старые записи удаляются по TTL

**Regression тесты:**
- Кэш корректно инвалидируется при изменении файла
- Кэш не возвращает устаревшие данные
- Кэш не влияет на корректность операций

---

## Подзадача 4.3: Streaming для больших файлов

### Задачи реализации

**Chunked upload в [app/api/v1/files.py](app/api/v1/files.py):**

```python
from fastapi import UploadFile, File, Form
from typing import Optional

# Хранение информации о chunk upload в Redis
class ChunkUploadManager:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
        self.chunk_timeout = 3600  # 1 hour
    
    async def initiate_upload(
        self,
        user_id: int,
        filename: str,
        total_size: int,
        total_chunks: int,
        content_type: str
    ) -> str:
        """Инициализация chunk upload"""
        upload_id = str(uuid.uuid4())
        upload_info = {
            "user_id": user_id,
            "filename": filename,
            "total_size": total_size,
            "total_chunks": total_chunks,
            "content_type": content_type,
            "uploaded_chunks": [],
            "created_at": datetime.utcnow().isoformat()
        }
        self.redis.setex(
            f"chunk_upload:{upload_id}",
            self.chunk_timeout,
            json.dumps(upload_info)
        )
        return upload_id
    
    async def upload_chunk(
        self,
        upload_id: str,
        chunk_number: int,
        chunk_data: bytes
    ) -> bool:
        """Загрузка чанка"""
        # Сохранение чанка в MinIO с временным именем
        chunk_path = f"temp/chunks/{upload_id}_{chunk_number}"
        await minio_client.upload_file_from_bytes(chunk_path, chunk_data)
        
        # Обновление информации о загрузке
        upload_info = await self._get_upload_info(upload_id)
        if upload_info:
            upload_info["uploaded_chunks"].append(chunk_number)
            self.redis.setex(
                f"chunk_upload:{upload_id}",
                self.chunk_timeout,
                json.dumps(upload_info)
            )
            return True
        return False
    
    async def complete_upload(
        self,
        upload_id: str,
        output_filename: Optional[str] = None
    ) -> Optional[File]:
        """Завершение загрузки и объединение чанков"""
        upload_info = await self._get_upload_info(upload_id)
        if not upload_info:
            return None
        
        # Проверка что все чанки загружены
        if len(upload_info["uploaded_chunks"]) != upload_info["total_chunks"]:
            raise ValueError("Not all chunks uploaded")
        
        # Объединение чанков
        temp_file = create_temp_file()
        with open(temp_file, "wb") as outfile:
            for i in range(upload_info["total_chunks"]):
                chunk_path = f"temp/chunks/{upload_id}_{i}"
                chunk_data = await minio_client.get_file_bytes(chunk_path)
                outfile.write(chunk_data)
                # Удаление чанка
                await minio_client.delete_file(chunk_path)
        
        # Загрузка полного файла в MinIO
        storage_path = f"{upload_info['user_id']}/{uuid.uuid4()}/{upload_info['filename']}"
        await minio_client.upload_file(temp_file, storage_path, upload_info["content_type"])
        
        # Создание записи в БД
        file_repo = FileRepository(db_session)
        file_record = await file_repo.create(
            user_id=upload_info["user_id"],
            filename=storage_path,
            original_filename=upload_info["filename"],
            size=upload_info["total_size"],
            content_type=upload_info["content_type"],
            metadata={}
        )
        
        # Очистка временного файла
        os.remove(temp_file)
        
        # Удаление информации о загрузке
        self.redis.delete(f"chunk_upload:{upload_id}")
        
        return file_record
    
    async def abort_upload(self, upload_id: str) -> bool:
        """Отмена загрузки"""
        upload_info = await self._get_upload_info(upload_id)
        if not upload_info:
            return False
        
        # Удаление всех загруженных чанков
        for chunk_num in upload_info["uploaded_chunks"]:
            chunk_path = f"temp/chunks/{upload_id}_{chunk_num}"
            await minio_client.delete_file(chunk_path)
        
        # Удаление информации о загрузке
        self.redis.delete(f"chunk_upload:{upload_id}")
        
        return True
    
    async def _get_upload_info(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о загрузке"""
        data = self.redis.get(f"chunk_upload:{upload_id}")
        if data:
            return json.loads(data)
        return None

# Endpoints
@router.post("/upload-init")
async def initiate_chunk_upload(
    filename: str = Form(...),
    total_size: int = Form(...),
    total_chunks: int = Form(...),
    content_type: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Инициализация chunk upload"""
    manager = ChunkUploadManager()
    upload_id = await manager.initiate_upload(
        current_user.id,
        filename,
        total_size,
        total_chunks,
        content_type
    )
    return {"upload_id": upload_id}

@router.post("/upload-chunk/{upload_id}/{chunk_number}")
async def upload_chunk(
    upload_id: str,
    chunk_number: int,
    chunk_data: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузка чанка"""
    manager = ChunkUploadManager()
    chunk_bytes = await chunk_data.read()
    success = await manager.upload_chunk(upload_id, chunk_number, chunk_bytes)
    
    if not success:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    return {"status": "uploaded", "chunk_number": chunk_number}

@router.post("/upload-complete/{upload_id}")
async def complete_upload(
    upload_id: str,
    output_filename: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Завершение загрузки"""
    manager = ChunkUploadManager()
    file_record = await manager.complete_upload(upload_id, output_filename)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    return FileUploadResponse.from_orm(file_record)

@router.post("/upload-abort/{upload_id}")
async def abort_upload(
    upload_id: str,
    current_user: User = Depends(get_current_user)
):
    """Отмена загрузки"""
    manager = ChunkUploadManager()
    success = await manager.abort_upload(upload_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    return {"status": "aborted"}
```

**Chunked download:**

```python
from fastapi.responses import StreamingResponse
import io

@router.get("/{file_id}/download-range")
async def download_file_range(
    file_id: int,
    range_header: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user)
):
    """Скачивание файла с поддержкой range"""
    # Получение информации о файле
    file_repo = FileRepository(db_session)
    file_record = await file_repo.get_by_id(file_id)
    
    if not file_record or file_record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Получение размера файла
    file_size = file_record.size
    
    # Парсинг Range header
    start = 0
    end = file_size - 1
    
    if range_header:
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
    
    # Вычисление content length
    content_length = end - start + 1
    
    # Чтение файла из MinIO
    def generate():
        with minio_client.get_file_stream(file_record.filename) as stream:
            stream.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(8192, remaining)
                data = stream.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data
    
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": file_record.content_type,
    }
    
    return StreamingResponse(
        generate(),
        status_code=206 if range_header else 200,
        headers=headers
    )
```

### Тестирование подзадачи 4.3

**Unit тесты chunk management:**
- initiate_upload() создает запись в Redis
- initiate_upload() возвращает уникальный upload_id
- upload_chunk() сохраняет чанк в MinIO
- upload_chunk() обновляет информацию о загрузке
- complete_upload() объединяет чанки
- complete_upload() проверяет что все чанки загружены
- complete_upload() создает запись в БД
- complete_upload() удаляет временные чанки
- complete_upload() удаляет информацию о загрузке
- abort_upload() удаляет загруженные чанки
- abort_upload() удаляет информацию о загрузке

**Интеграционные тесты:**

*Chunked upload:*
- Загрузка файла по частям работает
- Чанки загружаются корректно
- Чанки объединяются корректно
- Резюмирование загрузки после прерывания работает
- Отмена загрузки работает

*Chunked download:*
- Download по range работает
- Content-Length корректен
- Content-Range корректен
- Скачивание в несколько потоков работает

*Progress tracking:*
- Прогресс загрузки отслеживается
- Прогресс скачивания отслеживается

**Performance тесты:**
- Загрузка больших файлов (1GB+):
  - Chunked upload не потребляет много RAM
  - Время загрузки < 10 минут для 1GB
  - Возобновление прерванной загрузки работает
- Скачивание больших файлов:
  - Chunked download не потребляет много RAM
  - Стриминг работает плавно
  - Пауза и возобновление загрузки работает

**Regression тесты:**
- Файлы собираются корректно из чанков
- Нет потерь данных при chunked upload
- Нет повреждений при chunked download

---

## Подзадача 4.4: Автоочистка файлов

### Задачи реализации

**Celery periodic tasks в [app/queue/periodic_tasks.py](app/queue/periodic_tasks.py):**

```python
from datetime import datetime, timedelta
import os

@celery_app.task
def cleanup_old_files():
    """Периодическая очистка старых файлов"""
    from app.database.connection import get_db
    from app.database.repositories.file_repository import FileRepository
    from app.storage.minio_client import minio_client
    from app.config import settings
    
    db = get_db()
    file_repo = FileRepository(db)
    
    # Удаление файлов старее RETENTION_DAYS
    retention_days = getattr(settings, "STORAGE_RETENTION_DAYS", 7)
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    # Получение старых файлов
    old_files = file_repo.get_files_older_than(cutoff_date)
    
    deleted_count = 0
    for file_record in old_files:
        try:
            # Удаление из MinIO
            if not file_record.is_deleted:
                await minio_client.delete_file(file_record.filename)
            
            # Помечаем как удаленный в БД
            file_repo.mark_as_deleted(file_record.id)
            deleted_count += 1
            
        except Exception as e:
            # Логирование ошибки
            continue
    
    return f"Deleted {deleted_count} old files"

@celery_app.task
def cleanup_temp_files():
    """Периодическая очистка временных файлов"""
    from app.storage.minio_client import minio_client
    
    # Удаление orphan temp файлов
    temp_files = minio_client.list_files("temp/")
    
    deleted_count = 0
    for temp_file in temp_files:
        try:
            # Проверка возраста файла (старше 24 часов)
            file_info = minio_client.get_file_info(temp_file)
            file_age = datetime.utcnow() - datetime.fromisoformat(
                file_info.get("last_modified", "")
            )
            
            if file_age > timedelta(hours=24):
                await minio_client.delete_file(temp_file)
                deleted_count += 1
            
        except Exception as e:
            # Логирование ошибки
            continue
    
    return f"Deleted {deleted_count} temp files"

@celery_app.task
def cleanup_old_tasks():
    """Периодическая очистка старых задач"""
    from app.database.connection import get_db
    from app.database.repositories.task_repository import TaskRepository
    
    db = get_db()
    task_repo = TaskRepository(db)
    
    # Удаление задач старее 30 дней
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    deleted_count = task_repo.delete_tasks_older_than(cutoff_date)
    
    return f"Deleted {deleted_count} old tasks"
```

**Настройка Beat schedule в [app/queue/beat_schedule.py](app/queue/beat_schedule.py):**

```python
from celery.schedules import crontab

beat_schedule = {
    # Существующие задачи...
    
    # Новые задачи очистки
    "cleanup-old-files-every-6-hours": {
        "task": "app.queue.periodic_tasks.cleanup_old_files",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "cleanup-temp-files-every-hour": {
        "task": "app.queue.periodic_tasks.cleanup_temp_files",
        "schedule": crontab(minute=0),
    },
    "cleanup-old-tasks-daily": {
        "task": "app.queue.periodic_tasks.cleanup_old_tasks",
        "schedule": crontab(minute=0, hour=2),
    },
}
```

**Admin endpoint для ручной очистки:**

```python
# В app/api/v1/admin.py

@router.post("/cleanup")
async def manual_cleanup(
    file_retention_days: Optional[int] = Query(None, ge=1, le=90),
    task_retention_days: Optional[int] = Query(None, ge=1, le=365),
    current_admin: User = Depends(get_current_admin_user)
):
    """Ручная очистка старых файлов и задач"""
    from app.queue.periodic_tasks import (
        cleanup_old_files,
        cleanup_temp_files,
        cleanup_old_tasks
    )
    
    results = {}
    
    # Очистка старых файлов
    if file_retention_days:
        # Временно изменить настройку
        from app.config import settings
        old_retention = getattr(settings, "STORAGE_RETENTION_DAYS", 7)
        settings.STORAGE_RETENTION_DAYS = file_retention_days
        
        results["files"] = cleanup_old_files()
        
        # Вернуть настройку
        settings.STORAGE_RETENTION_DAYS = old_retention
    
    # Очистка temp файлов
    results["temp_files"] = cleanup_temp_files()
    
    # Очистка старых задач
    if task_retention_days:
        results["tasks"] = cleanup_old_tasks(task_retention_days)
    
    return results
```

### Тестирование подзадачи 4.4

**Unit тесты periodic tasks:**
- cleanup_old_files() находит файлы старее retention_days
- cleanup_old_files() удаляет файлы из MinIO
- cleanup_old_files() помечает файлы как удаленные в БД
- cleanup_old_files() не удаляет активные файлы
- cleanup_temp_files() находит temp файлы старее 24 часов
- cleanup_temp_files() удаляет orphan temp файлы
- cleanup_temp_files() не удаляет свежие temp файлы
- cleanup_old_tasks() находит задачи старее cutoff_date
- cleanup_old_tasks() удаляет старые задачи из БД

**Интеграционные тесты:**
- Автоочистка выполняется по расписанию:
  - cleanup_old_files каждые 6 часов
  - cleanup_temp_files каждый час
  - cleanup_old_tasks ежедневно в 2:00
- Удаляются только старые файлы (по дате)
- Удаляются только orphan temp файлы
- Удаляются только старые задачи
- Связанные записи в БД удаляются корректно

**Тесты ручной очистки:**
- Manual cleanup работает корректно
- Admin endpoint требует авторизации admin
- file_retention_days параметр работает
- task_retention_days параметр работает
- Результат возвращается корректно

**Regression тесты:**
- Активные файлы не удаляются
- Активные temp файлы не удаляются
- Нет утечек файлов при частых очистках

---

## Подзадача 4.5: Мониторинг и алерты

### Задачи реализации

**Prometheus alerts в [docker/prometheus/alerts.yml](docker/prometheus/alerts.yml):**

```yaml
groups:
  - name: ffmpeg_api_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total[5m]))
          ) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} for last 5 minutes"
      
      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "95th percentile latency is {{ $value }}s for last 5 minutes"
      
      # Queue size threshold
      - alert: HighQueueSize
        expr: |
          celery_queue_size{queue="default"} > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High queue size"
          description: "Queue size is {{ $value }} tasks"
      
      # High resource usage
      - alert: HighCPUUsage
        expr: |
          cpu_usage_percent > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"
      
      - alert: HighMemoryUsage
        expr: |
          memory_usage_percent > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"
      
      # Disk space low
      - alert: LowDiskSpace
        expr: |
          disk_usage_percent > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space"
          description: "Disk usage is {{ $value }}%"
      
      # Worker not responding
      - alert: WorkerNotResponding
        expr: |
          up{job="celery_worker"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Celery worker not responding"
          description: "Worker {{ $labels.instance }} is down"
      
      # Database connection issues
      - alert: DatabaseConnectionError
        expr: |
          pg_up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection error"
          description: "Cannot connect to PostgreSQL"
```

**Grafana дашборды (дополнение существующих):**

*[docker/grafana/dashboards/task_performance.json](docker/grafana/dashboards/task_performance.json):*
- Tasks by type
- Task duration (average, p95)
- Task success rate
- Task failure rate by type
- Active tasks by status

*[docker/grafana/dashboards/system_resources.json](docker/grafana/dashboards/system_resources.json):*
- CPU usage by container
- Memory usage by container
- Disk I/O
- Network I/O
- Container uptime

*[docker/grafana/dashboards/error_rates.json](docker/grafana/dashboards/error_rates.json):*
- HTTP error rate by endpoint
- HTTP error rate by status code
- Celery task failure rate
- Database query errors
- MinIO operation errors

*[docker/grafana/dashboards/queue_size.json](docker/grafana/dashboards/queue_size.json):*
- Queue size by status
- Queue size by type
- Tasks processed per minute
- Tasks failed per minute
- Worker utilization

**Структурированное логирование в [app/logging.py](app/logging.py):**

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON formatter для структурированного логирования"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Добавление extra полей
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        
        # Добавление exception если есть
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging():
    """Настройка структурированного логирования"""
    
    # Создание logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    return logger

# Использование
logger = setup_logging()

# Логирование с контекстом
logger.info("Task started", extra={
    "user_id": 123,
    "request_id": "abc-123",
    "task_id": 456
})

# Логирование ошибки
try:
    # ...
except Exception as e:
    logger.error("Task failed", extra={
        "task_id": 456,
        "error": str(e)
    }, exc_info=True)
```

### Тестирование подзадачи 4.5

**Интеграционные тесты Prometheus:**
- Alerts срабатывают при превышении порогов:
  - HighErrorRate при >5% ошибок
  - HighLatency при p95 > 1s
  - HighQueueSize при >100 задач
  - HighCPUUsage при >80%
  - HighMemoryUsage при >85%
  - LowDiskSpace при >90%
  - WorkerNotResponding при worker down
  - DatabaseConnectionError при недоступности БД
- Alerts не срабатывают в нормальных условиях
- Alerts автоматически исчезают при восстановлении

**Интеграционные тесты Grafana:**
- Дашборды отображают корректные данные
- Real-time обновление графиков
- Все метрики отображаются
- Графики читаемы
- Annotations для alert'ов работают

**Тесты логирования:**
- Структурированные логи в JSON формате
- Все поля присутствуют (timestamp, level, message, etc.)
- Extra поля добавляются корректно (user_id, request_id, task_id)
- Exception'ы логируются корректно
- Логи парсятся log aggregators (ELK, Loki)

**Regression тесты:**
- Метрики точны и своевременны
- Alerts не вызывают false positives
- Логи не теряются

---

## Подзадача 4.6: Users endpoints

### Задачи реализации

**Users endpoints в [app/api/v1/users.py](app/api/v1/users.py):**

```python
from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user
from app.schemas.user import UserSettings, UserStats, UserHistory, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получение информации о текущем пользователе"""
    return UserResponse.from_orm(current_user)

@router.get("/me/settings", response_model=UserSettings)
async def get_user_settings(
    current_user: User = Depends(get_current_user)
):
    """Получение настроек пользователя"""
    return UserSettings(
        settings=current_user.settings or {},
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@router.put("/me/settings")
async def update_user_settings(
    settings: dict,
    current_user: User = Depends(get_current_user)
):
    """Обновление настроек пользователя"""
    from app.database.connection import get_db
    from app.database.repositories.user_repository import UserRepository
    
    db = get_db()
    user_repo = UserRepository(db)
    
    # Объединение настроек
    current_settings = current_user.settings or {}
    updated_settings = {**current_settings, **settings}
    
    # Обновление
    updated_user = await user_repo.update(
        current_user,
        settings=updated_settings
    )
    
    return UserSettings(
        settings=updated_user.settings,
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at
    )

@router.get("/me/stats", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_current_user)
):
    """Статистика пользователя"""
    from app.database.connection import get_db
    from app.database.repositories.task_repository import TaskRepository
    from app.database.repositories.file_repository import FileRepository
    
    db = get_db()
    task_repo = TaskRepository(db)
    file_repo = FileRepository(db)
    
    # Статистика задач
    tasks_stats = await task_repo.get_tasks_statistics(current_user.id)
    
    # Статистика файлов
    storage_used = await file_repo.get_user_storage_usage(current_user.id)
    files_count = await file_repo.get_user_files_count(current_user.id)
    
    return UserStats(
        total_tasks=tasks_stats.get("total", 0),
        completed_tasks=tasks_stats.get("completed", 0),
        failed_tasks=tasks_stats.get("failed", 0),
        processing_tasks=tasks_stats.get("processing", 0),
        total_files=files_count,
        storage_used=storage_used,
        storage_limit=1073741824,  # 1GB
    )

@router.get("/me/history", response_model=UserHistory)
async def get_user_history(
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """История задач пользователя"""
    from app.database.connection import get_db
    from app.database.repositories.task_repository import TaskRepository
    
    db = get_db()
    task_repo = TaskRepository(db)
    
    tasks = await task_repo.get_tasks_with_filters(
        user_id=current_user.id,
        filters={
            "status": status,
            "type": task_type,
        },
        offset=offset,
        limit=limit
    )
    
    return UserHistory(
        tasks=[TaskResponse.from_orm(task) for task in tasks.tasks],
        total=tasks.total,
        page=offset // limit + 1,
        page_size=limit
    )
```

**User schemas в [app/schemas/user.py](app/schemas/user.py) (дополнение):**

```python
class UserSettings(BaseModel):
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class UserStats(BaseModel):
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    total_files: int
    storage_used: int
    storage_limit: int

class UserHistory(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
```

### Тестирование подзадачи 4.6

**Unit тесты UserService (дополнение):**
- get_settings() возвращает настройки пользователя
- update_settings() объединяет настройки
- update_settings() перезаписывает существующие
- get_stats() возвращает корректную статистику
- get_stats() считает total_tasks
- get_stats() считает completed_tasks
- get_stats() считает failed_tasks
- get_stats() считает processing_tasks
- get_stats() считает storage_used
- get_stats() считает storage_limit
- get_history() возвращает задачи с пагинацией
- get_history() фильтрует по статусу
- get_history() фильтрует по типу

**Интеграционные тесты endpoints:**

*GET /users/me:*
- Успешный запрос возвращает UserResponse
- Запрос без авторизации возвращает 401
- Ответ не содержит sensitive данные

*GET /users/me/settings:*
- Успешный запрос возвращает UserSettings
- Значения по умолчанию возвращаются для новых пользователей

*PUT /users/me/settings:*
- Успешный запрос обновляет настройки
- Настройки объединяются с существующими
- Запрос без авторизации возвращает 401

*GET /users/me/stats:*
- Успешный запрос возвращает UserStats
- Статистика точна (сравнить с БД)
- storage_used корректен
- storage_limit задан корректно

*GET /users/me/history:*
- Успешный запрос возвращает UserHistory
- Пагинация работает корректно
- Фильтр по статусу работает
- Фильтр по типу работает
- Только задачи пользователя

**Тесты прав доступа:**
- Пользователь видит только свои данные
- Пользователь не может видеть настройки других

---

## Подзадача 4.7: Admin endpoints

### Задачи реализации

**Admin endpoints в [app/api/v1/admin.py](app/api/v1/admin.py):**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import get_current_admin_user
from app.schemas.admin import AdminTasksResponse, AdminUsersResponse, AdminMetricsResponse, AdminQueueStatusResponse

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/tasks", response_model=AdminTasksResponse)
async def get_all_tasks(
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user)
):
    """Получение всех задач"""
    from app.database.connection import get_db
    from app.database.repositories.task_repository import TaskRepository
    
    db = get_db()
    task_repo = TaskRepository(db)
    
    tasks = await task_repo.get_all_tasks(
        status=status,
        user_id=user_id,
        offset=offset,
        limit=limit
    )
    
    return AdminTasksResponse(
        tasks=[TaskResponse.from_orm(task) for task in tasks.tasks],
        total=tasks.total,
        page=offset // limit + 1,
        page_size=limit
    )

@router.get("/users", response_model=AdminUsersResponse)
async def get_all_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user)
):
    """Получение всех пользователей"""
    from app.database.connection import get_db
    from app.database.repositories.user_repository import UserRepository
    
    db = get_db()
    user_repo = UserRepository(db)
    
    users = await user_repo.get_all(offset=offset, limit=limit)
    
    # Подсчет задач для каждого пользователя
    from app.database.repositories.task_repository import TaskRepository
    task_repo = TaskRepository(db)
    
    users_with_stats = []
    for user in users:
        stats = await task_repo.get_tasks_statistics(user.id)
        users_with_stats.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "tasks_count": stats.get("total", 0)
        })
    
    total = await user_repo.count_all()
    
    return AdminUsersResponse(
        users=users_with_stats,
        total=total,
        page=offset // limit + 1,
        page_size=limit
    )

@router.get("/metrics", response_model=AdminMetricsResponse)
async def get_system_metrics(
    current_admin: User = Depends(get_current_admin_user)
):
    """Получение системных метрик"""
    from app.database.connection import get_db
    from app.database.repositories.task_repository import TaskRepository
    from app.database.repositories.file_repository import FileRepository
    from app.queue.celery_app import celery_app
    
    db = get_db()
    task_repo = TaskRepository(db)
    file_repo = FileRepository(db)
    
    # Метрики задач
    all_tasks_stats = await task_repo.get_all_tasks_statistics()
    
    # Метрики файлов
    total_storage = await file_repo.get_total_storage_usage()
    total_files_count = await file_repo.count_all()
    
    # Метрики очереди
    inspect = celery_app.control.inspect()
    active_tasks = inspect.active() or {}
    scheduled_tasks = inspect.scheduled() or {}
    registered_tasks = inspect.registered() or {}
    
    queue_size = 0
    if active_tasks:
        for host, tasks in active_tasks.items():
            queue_size += len(tasks)
    
    return AdminMetricsResponse(
        total_users=await user_repo.count_all(),
        total_tasks=all_tasks_stats.get("total", 0),
        completed_tasks=all_tasks_stats.get("completed", 0),
        failed_tasks=all_tasks_stats.get("failed", 0),
        processing_tasks=all_tasks_stats.get("processing", 0),
        total_files=total_files_count,
        total_storage=total_storage,
        queue_size=queue_size,
        active_workers=len(active_tasks) if active_tasks else 0,
    )

@router.get("/queue-status", response_model=AdminQueueStatusResponse)
async def get_queue_status(
    current_admin: User = Depends(get_current_admin_user)
):
    """Статус очереди"""
    from app.queue.celery_app import celery_app
    
    inspect = celery_app.control.inspect()
    
    active = inspect.active() or {}
    scheduled = inspect.scheduled() or {}
    reserved = inspect.reserved() or {}
    
    # Подсчет задач по статусу
    pending_count = sum(len(tasks) for tasks in scheduled.values())
    processing_count = sum(len(tasks) for tasks in active.values())
    reserved_count = sum(len(tasks) for tasks in reserved.values())
    
    return AdminQueueStatusResponse(
        pending=pending_count,
        processing=processing_count,
        reserved=reserved_count,
        total=pending_count + processing_count + reserved_count,
        workers=list(active.keys()) if active else []
    )

@router.post("/cleanup")
async def manual_cleanup(
    file_retention_days: Optional[int] = Query(None, ge=1, le=90),
    task_retention_days: Optional[int] = Query(None, ge=1, le=365),
    current_admin: User = Depends(get_current_admin_user)
):
    """Ручная очистка старых файлов и задач"""
    from app.queue.periodic_tasks import (
        cleanup_old_files,
        cleanup_temp_files,
        cleanup_old_tasks
    )
    
    results = {}
    
    # Очистка старых файлов
    if file_retention_days:
        from app.config import settings
        old_retention = getattr(settings, "STORAGE_RETENTION_DAYS", 7)
        settings.STORAGE_RETENTION_DAYS = file_retention_days
        
        results["files"] = cleanup_old_files()
        
        settings.STORAGE_RETENTION_DAYS = old_retention
    
    # Очистка temp файлов
    results["temp_files"] = cleanup_temp_files()
    
    # Очистка старых задач
    if task_retention_days:
        results["tasks"] = cleanup_old_tasks(task_retention_days)
    
    return results
```

**Admin middleware в [app/middleware/admin_middleware.py](app/middleware/admin_middleware.py):**

```python
from fastapi import HTTPException, status

def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Проверка admin роли"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
```

**Admin schemas в [app/schemas/admin.py](app/schemas/admin.py):**

```python
class AdminTasksResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int

class AdminUserStats(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    tasks_count: int

class AdminUsersResponse(BaseModel):
    users: List[AdminUserStats]
    total: int
    page: int
    page_size: int

class AdminMetricsResponse(BaseModel):
    total_users: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    total_files: int
    total_storage: int
    queue_size: int
    active_workers: int

class AdminQueueStatusResponse(BaseModel):
    pending: int
    processing: int
    reserved: int
    total: int
    workers: List[str]
```

### Тестирование подзадачи 4.7

**Unit тесты AdminService:**
- get_all_tasks() возвращает все задачи
- get_all_tasks() фильтрует по статусу
- get_all_tasks() фильтрует по user_id
- get_all_users() возвращает всех пользователей
- get_all_users() включает статистику задач
- get_system_metrics() возвращает корректные метрики
- get_system_metrics() считает total_users
- get_system_metrics() считает total_tasks
- get_system_metrics() считает queue_size
- get_system_metrics() считает active_workers
- get_queue_status() возвращает актуальный статус очереди
- get_queue_status() разделяет pending/processing/reserved

**Интеграционные тесты endpoints:**

*GET /admin/tasks:*
- Успешный запрос возвращает AdminTasksResponse
- Запрос без admin токена возвращает 403
- Запрос без авторизации возвращает 401
- Пагинация работает
- Фильтры работают (status, user_id)
- Все задачи возвращаются

*GET /admin/users:*
- Успешный запрос возвращает AdminUsersResponse
- Запрос без admin токена возвращает 403
- Пользователи включают статистику задач
- Пагинация работает

*GET /admin/metrics:*
- Успешный запрос возвращает AdminMetricsResponse
- Запрос без admin токена возвращает 403
- Метрики точны (сравнить с БД)
- Метрики актуальны

*GET /admin/queue-status:*
- Успешный запрос возвращает AdminQueueStatusResponse
- Запрос без admin токена возвращает 403
- Статус актуальный
- Workers перечислены корректно

*POST /admin/cleanup:*
- Успешный запрос запускает очистку
- Запрос без admin токена возвращает 403
- file_retention_days работает
- task_retention_days работает
- Результат возвращается корректно

**Тесты прав доступа:**
- Admin имеет доступ ко всем endpoint'ам
- Non-admin не имеет доступа (403)
- Admin middleware работает корректно

---

## Критерии завершения Этапа 4

**Функциональные требования:**
- FFmpeg оптимизация работает (preset, tune, CRF)
- Hardware acceleration работает (если доступно)
- Кэширование работает (metadata cache, result cache)
- Streaming для больших файлов работает (chunked upload/download)
- Автоочистка работает (периодические задачи)
- Мониторинг расширен (Prometheus alerts, новые дашборды)
- Структурированное логирование работает
- Users endpoints работают
- Admin endpoints работают

**Требования к тестированию:**
- Все unit тесты проходят
- Все интеграционные тесты проходят
- Performance тесты показывают улучшение
- Coverage > 75% для кода этапа 4

**Документация:**
- Оптимизации документированы
- Cache API документирован
- Admin endpoints документированы в OpenAPI
- Prometheus alerts документированы
- Структурированные логи документированы

**Производительность:**
- Обработка видео на 20-30% быстрее с оптимизациями
- Повторные операции на 50%+ быстрее с кэшем
- Загрузка 1GB файла < 10 минут
- Загрузка не потребляет > 500MB RAM
- Скачивание работает плавно без буферизации
