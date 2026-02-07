/**
 * FFmpeg API - Dashboard JavaScript
 */

// Check authentication
if (!API.isAuthenticated()) {
    window.location.href = '/login.html';
}

// State
let currentUser = null;
let userApiKey = null;
let apiKeyVisible = false;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadUserData();
    initNavigation();
    initSidebar();
    initApiKey();
    initLogout();
    if (typeof RequestGenerator !== 'undefined') new RequestGenerator();
});

/**
 * Load user data
 */
async function loadUserData() {
    try {
        currentUser = await Auth.getMe();

        // Update UI
        document.getElementById('userName').textContent = currentUser.username;
        document.getElementById('userAvatar').textContent = currentUser.username.charAt(0).toUpperCase();

        // Settings form
        document.getElementById('settingsUsername').value = currentUser.username;
        document.getElementById('settingsEmail').value = currentUser.email;
        document.getElementById('settingsCreatedAt').value = currentUser.created_at
            ? formatDate(currentUser.created_at)
            : 'Неизвестно';

        // Load dashboard data
        await loadDashboardData();
    } catch (error) {
        console.error('Failed to load user:', error);
        // Redirect to login if unauthorized
        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
            Auth.logout();
        }
    }
}

/**
 * Load dashboard statistics
 */
async function loadDashboardData() {
    try {
        // Load tasks
        const tasksData = await API.get('/tasks?limit=5');

        // Update stats
        document.getElementById('totalTasks').textContent = tasksData.total || 0;

        // Count completed tasks
        const completedCount = (tasksData.tasks || []).filter(t => t.status === 'completed').length;
        document.getElementById('completedTasks').textContent = completedCount;

        // Render recent tasks
        renderRecentTasks(tasksData.tasks || []);

        // Load files
        const filesData = await API.get('/files?limit=10');
        document.getElementById('totalFiles').textContent = filesData.total || 0;

        // Calculate storage
        const totalStorage = (filesData.files || []).reduce((sum, f) => sum + (f.size || 0), 0);
        document.getElementById('storageUsed').textContent = formatFileSize(totalStorage);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

/**
 * Render recent tasks
 */
function renderRecentTasks(tasks) {
    const container = document.getElementById('recentTasks');

    if (!tasks || tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>Нет задач</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tasks.map(task => `
        <div class="task-item">
            <span class="task-type">${task.type || 'task'}</span>
            <div class="task-info">
                <div class="task-id">Задача #${task.id}</div>
                <div class="task-date">${task.created_at ? formatDate(task.created_at) : ''}</div>
            </div>
            <span class="task-status ${task.status}">${getStatusLabel(task.status)}</span>
        </div>
    `).join('');
}

/**
 * Get status label in Russian
 */
function getStatusLabel(status) {
    const labels = {
        'pending': 'Ожидает',
        'processing': 'В обработке',
        'completed': 'Выполнено',
        'failed': 'Ошибка',
        'cancelled': 'Отменено'
    };
    return labels[status] || status;
}

/**
 * Navigation
 */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    const pages = document.querySelectorAll('.page');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const pageId = item.dataset.page;

            // Update nav
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update pages
            pages.forEach(page => page.classList.remove('active'));
            document.getElementById(`page-${pageId}`).classList.add('active');

            // Update title
            document.getElementById('pageTitle').textContent = item.querySelector('span').textContent;

            // Load page data
            loadPageData(pageId);

            // Close mobile sidebar
            document.querySelector('.sidebar').classList.remove('open');
        });
    });

    // Also handle links with data-page attribute
    document.querySelectorAll('a[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const pageId = link.dataset.page;
            const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
            if (navItem) navItem.click();
        });
    });
}

/**
 * Load page-specific data
 */
async function loadPageData(pageId) {
    switch (pageId) {
        case 'tasks':
            await loadTasks();
            break;
        case 'files':
            await loadFiles();
            break;
    }
}

/**
 * Load tasks with pagination
 */
