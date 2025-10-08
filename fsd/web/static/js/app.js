// FSD Web Interface Application Logic

let currentFilter = 'all';
let allTasks = [];
let isInitialized = false;

// Utility Functions
async function fetchData(endpoint, timeout = 10000) {
    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(`/api${endpoint}`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            // Try to get error details from response
            let errorDetail = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorDetail = errorData.detail;
                }
            } catch (e) {
                // Response wasn't JSON, use status text
                errorDetail = `${response.status} ${response.statusText}`;
            }
            throw new Error(errorDetail);
        }
        
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            throw new Error('Request timed out - server may be slow or unresponsive');
        }
        throw error;
    }
}

function showError(message) {
    const errorContainer = document.getElementById('error-container');
    errorContainer.innerHTML = `<div class="error">⚠️ ${message}</div>`;
    setTimeout(() => {
        errorContainer.innerHTML = '';
    }, 5000);
}

function showSuccess(message) {
    const successContainer = document.getElementById('success-container');
    successContainer.innerHTML = `<div class="success-message">✓ ${message}</div>`;
    setTimeout(() => {
        successContainer.innerHTML = '';
    }, 5000);
}

function showInitSection() {
    document.getElementById('init-section').style.display = 'block';
    document.getElementById('main-content').style.display = 'none';
}

function hideInitSection() {
    document.getElementById('init-section').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';
}

// System Initialization
async function initializeFSD() {
    const initBtn = document.getElementById('init-btn');
    initBtn.disabled = true;
    initBtn.textContent = 'Initializing...';

    try {
        const response = await fetch('/api/init', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to initialize');
        }

        const result = await response.json();
        showSuccess(result.message);

        isInitialized = true;
        hideInitSection();

        // Refresh data after initialization
        await refreshData();

    } catch (error) {
        console.error('Failed to initialize:', error);
        showError(error.message || 'Failed to initialize FSD');
        initBtn.disabled = false;
        initBtn.textContent = 'Initialize FSD';
    }
}

// System Status
async function loadSystemStatus() {
    try {
        const status = await fetchData('/status');

        // Check if FSD is initialized
        isInitialized = status.fsd_initialized;

        if (!isInitialized) {
            showInitSection();
            return;
        } else {
            hideInitSection();
        }

        // Update status badges (both top and overview)
        const topBadge = document.getElementById('top-status-badge');
        const badge = document.getElementById('system-status-badge');
        
        const badgeHTML = status.execution_active
            ? '<span class="status-indicator" style="background: #f59e0b;"></span>Active'
            : '<span class="status-indicator" style="background: #10b981;"></span>Idle';
        
        const badgeClass = status.execution_active ? 'status-badge active' : 'status-badge idle';
        
        if (topBadge) {
            topBadge.className = badgeClass;
            topBadge.innerHTML = badgeHTML;
        }
        
        if (badge) {
            badge.className = badgeClass;
            badge.innerHTML = badgeHTML;
        }

        // Update stats
        const statsHtml = `
            <div class="stat">
                <span class="stat-label">FSD Initialized</span>
                <span class="stat-value">${status.fsd_initialized ? '✓ Yes' : '✗ No'}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Total Tasks</span>
                <span class="stat-value">${status.total_tasks}</span>
            </div>
        `;
        document.getElementById('system-stats').innerHTML = statsHtml;

        // Update queue stats
        const queueHtml = `
            <div class="stat">
                <span class="stat-label">Queued</span>
                <span class="stat-value queued">${status.task_counts.queued}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Running</span>
                <span class="stat-value running">${status.task_counts.running}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Completed</span>
                <span class="stat-value completed">${status.task_counts.completed}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Failed</span>
                <span class="stat-value failed">${status.task_counts.failed}</span>
            </div>
        `;
        document.getElementById('queue-stats').innerHTML = queueHtml;

    } catch (error) {
        console.error('Failed to load system status:', error);
        showError('Failed to load system status');
    }
}

