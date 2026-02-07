/**
 * API Request Generator
 */
class RequestGenerator {
    constructor() {
        this.taskTypeSelect = document.getElementById('genTaskType');
        this.formContainer = document.getElementById('genFormContainer');
        this.btnCurl = document.getElementById('btnGenCurl');
        this.btnPython = document.getElementById('btnGenPython');
        this.btnExecute = document.getElementById('btnExecuteRequest');
        this.output = document.getElementById('genOutput');

        this.init();
    }

    init() {
        if (!this.taskTypeSelect) return;

        // Event listeners
        this.taskTypeSelect.addEventListener('change', () => this.renderForm());
        this.btnCurl.addEventListener('click', () => this.generateCode('curl'));
        this.btnPython.addEventListener('click', () => this.generateCode('python'));
        this.btnExecute.addEventListener('click', () => this.executeRequest());

        // Initial render
        this.renderForm();
    }

    getTaskType() {
        return this.taskTypeSelect.value;
    }

    renderForm() {
        const type = this.getTaskType();
        let html = '';

        switch (type) {
            case 'join':
                html = `
                    <div class="dynamic-field-group">
                        <label>ID файлов (через запятую)</label>
                        <input type="text" id="joinFiles" class="form-input" placeholder="1, 2, 3">
                        <div class="help-text">Минимум 2 файла</div>
                    </div>
                    <div class="dynamic-field-group">
                        <label>Имя выходного файла</label>
                        <input type="text" id="joinOutput" class="form-input" value="joined.mp4">
                    </div>
                `;
                break;

            case 'video_overlay':
                html = `
                    <div class="dynamic-field-group">
                        <label>Base Video ID</label>
                        <input type="number" id="baseFileId" class="form-input" placeholder="ID основного видео">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Overlay Video ID</label>
                        <input type="number" id="overlayFileId" class="form-input" placeholder="ID видео для наложения">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Position X</label>
                        <input type="number" id="overlayX" class="form-input" value="10">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Position Y</label>
                        <input type="number" id="overlayY" class="form-input" value="10">
                    </div>
                     <div class="dynamic-field-group">
                        <label>Scale (0.1 - 1.0)</label>
                        <input type="number" id="overlayScale" class="form-input" value="0.3" step="0.1" max="1">
                    </div>
                `;
                break;

            case 'text_overlay':
                html = `
                    <div class="dynamic-field-group">
                        <label>Video ID</label>
                        <input type="number" id="textVideoId" class="form-input" placeholder="ID видео">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Текст</label>
                        <input type="text" id="textContent" class="form-input" placeholder="Текст для наложения">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Позиция</label>
                        <select id="textPosition" class="form-input">
                            <option value="center">Center</option>
                            <option value="top-left">Top Left</option>
                            <option value="top-right">Top Right</option>
                            <option value="bottom-left">Bottom Left</option>
                            <option value="bottom-right">Bottom Right</option>
                        </select>
                    </div>
                    <div class="dynamic-field-group">
                        <label>Цвет (HEX)</label>
                        <input type="text" id="textColor" class="form-input" value="#FFFFFF">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Размер шрифта</label>
                        <input type="number" id="textSize" class="form-input" value="48">
                    </div>
                `;
                break;

            case 'audio_overlay':
                html = `
                    <div class="dynamic-field-group">
                        <label>Video ID</label>
                        <input type="number" id="audioVideoId" class="form-input" placeholder="ID видео">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Audio ID</label>
                        <input type="number" id="audioAudioId" class="form-input" placeholder="ID аудио">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Режим</label>
                        <select id="audioMode" class="form-input">
                            <option value="replace">Заменить звук</option>
                            <option value="mix">Смешать</option>
                        </select>
                    </div>
                `;
                break;

            case 'subtitles':
                html = `
                    <div class="dynamic-field-group">
                        <label>Video ID</label>
                        <input type="number" id="subVideoId" class="form-input" placeholder="ID видео">
                    </div>
                    <div class="dynamic-field-group">
                        <label>Subtitle File ID</label>
                        <input type="number" id="subFileId" class="form-input" placeholder="ID файла субтитров">
                    </div>
                     <div class="dynamic-field-group">
                        <label>Формат</label>
                        <select id="subFormat" class="form-input">
                            <option value="SRT">SRT</option>
                            <option value="VTT">VTT</option>
                            <option value="ASS">ASS</option>
                        </select>
                    </div>
                `;
                break;
        }

        this.formContainer.innerHTML = html;
    }