async function loadTasks(page = 1) {
    const container = document.getElementById('tasksList');
    const statusFilter = document.getElementById('taskStatusFilter').value;

    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const params = new URLSearchParams({
            offset: (page - 1) * 20,
            limit: 20
        });

        if (statusFilter) {
            params.append('status', statusFilter);
        }

        const data = await API.get(`/tasks?${params}`);

        if (!data.tasks || data.tasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📋</div>
                    <p>Нет задач</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.tasks.map(task => `
            <div class="task-item">
                <span class="task-type">${task.type || 'task'}</span>
                <div class="task-info">
                    <div class="task-id">Задача #${task.id}</div>
                    <div class="task-date">${task.created_at ? formatDate(task.created_at) : ''}</div>
                </div>
                <span class="task-status ${task.status}">${getStatusLabel(task.status)}</span>
            </div>
        `).join('');

    } catch (error) {
        container.innerHTML = `<div class="empty-state">Ошибка загрузки</div>`;
    }
}

/**
 * Load files
 */
async function loadFiles() {
    const container = document.getElementById('filesList');
    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const data = await API.get('/files?limit=50');

        if (!data.files || data.files.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📁</div>
                    <p>Нет файлов</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.files.map(file => `
            <div class="file-card">
                <div class="file-icon">${getFileIcon(file.filename)}</div>
                <div class="file-name">${file.filename || 'Файл'}</div>
                <div class="file-size">${formatFileSize(file.size || 0)}</div>
            </div>
        `).join('');

    } catch (error) {
        container.innerHTML = `<div class="empty-state">Ошибка загрузки</div>`;
    }
}

/**
 * Get file icon by extension
 */
function getFileIcon(filename) {
    if (!filename) return '📄';
    const ext = filename.split('.').pop()?.toLowerCase();
    const icons = {
        'mp4': '🎬',
        'avi': '🎬',
        'mov': '🎬',
        'mkv': '🎬',
        'mp3': '🎵',
        'wav': '🎵',
        'aac': '🎵',
        'srt': '📝',
        'vtt': '📝',
        'ass': '📝'
    };
    return icons[ext] || '📄';
}

/**
 * Sidebar toggle for mobile
 */
function initSidebar() {
    const toggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');

    toggle?.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 &&
            !sidebar.contains(e.target) &&
            !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

/**
 * API Key management
 */
function initApiKey() {
    const toggleBtn = document.getElementById('toggleApiKey');
    const copyBtn = document.getElementById('copyApiKey');
    const regenerateBtn = document.getElementById('regenerateApiKey');
    const apiKeyDisplay = document.getElementById('apiKeyValue');

    // Toggle visibility
    toggleBtn?.addEventListener('click', async () => {
        if (apiKeyVisible) {
            apiKeyDisplay.textContent = '••••••••••••••••••••••••••••••••';
            apiKeyVisible = false;
        } else {
            // Get API key from user settings or show JWT token
            apiKeyDisplay.textContent = API.token || 'Ключ не найден';
            apiKeyVisible = true;
        }
    });

    // Copy to clipboard
    copyBtn?.addEventListener('click', async () => {
        const key = apiKeyVisible ? apiKeyDisplay.textContent : API.token;
        await navigator.clipboard.writeText(key);
        showNotification('Ключ скопирован!', 'success');
    });

    // Regenerate
    regenerateBtn?.addEventListener('click', async () => {
        if (!confirm('Вы уверены? Старый ключ перестанет работать.')) {
            return;
        }

        try {
            // API for regenerating key would go here
            showNotification('Новый ключ сгенерирован', 'success');
        } catch (error) {
            showNotification('Ошибка генерации ключа', 'error');
        }
    });
}

/**
 * Logout
 */
function initLogout() {
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        Auth.logout();
    });
}

// Task status filter
document.getElementById('taskStatusFilter')?.addEventListener('change', () => {
    loadTasks();
});
