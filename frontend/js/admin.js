/**
 * FFmpeg API - Admin Panel JavaScript
 */

// Check authentication and admin status
if (!API.isAuthenticated()) {
    window.location.href = '/login.html';
}

let currentUser = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await checkAdminAccess();
    initNavigation();
    initModals();
    initLogout();
    loadOverviewData();
});

/**
 * Check admin access
 */
async function checkAdminAccess() {
    try {
        currentUser = await Auth.getMe();
        document.getElementById('userName').textContent = currentUser.username;

        if (!currentUser.is_admin) {
            alert('Доступ запрещён. Требуются права администратора.');
            window.location.href = '/dashboard.html';
        }
    } catch (error) {
        Auth.logout();
    }
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

            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            pages.forEach(page => page.classList.remove('active'));
            document.getElementById(`page-${pageId}`).classList.add('active');

            document.getElementById('pageTitle').textContent = item.querySelector('span').textContent;
            loadPageData(pageId);

            document.querySelector('.sidebar').classList.remove('open');
        });
    });

    // Sidebar toggle
    document.querySelector('.sidebar-toggle')?.addEventListener('click', () => {
        document.querySelector('.sidebar').classList.toggle('open');
    });
}

/**
 * Load page data
 */
async function loadPageData(pageId) {
    switch (pageId) {
        case 'overview': await loadOverviewData(); break;
        case 'users': await loadUsers(); break;
        case 'tasks': await loadAllTasks(); break;
        case 'queue': await loadQueueStatus(); break;
        case 'system': await loadSystemMetrics(); break;
    }
}

/**
 * Load overview data
 */
async function loadOverviewData() {
    try {
        const metrics = await API.get('/admin/metrics');

        document.getElementById('totalUsers').textContent = metrics.total_users || 0;
        document.getElementById('totalTasks').textContent = metrics.total_tasks || 0;
        document.getElementById('pendingTasks').textContent = metrics.pending_tasks || 0;
        document.getElementById('storageUsed').textContent = formatFileSize(metrics.storage_used || 0);

        // Load recent users
        const usersData = await API.get('/admin/users?limit=5');
        renderRecentUsers(usersData.users || []);

        // Load active tasks
        const tasksData = await API.get('/admin/tasks?status=processing&limit=5');
        renderActiveTasks(tasksData.tasks || []);

    } catch (error) {
        console.error('Failed to load overview:', error);
    }
}

function renderRecentUsers(users) {
    const container = document.getElementById('recentUsers');
    if (!users.length) {
        container.innerHTML = '<div class="empty-state">Нет пользователей</div>';
        return;
    }
    container.innerHTML = users.map(user => `
        <div class="user-item">
            <div class="user-avatar">${user.username.charAt(0).toUpperCase()}</div>
            <div class="user-info">
                <div class="user-name">${user.username}</div>
                <div class="user-email">${user.email}</div>
            </div>
        </div>
    `).join('');
}

function renderActiveTasks(tasks) {
    const container = document.getElementById('activeTasks');
    if (!tasks.length) {
        container.innerHTML = '<div class="empty-state">Нет активных задач</div>';
        return;
    }
    container.innerHTML = tasks.map(task => `
        <div class="task-item">
            <span class="task-type">${task.type || 'task'}</span>
            <div class="task-info">
                <div class="task-id">Задача #${task.id}</div>
            </div>
            <span class="task-status ${task.status}">${task.status}</span>
        </div>
    `).join('');
}

/**
 * Load users
 */