// Task Management
async function loadTasks() {
    if (!isInitialized) return;

    try {
        // Show loading indicator
        document.getElementById('tasks-list').innerHTML = '<div class="loading">Loading tasks...</div>';
        
        allTasks = await fetchData('/tasks');
        
        // Check if we got valid data
        if (!Array.isArray(allTasks)) {
            throw new Error('Invalid response format');
        }
        
        renderTasks();
    } catch (error) {
        console.error('Failed to load tasks:', error);
        const errorMessage = error.message || 'Failed to load tasks';
        document.getElementById('tasks-list').innerHTML = `
            <div class="error">
                <strong>⚠️ Failed to load tasks</strong>
                <p style="margin-top: 8px; font-size: 13px;">${errorMessage}</p>
                <button class="refresh-btn" onclick="loadTasks()" style="margin-top: 12px; padding: 8px 16px;">
                    Retry
                </button>
            </div>
        `;
    }
}

function renderTasks() {
    const tasksList = document.getElementById('tasks-list');

    const filteredTasks = currentFilter === 'all'
        ? allTasks
        : allTasks.filter(task => task.status === currentFilter);

    if (filteredTasks.length === 0) {
        tasksList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No ${currentFilter === 'all' ? '' : currentFilter} tasks found</p>
            </div>
        `;
        return;
    }

    const tasksHtml = filteredTasks.map(task => {
        // Generate action buttons based on status
        let actions = '';
        if (task.status === 'queued') {
            actions = `
                <div class="task-item-actions">
                    <button class="task-item-btn btn-info" onclick="event.stopPropagation(); openTaskDetail('${task.id}')">
                        View Details
                    </button>
                    <button class="task-item-btn btn-warning" onclick="event.stopPropagation(); cancelTask('${task.id}')">
                        Cancel
                    </button>
                    <button class="task-item-btn btn-danger" onclick="event.stopPropagation(); deleteTask('${task.id}')">
                        Delete
                    </button>
                </div>
            `;
        } else if (task.status === 'running') {
            actions = `
                <div class="task-item-actions">
                    <button class="task-item-btn btn-info" onclick="event.stopPropagation(); openTaskDetail('${task.id}')">
                        View Details
                    </button>
                    <button class="task-item-btn btn-secondary" onclick="event.stopPropagation(); openLogsModal('${task.id}')">
                        📋 View Logs
                    </button>
                    <button class="task-item-btn btn-warning" onclick="event.stopPropagation(); cancelTask('${task.id}')">
                        Cancel
                    </button>
                </div>
            `;
        } else if (task.status === 'completed' || task.status === 'failed') {
            actions = `
                <div class="task-item-actions">
                    <button class="task-item-btn btn-info" onclick="event.stopPropagation(); openTaskDetail('${task.id}')">
                        View Details
                    </button>
                    <button class="task-item-btn btn-secondary" onclick="event.stopPropagation(); openLogsModal('${task.id}')">
                        📋 View Logs
                    </button>
                    <button class="task-item-btn btn-success" onclick="event.stopPropagation(); requeueTask('${task.id}')">
                        Re-queue
                    </button>
                    <button class="task-item-btn btn-danger" onclick="event.stopPropagation(); deleteTask('${task.id}')">
                        Delete
                    </button>
                </div>
            `;
        }

        return `
            <div class="task-item">
                <div class="task-item-content" onclick="openTaskDetail('${task.id}')">
                    <div class="task-header">
                        <span class="task-id">${task.id}</span>
                        <div class="task-badges">
                            <span class="badge priority-${task.priority}">${task.priority.toUpperCase()}</span>
                            <span class="badge status-${task.status}">${task.status.toUpperCase()}</span>
                        </div>
                    </div>
                    <div class="task-description">${task.description}</div>
                    <div class="task-meta">
                        <span>⏱️ ${task.estimated_duration}</span>
                        ${task.focus_files ? `<span>📁 ${task.focus_files.length} file(s)</span>` : ''}
                    </div>
                </div>
                ${actions}
            </div>
        `;
    }).join('');

    tasksList.innerHTML = `<div class="task-list">${tasksHtml}</div>`;
}

function filterTasks(filter) {
    currentFilter = filter;

    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        }
    });

    renderTasks();
}

// Activity Logs
async function loadActivity() {
    if (!isInitialized) return;

    try {
        const activity = await fetchData('/activity?limit=20');

        if (activity.length === 0) {
            document.getElementById('activity-list').innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📊</div>
                    <p>No recent activity</p>
                </div>
            `;
            return;
        }

        const activityHtml = activity.map(event => {
            const date = new Date(event.timestamp);
            const timeStr = date.toLocaleString();

            return `
                <div class="activity-item">
                    <div class="activity-time">${timeStr}</div>
                    <div class="activity-message">${event.message}</div>
                </div>
            `;
        }).join('');

        document.getElementById('activity-list').innerHTML = `<div class="activity-list">${activityHtml}</div>`;

    } catch (error) {
        console.error('Failed to load activity:', error);
        document.getElementById('activity-list').innerHTML = '<div class="error">Failed to load activity</div>';
    }
}