    getParams() {
        const type = this.getTaskType();
        let params = {};

        // Helper to parse FileSource (int or string)
        const parseFileSource = (val) => {
            if (!val) return null;
            val = val.trim();
            if (/^\d+$/.test(val)) return parseInt(val, 10);
            return val;
        };

        // Helper for ID lists
        const parseIds = (str) => str.split(',').map(s => parseFileSource(s)).filter(v => v !== null);

        try {
            switch (type) {
                case 'join':
                    params = {
                        file_ids: parseIds(document.getElementById('joinFiles').value),
                        output_filename: document.getElementById('joinOutput').value
                    };
                    break;
                case 'video_overlay':
                    params = {
                        base_video_file_id: parseFileSource(document.getElementById('baseFileId').value),
                        overlay_video_file_id: parseFileSource(document.getElementById('overlayFileId').value),
                        config: {
                            x: parseInt(document.getElementById('overlayX').value),
                            y: parseInt(document.getElementById('overlayY').value),
                            scale: parseFloat(document.getElementById('overlayScale').value),
                        }
                    };
                    break;
                case 'text_overlay':
                    params = {
                        video_file_id: parseFileSource(document.getElementById('textVideoId').value),
                        text: document.getElementById('textContent').value,
                        position: {
                            type: "relative",
                            position: document.getElementById('textPosition').value
                        },
                        style: {
                            color: document.getElementById('textColor').value,
                            font_size: parseInt(document.getElementById('textSize').value)
                        }
                    };
                    break;
                case 'audio_overlay':
                    params = {
                        video_file_id: parseFileSource(document.getElementById('audioVideoId').value),
                        audio_file_id: parseFileSource(document.getElementById('audioAudioId').value),
                        mode: document.getElementById('audioMode').value,
                        overlay_volume: 1.0 // Default
                    };
                    break;
                case 'subtitles':
                    params = {
                        video_file_id: parseFileSource(document.getElementById('subVideoId').value),
                        subtitle_file_id: parseFileSource(document.getElementById('subFileId').value),
                        format: document.getElementById('subFormat').value
                    };
                    break;
            }
        } catch (e) {
            console.error("Error getting params", e);
            return null; // Validation error
        }

        return params;
    }

    generateCode(lang) {
        const type = this.getTaskType();
        const params = this.getParams();
        const baseUrl = window.location.origin + '/api/v1';
        let endpoint = '';
        let code = '';

        if (!params) {
            this.output.textContent = 'Ошибка: Проверьте введенные данные';
            return;
        }

        switch (type) {
            case 'join': endpoint = '/tasks/join'; break;
            case 'video_overlay': endpoint = '/tasks/video-overlay'; break;
            case 'text_overlay': endpoint = '/tasks/text-overlay'; break;
            case 'audio_overlay': endpoint = '/tasks/audio-overlay'; break;
            case 'subtitles': endpoint = '/tasks/subtitles'; break;
        }

        if (lang === 'curl') {
            code = `curl -X POST "${baseUrl}${endpoint}" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${API.token || 'YOUR_TOKEN'}" \\
  -d '${JSON.stringify(params, null, 2)}'`;
        } else if (lang === 'python') {
            code = `import requests

url = "${baseUrl}${endpoint}"
token = "${API.token || 'YOUR_TOKEN'}"

payload = ${JSON.stringify(params, null, 4)}

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`;
        }

        this.output.textContent = code;
    }

    async executeRequest() {
        const type = this.getTaskType();
        const params = this.getParams();
        let endpoint = '';

        if (!params) {
            showNotification('Проверьте данные формы', 'error');
            return;
        }

        switch (type) {
            case 'join': endpoint = '/tasks/join'; break;
            case 'video_overlay': endpoint = '/tasks/video-overlay'; break;
            case 'text_overlay': endpoint = '/tasks/text-overlay'; break;
            case 'audio_overlay': endpoint = '/tasks/audio-overlay'; break;
            case 'subtitles': endpoint = '/tasks/subtitles'; break;
        }

        this.output.textContent = 'Отправка запроса...';

        try {
            const result = await API.post(endpoint, params);
            this.output.textContent = JSON.stringify(result, null, 2);
            showNotification('Запрос выполнен успешно!', 'success');

            // Refresh tasks list if on tasks page or just generally
            // But we are on generator page. Maybe show notification.
        } catch (error) {
            this.output.textContent = `Error: ${error.message}`;
            showNotification('Ошибка выполнения запроса', 'error');
        }
    }
}