async function loadUsers(page = 1) {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Загрузка...</td></tr>';

    try {
        const data = await API.get(`/admin/users?offset=${(page - 1) * 20}&limit=20`);

        if (!data.users || !data.users.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Нет пользователей</td></tr>';
            return;
        }

        tbody.innerHTML = data.users.map(user => `
            <tr>
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td>${user.email}</td>
                <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Активен' : 'Неактивен'}</span></td>
                <td>${user.is_admin ? '<span class="status-badge admin">Админ</span>' : 'Пользователь'}</td>
                <td class="actions">
                    <button class="btn btn-ghost btn-sm" onclick="toggleUserStatus(${user.id}, ${!user.is_active})">${user.is_active ? 'Блок' : 'Разблок'}</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
    }
}

/**
 * Toggle user status
 */
async function toggleUserStatus(userId, activate) {
    try {
        await API.put(`/admin/users/${userId}`, { is_active: activate });
        showNotification(activate ? 'Пользователь активирован' : 'Пользователь заблокирован', 'success');
        loadUsers();
    } catch (error) {
        showNotification('Ошибка', 'error');
    }
}

/**
 * Load all tasks
 */
async function loadAllTasks() {
    const tbody = document.getElementById('tasksTableBody');
    const status = document.getElementById('taskStatusFilter').value;
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Загрузка...</td></tr>';

    try {
        let url = '/admin/tasks?limit=50';
        if (status) url += `&status=${status}`;

        const data = await API.get(url);

        if (!data.tasks || !data.tasks.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Нет задач</td></tr>';
            return;
        }

        tbody.innerHTML = data.tasks.map(task => `
            <tr>
                <td>${task.id}</td>
                <td>${task.type || '-'}</td>
                <td>${task.user_id || '-'}</td>
                <td><span class="task-status ${task.status}">${task.status}</span></td>
                <td>${task.created_at ? formatDate(task.created_at) : '-'}</td>
                <td class="actions">
                    <button class="btn btn-ghost btn-sm" onclick="viewTask(${task.id})">👁️</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
    }
}

document.getElementById('taskStatusFilter')?.addEventListener('change', loadAllTasks);

/**
 * Load queue status
 */
async function loadQueueStatus() {
    const container = document.getElementById('queueInfo');
    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const data = await API.get('/admin/queue');

        container.innerHTML = `
            <div class="queue-stats">
                <div class="queue-stat">
                    <div class="queue-stat-value">${data.active || 0}</div>
                    <div class="queue-stat-label">Активных</div>
                </div>
                <div class="queue-stat">
                    <div class="queue-stat-value">${data.reserved || 0}</div>
                    <div class="queue-stat-label">Зарезервировано</div>
                </div>
                <div class="queue-stat">
                    <div class="queue-stat-value">${data.scheduled || 0}</div>
                    <div class="queue-stat-label">Запланировано</div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = '<div class="empty-state">Ошибка загрузки статуса очереди</div>';
    }
}

document.getElementById('refreshQueueBtn')?.addEventListener('click', loadQueueStatus);

/**
 * Load system metrics
 */
async function loadSystemMetrics() {
    const container = document.getElementById('systemMetrics');
    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const data = await API.get('/admin/metrics');

        container.innerHTML = `
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">Всего пользователей</div>
                    <div class="metric-value">${data.total_users || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Активных пользователей</div>
                    <div class="metric-value">${data.active_users || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Всего задач</div>
                    <div class="metric-value">${data.total_tasks || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Выполнено задач</div>
                    <div class="metric-value">${data.completed_tasks || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Всего файлов</div>
                    <div class="metric-value">${data.total_files || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Использовано хранилища</div>
                    <div class="metric-value">${formatFileSize(data.storage_used || 0)}</div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = '<div class="empty-state">Ошибка загрузки метрик</div>';
    }
}

/**
 * Cleanup
 */
document.getElementById('cleanupBtn')?.addEventListener('click', async () => {
    if (!confirm('Запустить очистку старых файлов?')) return;

    try {
        await API.post('/admin/cleanup');
        showNotification('Очистка запущена', 'success');
    } catch (error) {
        showNotification('Ошибка запуска очистки', 'error');
    }
});

/**
 * Modal management
 */
function initModals() {
    const modal = document.getElementById('createUserModal');

    document.getElementById('createUserBtn')?.addEventListener('click', () => modal.classList.add('open'));

    modal.querySelector('.modal-close')?.addEventListener('click', () => modal.classList.remove('open'));
    modal.querySelector('.modal-cancel')?.addEventListener('click', () => modal.classList.remove('open'));
    modal.querySelector('.modal-backdrop')?.addEventListener('click', () => modal.classList.remove('open'));

    document.getElementById('createUserForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const form = e.target;

        try {
            await API.post('/auth/register', {
                username: form.username.value,
                email: form.email.value,
                password: form.password.value
            });

            modal.classList.remove('open');
            form.reset();
            showNotification('Пользователь создан', 'success');
            loadUsers();
        } catch (error) {
            showNotification(error.message || 'Ошибка создания', 'error');
        }
    });
}

/**
 * Logout
 */
function initLogout() {
    document.getElementById('logoutBtn')?.addEventListener('click', () => Auth.logout());
}

function viewTask(taskId) {
    alert(`Задача #${taskId}\nПодробности будут добавлены позже.`);
}