async function loadCompletedTasks() {
    try {
        const response = await fetch('/api/tasks/completed/recent?limit=5');
        if (!response.ok) {
            throw new Error('Failed to fetch completed tasks');
        }

        const tasks = await response.json();
        const container = document.getElementById('completed-tasks-list');

        if (tasks.length === 0) {
            container.innerHTML = '<div style="padding: 16px; text-align: center; color: #6b7280;">No completed tasks yet</div>';
            return;
        }

        // Helper function to format duration
        function formatDuration(seconds) {
            if (!seconds) return 'N/A';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        }

        // Helper function to format timestamp
        function formatTimestamp(isoString) {
            if (!isoString) return 'N/A';
            const date = new Date(isoString);
            const now = new Date();
            const diff = now - date;
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(hours / 24);

            if (days > 0) return `${days}d ago`;
            if (hours > 0) return `${hours}h ago`;
            return 'Just now';
        }

        // Render completed tasks as cards
        container.innerHTML = tasks.map(task => {
            const statusColor = task.status === 'completed' ? '#10b981' : '#ef4444';
            const statusIcon = task.status === 'completed' ? '✓' : '✗';
            const priorityColors = {
                'critical': '#dc2626',
                'high': '#f59e0b',
                'medium': '#3b82f6',
                'low': '#6b7280'
            };

            return `
                <div class="card" style="margin-bottom: 12px; border-left: 4px solid ${statusColor};">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <span style="font-size: 20px;">${statusIcon}</span>
                                <strong style="font-size: 16px;">${task.id}</strong>
                                <span class="status-badge" style="background: ${priorityColors[task.priority]};">
                                    ${task.priority}
                                </span>
                            </div>
                            <div style="color: #6b7280; font-size: 14px; margin-bottom: 8px;">
                                ${task.description}
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 16px; font-size: 13px; color: #6b7280;">
                        <div>
                            <strong>Completed:</strong> ${formatTimestamp(task.completed_at)}
                        </div>
                        <div>
                            <strong>Duration:</strong> ${formatDuration(task.duration_seconds)}
                        </div>
                        ${task.retry_count > 0 ? `
                            <div>
                                <strong>Retries:</strong> ${task.retry_count}
                            </div>
                        ` : ''}
                        ${task.error_message ? `
                            <div style="color: #ef4444;">
                                <strong>Error:</strong> ${task.error_message.substring(0, 50)}...
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Failed to load completed tasks:', error);
        const errorMsg = error.message || 'Unknown error';
        document.getElementById('completed-tasks-list').innerHTML =
            `<div class="error">Failed to load completed tasks: ${errorMsg}</div>`;
    }
}

async function refreshData() {
    try {
        // Run all loads in parallel, but don't fail if one fails
        await Promise.allSettled([
            loadSystemStatus(),
            loadTasks(),
            loadActivity(),
            loadCompletedTasks()
        ]);
    } catch (error) {
        console.error('Error during refresh:', error);
        // Don't show error to user - individual functions will handle their own errors
    }
}

// Modal Functions
function openTaskModal() {
    if (!isInitialized) {
        showError('Please initialize FSD first');
        return;
    }
    document.getElementById('task-modal').classList.add('active');
}

function closeTaskModal() {
    document.getElementById('task-modal').classList.remove('active');
    // Reset forms
    document.getElementById('natural-form').reset();
    document.getElementById('structured-form').reset();
}

function closeModalOnOverlay(event) {
    if (event.target.classList.contains('modal-overlay')) {
        closeTaskModal();
    }
}

function switchTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    if (tab === 'natural') {
        document.getElementById('natural-tab').classList.add('active');
    } else {
        document.getElementById('structured-tab').classList.add('active');
    }
}

// Main Tab Switching
function switchMainTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.main-tab').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.main-tab-content').forEach(content => {
        content.classList.remove('active');
    });

    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) {
        targetTab.classList.add('active');
    }
}

