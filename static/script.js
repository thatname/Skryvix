document.addEventListener('DOMContentLoaded', () => {
    // --- Workspace Elements ---
    const workspaceList = document.getElementById('workspace-list');
    const createWorkspaceBtn = document.getElementById('create-workspace-btn');
    const workspaceCountInput = document.getElementById('workspace-count');
    const setWorkspaceCountBtn = document.getElementById('set-workspace-count-btn');

    const taskDescriptionInput = document.getElementById('task-description');
    const workerConfigSelect = document.getElementById('worker-config-select');
    const createTaskBtn = document.getElementById('create-task-btn');
    const pendingTasksList = document.getElementById('pending-tasks');
    const processingTasksList = document.getElementById('processing-tasks');
    const completeTasksList = document.getElementById('complete-tasks');

    let selectedTaskId = null; // Track which task's details are being viewed
    let tasksData = {}; // Store task data locally { 'uuid': { description: ..., history: ..., state: ... } }

    // --- WebSocket Setup ---
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    let socket;

    function connectWebSocket() {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('WebSocket connection established');
        };

        socket.onmessage = (event) => {
            console.log('WebSocket message received:', event.data);
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event.reason);
            // Attempt to reconnect after a delay
            setTimeout(connectWebSocket, 5000);
        };
    }

    function handleWebSocketMessage(message) {
        switch (message.type) {
            case 'workspaces_updated':
                fetchWorkspaces(); // Re-fetch and re-render the workspace list
                break;
            case 'task_created':
                // Add the new task to our local store and re-render
                tasksData[message.task.id] = message.task;
                renderTasks();
                break;
            case 'task_update':
                // Update task state in local store and UI
                if (tasksData[message.task_id]) {
                    Object.assign(tasksData[message.task_id], message.data); // Update changed properties
                    renderTasks(); // Re-render all task lists
                }
                break;
            case 'task_deleted':
                // Remove task from local store and UI
                if (tasksData[message.task_id]) {
                    delete tasksData[message.task_id];
                    renderTasks();
                    // If the deleted task was selected, clear selection
                    if (selectedTaskId === message.task_id) {
                        selectedTaskId = null;
                    }
                }
                break;
            default:
                console.log('Unknown WebSocket message type:', message.type);
        }
    }

    // --- API Helper ---
    async function apiRequest(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                console.error(`API Error (${response.status}): ${errorData.detail || response.statusText}`);
                alert(`Error: ${errorData.detail || response.statusText}`); // Simple user feedback
                return null;
            }
            // Handle cases with no content response (e.g., DELETE)
            if (response.status === 204 || response.headers.get('content-length') === '0') {
                return true; // Indicate success for no-content responses
            }
            return await response.json();
        } catch (error) {
            console.error('API Request failed:', error);
            alert('API Request failed. Check console for details.');
            return null;
        }
    }

    // --- Rendering Functions ---
    function renderWorkspaces(workspaces) {
        workspaceList.innerHTML = ''; // Clear existing list
        let currentCount = 0;
        workspaces.forEach(ws => {
            const li = document.createElement('li');
            const statusClass = ws.is_occupied ? 'status busy' : 'status';
            const statusText = ws.is_occupied ? `Busy (Task: ${ws.taskid})` : 'Idle';
            li.dataset.wsPath = `ws${ws.id}`; // Store workspace path
            li.style.cursor = 'pointer'; // Indicate clickable
            li.innerHTML = `
                <span>ID: ${ws.id}</span>
                <span class="${statusClass}">Status: ${statusText}</span>
                <button class="delete-ws-btn" data-ws-id="${ws.id}" ${ws.is_occupied ? 'disabled' : ''}>Delete</button>
            `;

            // Add event listener for the delete button
            li.querySelector('.delete-ws-btn').addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent li click event when deleting
                const wsId = e.target.getAttribute('data-ws-id');
                if (confirm(`Are you sure you want to delete workspace ${wsId}?`)) {
                    deleteWorkspace(wsId);
                }
            });

    // Add event listener for the workspace item itself
    li.addEventListener('click', (e) => {
        // Don't trigger if delete button was clicked
        if (e.target.tagName !== 'BUTTON') {
            const wsPath = e.currentTarget.dataset.wsPath;
            // Update the details iframe to show this workspace's folder
            document.getElementById('task-details-frame').src = `/static/folder.htm?subdir=${encodeURIComponent(wsPath)}`;
        }
    });
            workspaceList.appendChild(li);
            currentCount++;
        });
        workspaceCountInput.value = currentCount; // Update the count input
    }

    function renderTasks() {
        // Clear existing lists
        pendingTasksList.innerHTML = '';
        processingTasksList.innerHTML = '';
        completeTasksList.innerHTML = '';

        Object.entries(tasksData).forEach(([taskId, task]) => {
            const li = document.createElement('li');
            li.dataset.taskId = taskId; // Store task ID on the element
            li.style.cursor = 'pointer'; // Indicate it's clickable

            let buttons = '';
            let targetList;

            switch (task.state) {
                case 'pending':
                    buttons = `
                        <button class="start-task-btn">Start</button>
                        <button class="delete-task-btn">Delete</button>
                    `;
                    targetList = pendingTasksList;
                    break;
                case 'processing':
                    buttons = `<button class="stop-task-btn">Stop</button>`;
                    targetList = processingTasksList;
                    break;
                case 'complete':
                    buttons = `<button class="delete-task-btn">Delete</button>`;
                    targetList = completeTasksList;
                    break;
                default:
                    console.warn(`Unknown task state: ${task.state} for task ${taskId}`);
                    return; // Skip rendering unknown state tasks
            }

            li.innerHTML = `<span>Desc: ${escapeHtml(task.description)}</span> ${buttons}`;

            // Add click listener to show details
            li.addEventListener('click', (e) => {
                // Don't trigger details view if a button was clicked
                if (e.target.tagName !== 'BUTTON') {
                    selectTask(taskId);
                }
            });

            // Add button listeners
            const startBtn = li.querySelector('.start-task-btn');
            const stopBtn = li.querySelector('.stop-task-btn');
            const deleteBtn = li.querySelector('.delete-task-btn');

            if (startBtn) {
                startBtn.addEventListener('click', () => startTask(taskId));
            }
            if (stopBtn) {
                stopBtn.addEventListener('click', () => stopTask(taskId));
            }
            if (deleteBtn) {
                deleteBtn.addEventListener('click', () => deleteTask(taskId));
            }

            targetList.appendChild(li);
        });

        // Highlight selected task
        highlightSelectedTask();
    }

    function renderWorkerConfigs(configs) {
        workerConfigSelect.innerHTML = ''; // Clear existing options
        if (configs && configs.length > 0) {
            configs.forEach(configName => {
                const option = document.createElement('option');
                option.value = configName;
                option.textContent = configName;
                workerConfigSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.textContent = 'No worker configs found';
            option.disabled = true;
            workerConfigSelect.appendChild(option);
        }
    }

    function selectTask(taskId) {
        selectedTaskId = taskId;
        const iframe = document.getElementById('task-details-frame');
        iframe.src = `/static/task.html?task_id=${taskId}`;
        highlightSelectedTask();
    }

    function highlightSelectedTask() {
         document.querySelectorAll('#task-panel li').forEach(li => {
            if (li.dataset.taskId === selectedTaskId) {
                li.style.backgroundColor = '#e0e0e0'; // Highlight color
            } else {
                li.style.backgroundColor = '#f9f9f9'; // Default color
            }
        });
    }

    // --- Data Fetching Functions ---
    async function fetchWorkspaces() {
        const data = await apiRequest('/api/workspaces');
        if (data) {
            renderWorkspaces(data);
        }
    }

    async function fetchTasks() {
        const data = await apiRequest('/api/tasks');
        if (data) {
            // Reconstruct the flat tasksData dictionary
            tasksData = {};
            Object.values(data).flat().forEach(task => {
                tasksData[task.id] = task;
            });
            renderTasks();
            // If a task was selected, update the iframe
            if (selectedTaskId && tasksData[selectedTaskId]) {
                const iframe = document.getElementById('task-details-frame');
                iframe.src = `/task.html?task_id=${selectedTaskId}`;
            }
        }
    }

    async function fetchWorkerConfigs() {
        const data = await apiRequest('/api/worker_configs');
        if (data && data.configs) {
            renderWorkerConfigs(data.configs);
        }
    }

    // --- Action Functions ---
    async function createWorkspace() {
        await apiRequest('/api/workspaces', 'POST');
        // UI update will be handled by WebSocket message 'workspaces_updated'
    }

    async function setWorkspaceCount() {
        const count = parseInt(workspaceCountInput.value, 10);
        if (isNaN(count) || count < 0) {
            alert('Please enter a valid non-negative number for workspace count.');
            return;
        }
        await apiRequest('/api/workspaces/count', 'PUT', { count });
        // UI update handled by WebSocket
    }

    async function deleteWorkspace(wsId) {
        await apiRequest(`/api/workspaces/${wsId}`, 'DELETE');
        // UI update handled by WebSocket
    }

    async function createTask() {
        const description = taskDescriptionInput.value.trim();
        if (!description) {
            alert('Please enter a task description.');
            return;
        }
        const response = await apiRequest('/api/tasks', 'POST', { description });
        if (response) {
            taskDescriptionInput.value = ''; // Clear input on success
            // UI update handled by WebSocket 'task_created'
        }
    }

    async function startTask(taskId) {
        const selectedConfig = workerConfigSelect.value;
        if (!selectedConfig || workerConfigSelect.disabled) {
            alert('Please select a valid worker configuration.');
            return;
        }
        await apiRequest(`/api/tasks/${taskId}/start`, 'POST', { worker_config: selectedConfig });
        // Task state change and workspace update handled by WebSocket
    }

    async function stopTask(taskId) {
        await apiRequest(`/api/tasks/${taskId}/stop`, 'POST');
        // Task state change and workspace update handled by WebSocket
    }

    async function deleteTask(taskId) {
        if (confirm(`Are you sure you want to delete task ${taskId}?`)) {
            await apiRequest(`/api/tasks/${taskId}`, 'DELETE');
            // UI update handled by WebSocket 'task_deleted'
        }
    }

    // --- Utility ---
    function escapeHtml(unsafe) {
        if (unsafe === null || unsafe === undefined) return '';
        // Correctly escape HTML entities
        return unsafe
             .toString()
             .replace(/&/g, "&")
             .replace(/</g, "<")
             .replace(/>/g, ">")
             .replace(/"/g, "\"")
             .replace(/'/g, "&#039;");
    }


    // --- Initialization ---
    connectWebSocket();
    fetchWorkspaces();
    fetchTasks();
    fetchWorkerConfigs();

    // --- Event Listeners ---
    createWorkspaceBtn.addEventListener('click', createWorkspace);
    setWorkspaceCountBtn.addEventListener('click', setWorkspaceCount);
    createTaskBtn.addEventListener('click', createTask);

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    };

});