// Task Creation
async function submitNaturalTask(event) {
    event.preventDefault();

    const submitBtn = document.getElementById('natural-submit');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating...';

    try {
        const text = document.getElementById('natural-text').value;

        const response = await fetch('/api/tasks/natural', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create task');
        }

        const result = await response.json();
        showSuccess(result.message);
        closeTaskModal();

        // Refresh data
        await refreshData();

    } catch (error) {
        console.error('Failed to create task:', error);
        showError(error.message || 'Failed to create task');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

async function submitStructuredTask(event) {
    event.preventDefault();

    const submitBtn = document.getElementById('structured-submit');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating...';

    try {
        const focusFilesInput = document.getElementById('task-focus-files').value;
        const focusFiles = focusFilesInput
            ? focusFilesInput.split(',').map(f => f.trim()).filter(f => f)
            : null;

        const createPr = document.getElementById('task-create-pr').checked;
        const prTitle = createPr ? document.getElementById('task-pr-title').value : null;

        const taskData = {
            id: document.getElementById('task-id').value,
            description: document.getElementById('task-description').value,
            priority: document.getElementById('task-priority').value,
            estimated_duration: document.getElementById('task-duration').value,
            context: document.getElementById('task-context').value || null,
            focus_files: focusFiles,
            success_criteria: document.getElementById('task-success').value || null,
            create_pr: createPr,
            pr_title: prTitle,
            notify_slack: false,
        };

        const response = await fetch('/api/tasks/structured', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create task');
        }

        const result = await response.json();
        showSuccess(result.message);
        closeTaskModal();

        // Refresh data
        await refreshData();

    } catch (error) {
        console.error('Failed to create task:', error);
        showError(error.message || 'Failed to create task');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Task Detail View
async function openTaskDetail(taskId) {
    const modal = document.getElementById('task-detail-modal');
    const content = document.getElementById('task-detail-content');
    
    // Show modal with loading state
    modal.classList.add('active');
    content.innerHTML = '<div class="loading">Loading task details...</div>';
    
    try {
        // Fetch task details
        const task = await fetchData(`/tasks/${taskId}`);
        
        // Render task details
        renderTaskDetail(task);
    } catch (error) {
        console.error('Failed to load task details:', error);
        content.innerHTML = `
            <div class="error">
                <strong>⚠️ Failed to load task details</strong>
                <p style="margin-top: 8px; font-size: 13px;">${error.message || 'Unknown error'}</p>
                <button class="refresh-btn" onclick="openTaskDetail('${taskId}')" style="margin-top: 12px; padding: 8px 16px;">
                    Retry
                </button>
            </div>
        `;
    }
}

function renderTaskDetail(task) {
    const content = document.getElementById('task-detail-content');
    
    // Build HTML
    let html = `
        <!-- Task Header -->
        <div class="detail-section">
            <div class="detail-badges">
                <span class="badge priority-${task.priority}">${task.priority.toUpperCase()}</span>
                <span class="badge status-${task.status}">${task.status.toUpperCase()}</span>
            </div>
        </div>

        <!-- Task ID -->
        <div class="detail-section">
            <div class="detail-label">Task ID</div>
            <div class="detail-value">
                <code style="background: #f9fafb; padding: 4px 8px; border-radius: 4px; font-size: 13px;">${task.id}</code>
            </div>
        </div>

        <!-- Description -->
        <div class="detail-section">
            <div class="detail-label">Description</div>
            <div class="detail-value">${task.description || '<span class="detail-empty">No description</span>'}</div>
        </div>

        <!-- Duration -->
        <div class="detail-section">
            <div class="detail-label">Estimated Duration</div>
            <div class="detail-value">⏱️ ${task.estimated_duration}</div>
        </div>
    `;

    // Context (optional)
    if (task.context) {
        html += `
            <div class="detail-section">
                <div class="detail-label">Context</div>
                <div class="detail-value">
                    <pre>${task.context}</pre>
                </div>
            </div>
        `;
    }

    // Focus Files (optional)
    if (task.focus_files && task.focus_files.length > 0) {
        html += `
            <div class="detail-section">
                <div class="detail-label">Focus Files (${task.focus_files.length})</div>
                <div class="detail-file-list">
                    ${task.focus_files.map(file => `<div class="detail-file-item">${file}</div>`).join('')}
                </div>
            </div>
        `;
    }

    // Success Criteria (optional)
    if (task.success_criteria) {
        html += `
            <div class="detail-section">
                <div class="detail-label">Success Criteria</div>
                <div class="detail-value">
                    <pre>${task.success_criteria}</pre>
                </div>
            </div>
        `;
    }

    // Add action buttons based on status
    html += '<div class="task-actions">';

    if (task.status === 'queued') {
        html += `
            <button class="btn btn-warning" onclick="cancelTask('${task.id}')">
                Cancel Task
            </button>
            <button class="btn btn-danger" onclick="deleteTask('${task.id}')">
                Remove from Queue
            </button>
        `;
    } else if (task.status === 'running') {
        html += `
            <button class="btn btn-secondary" onclick="closeTaskDetailModal(); openLogsModal('${task.id}')">
                📋 View Logs
            </button>
            <button class="btn btn-warning" onclick="cancelTask('${task.id}')">
                Cancel Execution
            </button>
        `;
    } else if (task.status === 'completed' || task.status === 'failed') {
        html += `
            <button class="btn btn-secondary" onclick="closeTaskDetailModal(); openLogsModal('${task.id}')">
                📋 View Logs
            </button>
            <button class="btn btn-info" onclick="requeueTask('${task.id}')">
                Re-queue Task
            </button>
            <button class="btn btn-danger" onclick="deleteTask('${task.id}')">
                Remove from Queue
            </button>
        `;
    }

    html += '</div>';

    content.innerHTML = html;
}

function closeTaskDetailModal(event) {
    // Close if clicking overlay or calling function directly
    if (!event || event.target.classList.contains('modal-overlay')) {
        document.getElementById('task-detail-modal').classList.remove('active');
    }
}

// Task Actions
async function deleteTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete task');
        }

        const result = await response.json();
        showSuccess(result.message);

        // Close modal and refresh
        closeTaskDetailModal();
        await refreshData();

    } catch (error) {
        console.error('Failed to delete task:', error);
        showError(error.message || 'Failed to delete task');
    }
}

async function cancelTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/cancel`, {
            method: 'POST',
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to cancel task');
        }

        const result = await response.json();
        showSuccess(result.message);

        // Close modal and refresh
        closeTaskDetailModal();
        await refreshData();

    } catch (error) {
        console.error('Failed to cancel task:', error);
        showError(error.message || 'Failed to cancel task');
    }
}

async function requeueTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status?new_status=queued`, {
            method: 'PATCH',
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to re-queue task');
        }

        const result = await response.json();
        showSuccess(result.message);

        // Refresh task detail view
        await openTaskDetail(taskId);
        await refreshData();

    } catch (error) {
        console.error('Failed to re-queue task:', error);
        showError(error.message || 'Failed to re-queue task');
    }
}

async function bulkDeleteTasks() {
    const completedCount = allTasks.filter(t => t.status === 'completed').length;
    const failedCount = allTasks.filter(t => t.status === 'failed').length;
    const totalCount = completedCount + failedCount;

    if (totalCount === 0) {
        showError('No completed or failed tasks to delete');
        return;
    }

    try {
        // Delete completed tasks
        if (completedCount > 0) {
            const response1 = await fetch('/api/tasks/bulk-delete?status_filter=completed', {
                method: 'POST',
            });

            if (!response1.ok) {
                const error = await response1.json();
                throw new Error(error.detail || 'Failed to delete completed tasks');
            }
        }

        // Delete failed tasks
        if (failedCount > 0) {
            const response2 = await fetch('/api/tasks/bulk-delete?status_filter=failed', {
                method: 'POST',
            });

            if (!response2.ok) {
                const error = await response2.json();
                throw new Error(error.detail || 'Failed to delete failed tasks');
            }
        }

        showSuccess(`Successfully deleted ${totalCount} task(s)`);
        await refreshData();

    } catch (error) {
        console.error('Failed to bulk delete tasks:', error);
        showError(error.message || 'Failed to bulk delete tasks');
    }
}

// Execution Control
async function openExecutionModal() {
    if (!isInitialized) {
        showError('Please initialize FSD first');
        return;
    }

    // Directly start execution in autonomous mode without asking
    try {
        const response = await fetch('/api/execution/start?mode=autonomous', {
            method: 'POST',
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start execution');
        }

        const result = await response.json();

        // Show success message with note if present
        let message = result.message;
        if (result.note) {
            message += ` (${result.note})`;
        }
        showSuccess(message);

        // Refresh data after a short delay to allow execution to start
        setTimeout(() => refreshData(), 1000);

    } catch (error) {
        console.error('Failed to start execution:', error);
        showError(error.message || 'Failed to start execution');
    }
}

// Execution modal functions removed - execution now starts directly

async function stopExecution() {
    if (!isInitialized) {
        showError('FSD not initialized');
        return;
    }
    
    if (!confirm('Are you sure you want to stop task execution?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/execution/stop', {
            method: 'POST',
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to stop execution');
        }
        
        const result = await response.json();
        showSuccess(result.message);
        
        // Refresh data
        await refreshData();
        
    } catch (error) {
        console.error('Failed to stop execution:', error);
        showError(error.message || 'Failed to stop execution');
    }
}

// Log Viewing
let currentLogTaskId = null;
let logStreamEventSource = null;

async function loadSystemLogs() {
    if (!isInitialized) return;
    
    try {
        const levelFilter = document.getElementById('log-level-filter').value;
        const params = new URLSearchParams({ lines: 200 });
        if (levelFilter) {
            params.append('level', levelFilter);
        }
        
        const data = await fetchData(`/logs?${params}`);
        
        const container = document.getElementById('logs-container');
        
        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div style="color: #9ca3af;">No logs available</div>';
            return;
        }
        
        // Render logs
        const logsHtml = data.logs.map(entry => formatLogEntry(entry)).join('');
        container.innerHTML = logsHtml;
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
        
    } catch (error) {
        console.error('Failed to load system logs:', error);
        document.getElementById('logs-container').innerHTML = `<div style="color: #ef4444;">Failed to load logs: ${error.message}</div>`;
    }
}

function filterLogs() {
    loadSystemLogs();
}

function openLogsModal(taskId) {
    if (!isInitialized) {
        showError('FSD not initialized');
        return;
    }
    
    currentLogTaskId = taskId;
    
    const modal = document.getElementById('logs-modal');
    document.getElementById('logs-modal-task-id').textContent = taskId;
    document.getElementById('logs-follow-mode').checked = false;
    document.getElementById('logs-modal-level-filter').value = '';
    
    modal.classList.add('active');
    
    // Load logs
    reloadTaskLogs();
}

function closeLogsModal(event) {
    if (!event || event.target.classList.contains('modal-overlay')) {
        // Stop streaming if active
        if (logStreamEventSource) {
            logStreamEventSource.close();
            logStreamEventSource = null;
        }
        
        document.getElementById('logs-modal').classList.remove('active');
        currentLogTaskId = null;
    }
}

async function reloadTaskLogs() {
    if (!currentLogTaskId) return;
    
    try {
        const levelFilter = document.getElementById('logs-modal-level-filter').value;
        const params = new URLSearchParams({ lines: 200 });
        if (levelFilter) {
            params.append('level', levelFilter);
        }
        
        const data = await fetchData(`/logs/${currentLogTaskId}?${params}`);
        
        const container = document.getElementById('logs-modal-container');
        
        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div style="color: #9ca3af;">No logs available for this task</div>';
            return;
        }
        
        // Render logs
        const logsHtml = data.logs.map(entry => formatLogEntry(entry)).join('');
        container.innerHTML = logsHtml;
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
        
    } catch (error) {
        console.error('Failed to load task logs:', error);
        document.getElementById('logs-modal-container').innerHTML = `<div style="color: #ef4444;">Failed to load logs: ${error.message}</div>`;
    }
}

function toggleFollowMode() {
    const followMode = document.getElementById('logs-follow-mode').checked;
    
    if (followMode) {
        startLogStreaming();
    } else {
        stopLogStreaming();
    }
}

function startLogStreaming() {
    if (!currentLogTaskId) return;
    
    // Stop existing stream if any
    stopLogStreaming();
    
    const levelFilter = document.getElementById('logs-modal-level-filter').value;
    const params = new URLSearchParams();
    if (levelFilter) {
        params.append('level', levelFilter);
    }
    
    const url = `/api/logs/${currentLogTaskId}/stream?${params}`;
    
    logStreamEventSource = new EventSource(url);
    
    logStreamEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'log') {
                // Append new log entry
                const container = document.getElementById('logs-modal-container');
                const logHtml = formatLogEntry(data.entry);
                container.insertAdjacentHTML('beforeend', logHtml);
                
                // Auto-scroll to bottom
                container.scrollTop = container.scrollHeight;
            } else if (data.type === 'connected') {
                console.log('Connected to log stream for task:', data.task_id);
            }
        } catch (error) {
            console.error('Error parsing log stream data:', error);
        }
    };
    
    logStreamEventSource.onerror = function(error) {
        console.error('Log stream error:', error);
        stopLogStreaming();
        showError('Lost connection to log stream');
        document.getElementById('logs-follow-mode').checked = false;
    };
}

function stopLogStreaming() {
    if (logStreamEventSource) {
        logStreamEventSource.close();
        logStreamEventSource = null;
    }
}

function formatLogEntry(entry) {
    if (entry.raw) {
        return `<div style="color: #d4d4d4; margin-bottom: 4px;">${escapeHtml(entry.message)}</div>`;
    }
    
    // Format timestamp
    let timeStr = '';
    if (entry.timestamp && entry.timestamp !== 'unknown') {
        const timestamp = entry.timestamp.includes('T') ? entry.timestamp.split('T')[1].split('.')[0] : entry.timestamp;
        timeStr = `<span style="color: #6b7280;">[${timestamp}]</span> `;
    }
    
    // Color code by level
    const levelColors = {
        'DEBUG': '#9ca3af',
        'INFO': '#3b82f6',
        'WARN': '#f59e0b',
        'ERROR': '#ef4444'
    };
    
    const levelColor = levelColors[entry.level] || '#d4d4d4';
    const levelStr = `<span style="color: ${levelColor}; font-weight: 600;">[${entry.level}]</span>`;
    
    // Format message
    const message = escapeHtml(entry.message || '');
    
    // Build additional fields
    let extras = '';
    if (entry.task_id) {
        extras += ` <span style="color: #8b5cf6;">[Task: ${entry.task_id}]</span>`;
    }
    if (entry.error) {
        extras += `\n  <span style="color: #ef4444;">Error: ${escapeHtml(entry.error)}</span>`;
    }
    
    return `<div style="margin-bottom: 6px; line-height: 1.5;">${timeStr}${levelStr} ${message}${extras}</div>`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize Application
document.addEventListener('DOMContentLoaded', function() {
    // Initial load
    refreshData();
    loadSystemLogs();

    // Auto-refresh every 5 seconds (only if initialized)
    setInterval(() => {
        if (isInitialized) {
            refreshData();
            // Only refresh logs if not in follow mode
            if (!document.getElementById('logs-follow-mode') || !document.getElementById('logs-follow-mode').checked) {
                loadSystemLogs();
            }
        } else {
            // Just check system status to detect if initialized
            loadSystemStatus();
        }
    }, 5000);

    // Toggle PR title field visibility
    const createPrCheckbox = document.getElementById('task-create-pr');
    if (createPrCheckbox) {
        createPrCheckbox.addEventListener('change', function(e) {
            document.getElementById('pr-title-group').style.display = e.target.checked ? 'block' : 'none';
        });
    }
});

