// --- DOM Elements ---
const agentList = document.getElementById('agentList');
const newTasksList = document.getElementById('newTasks');
const runningTasksList = document.getElementById('runningTasks');
const incompleteTasksList = document.getElementById('incompleteTasks'); // Added
const completedTasksList = document.getElementById('completedTasks');
const createAgentBtn = document.getElementById('createAgent');
const addTaskBtn = document.getElementById('addTask');
const autoModeSwitch = document.getElementById('autoModeSwitch'); // Added
const taskDescInput = document.getElementById('taskDesc');
const progressPanel = document.getElementById('progressPanel');
const progressTaskId = document.getElementById('progressTaskId');
const progressContent = document.getElementById('progressContent');
const closeProgressPanel = document.getElementById('closeProgressPanel');
const toggleLayoutBtn = document.getElementById('toggleLayout'); // Added
const mainContainer = document.getElementById('mainContainer'); // Added

// --- Global State ---
let currentAssignmentMode = 'auto'; // Default, will be updated by server
let currentAgents = {};
let currentTasks = {};
let ws = null;

// --- WebSocket Setup ---
const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${location.host}/ws/ui`;

function connectWebSocket() {
    ws = new WebSocket(wsUrl);
    console.log(`Attempting to connect to ${wsUrl}`);

    ws.onopen = function(event) {
        console.log("UI WebSocket connected");
        // Clear any previous error messages
        agentList.innerHTML = '';
        newTasksList.innerHTML = '';
        runningTasksList.innerHTML = '';
        completedTasksList.innerHTML = '';
    };

    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log("Received message:", data);
            if (data.type === 'state') {
                // Store state globally before updating UI
                currentAgents = data.agents || {};
                currentTasks = data.tasks || {};
                currentAssignmentMode = data.mode || 'auto'; // Update mode from state
                document.getElementById('autoModeSwitch').checked = (currentAssignmentMode === 'auto');
                updateUI(); // Call without args, uses global state
            } else if (data.type === 'mode_update') { // Handle mode updates separately
                currentAssignmentMode = data.mode;
                document.getElementById('autoModeSwitch').checked = (currentAssignmentMode === 'auto');
                updateUI(); // Re-render UI based on new mode
            } else if (data.type === 'task_progress_full') {
                updateProgressPanelFull(data.payload);
            } else if (data.type === 'task_progress_delta') {
                updateProgressPanelDelta(data.payload);
            } else if (data.type === 'error') { // Handle potential errors from server
                console.error("Server error:", data.payload.message);
                // Optionally display error to user, e.g., in the progress panel
                if (progressPanel.style.display === 'block') {
                    progressContent.textContent = `Error: ${data.payload.message}`;
                }
            } else {
                console.warn("Received unknown message type:", data.type);
            }
        } catch (e) {
            console.error("Failed to parse message or update UI:", e);
            console.error("Received data:", event.data);
        }
    };

    ws.onerror = function(event) {
        console.error("UI WebSocket error:", event);
        // Display error in UI
        agentList.innerHTML = '<li>WebSocket error. Check console.</li>';
    };

    ws.onclose = function(event) {
        console.log("UI WebSocket closed:", event);
        agentList.innerHTML = '<li>Connection lost. Attempting to reconnect...</li>';
        // Attempt to reconnect after a delay
        setTimeout(connectWebSocket, 5000); // Reconnect after 5 seconds
    };
}

// --- UI Update Logic ---
// Now uses global state: currentAgents, currentTasks, currentAssignmentMode
function updateUI() {
    // Update Agents
    agentList.innerHTML = ''; // Clear previous list
    const agentIds = Object.keys(currentAgents).sort(); // Sort for consistent order

    if (agentIds.length === 0) {
        agentList.innerHTML = '<li>No active agents.</li>';
    } else {
        agentIds.forEach(agentId => {
            const agent = currentAgents[agentId]; // Use global state
            const li = document.createElement('li');
            const status = agent.status || 'unknown';
            li.className = `status-${status}`; // Use normalized status

            // Agent Info Span
            const infoSpan = document.createElement('span');
            infoSpan.textContent = `Agent ${agentId.substring(0, 8)} (${status})`;
            li.appendChild(infoSpan);

            // Action Buttons based on NEW state machine
            if (['created', 'stopped', 'error'].includes(status)) {
                // Can Start from these states
                const startBtn = document.createElement('button');
                startBtn.textContent = 'Start';
                startBtn.onclick = (e) => { e.stopPropagation(); startAgent(agentId); };
                li.appendChild(startBtn);
            } else if (['idle', 'busy'].includes(status)) {
                // Can Stop from these states
                const stopBtn = document.createElement('button');
                stopBtn.textContent = 'Stop';
                stopBtn.onclick = (e) => { e.stopPropagation(); stopAgent(agentId); };
                li.appendChild(stopBtn);
            }
            // Starting and Stopping are transient, no user actions needed

            // Can always Terminate (unless already terminating)
            if (status !== 'terminating') {
                const terminateBtn = document.createElement('button');
                terminateBtn.textContent = 'Terminate';
                terminateBtn.onclick = (e) => { e.stopPropagation(); terminateAgent(agentId); };
                li.appendChild(terminateBtn);
            }
            agentList.appendChild(li);
        });
    }


    // Update Tasks
    newTasksList.innerHTML = '';
    runningTasksList.innerHTML = '';
    incompleteTasksList.innerHTML = ''; // Clear new list
    completedTasksList.innerHTML = '';
    const taskIds = Object.keys(currentTasks).sort((a, b) => currentTasks[a].id.localeCompare(currentTasks[b].id)); // Sort by ID

    let hasNew = false, hasRunning = false, hasIncomplete = false, hasCompleted = false; // Added hasIncomplete

    taskIds.forEach(taskId => {
        const task = currentTasks[taskId]; // Use global state
        const li = document.createElement('li');
        li.className = `status-${task.status || 'unknown'}`;

        // Task Info Span
        const infoSpan = document.createElement('span');
        let text = `Task ${taskId.substring(0, 8)}: ${task.description || 'No description'}`;
        if (task.status === 'running') {
            text += ` (Agent: ${task.assigned_agent_id ? task.assigned_agent_id.substring(0, 8) : 'N/A'})`;
        } else if (task.status === 'completed') { // Only show result for completed
            let resultText = 'N/A';
            if (task.result !== null && task.result !== undefined) {
                 try {
                    // Attempt to stringify; limit length
                    resultText = JSON.stringify(task.result);
                    if (resultText.length > 100) {
                         resultText = resultText.substring(0, 100) + '...';
                    }
                } catch (e) {
                    resultText = String(task.result).substring(0, 100) + '...'; // Fallback
                }
            }
             text += ` (Result: ${resultText})`;
        }
        infoSpan.textContent = text;
        li.appendChild(infoSpan);

        // Add click handler to show progress
        infoSpan.style.cursor = 'pointer'; // Indicate it's clickable
        infoSpan.onclick = () => requestTaskProgress(taskId);

        // Add Delete Button to ALL tasks
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.style.marginLeft = '10px';
        deleteBtn.onclick = (e) => { e.stopPropagation(); deleteTask(taskId); };
        li.appendChild(deleteBtn);

        // Add Manual Assignment Controls (if applicable)
        if (currentAssignmentMode === 'manual' && (task.status === 'new' || task.status === 'incomplete')) {
            const assignDiv = document.createElement('div');
            assignDiv.style.display = 'inline-block'; // Keep controls on same line
            assignDiv.style.marginLeft = '10px';

            const select = document.createElement('select');
            select.id = `assign-select-${taskId}`;
            let hasIdleAgents = false;
            Object.values(currentAgents).forEach(agent => {
                if (agent.status === 'idle') {
                    const option = document.createElement('option');
                    option.value = agent.id;
                    option.textContent = `Agent ${agent.id.substring(0, 8)}`;
                    select.appendChild(option);
                    hasIdleAgents = true;
                }
            });

            if (!hasIdleAgents) {
                const option = document.createElement('option');
                option.textContent = 'No idle agents';
                option.disabled = true;
                select.appendChild(option);
            }

            const assignBtn = document.createElement('button');
            assignBtn.textContent = 'Assign';
            assignBtn.disabled = !hasIdleAgents;
            assignBtn.onclick = (e) => {
                e.stopPropagation();
                const selectedAgentId = select.value;
                // Check if a valid, non-disabled agent is selected
                if (selectedAgentId && !select.options[select.selectedIndex].disabled) {
                    manualAssignTask(taskId, selectedAgentId);
                }
            };

            assignDiv.appendChild(select);
            assignDiv.appendChild(assignBtn);
            li.appendChild(assignDiv);
        }


        // Append task to the correct list
        if (task.status === 'new') {
            newTasksList.appendChild(li);
            hasNew = true;
        } else if (task.status === 'running') {
            runningTasksList.appendChild(li);
            hasRunning = true;
        } else if (task.status === 'incomplete') { // Added case
            incompleteTasksList.appendChild(li);
            hasIncomplete = true;
        } else { // completed
            completedTasksList.appendChild(li);
            hasCompleted = true;
        }
    });

    // Add placeholder if lists are empty
    if (!hasNew) newTasksList.innerHTML = '<li>No new tasks.</li>';
    if (!hasRunning) runningTasksList.innerHTML = '<li>No tasks running.</li>';
    if (!hasIncomplete) incompleteTasksList.innerHTML = '<li>No incomplete tasks.</li>'; // Added
    if (!hasCompleted) completedTasksList.innerHTML = '<li>No completed tasks.</li>';
}

async function loadConfigs() {
    const response = await fetch('/get_configs');
    const data = await response.json();
    const select = document.getElementById('config-select');
    select.innerHTML = '';
    data.configs.forEach(config => {
        const option = document.createElement('option');
        option.value = config;
        option.textContent = config;
        select.appendChild(option);
    });
}

window.onload = async () => {
    await loadConfigs();
    connectWebSocket(); // Connect WebSocket after initial setup
};

// --- Event Handlers ---
// Add listener for the mode switch
autoModeSwitch.onchange = () => {
    const mode = autoModeSwitch.checked ? 'auto' : 'manual';
    console.log(`Setting assignment mode to: ${mode}`);
    sendWsCommand({ command: 'set_assignment_mode', payload: { mode: mode } });
};

createAgentBtn.onclick = () => {
    const config = document.getElementById('config-select').value;
    console.log("Requesting agent creation with config:", config);
    sendWsCommand({ command: 'create_agent', payload: { config: config } });
};

function startAgent(agentId) {
    console.log("Requesting start for agent:", agentId);
    sendWsCommand({ command: 'start_agent', payload: { agent_id: agentId } });
}

function stopAgent(agentId) {
    console.log("Requesting stop for agent:", agentId);
    sendWsCommand({ command: 'stop_agent', payload: { agent_id: agentId } });
}

addTaskBtn.onclick = () => {
    const description = taskDescInput.value.trim();
    if (description) {
        console.log("Adding task:", description);
        sendWsCommand({ command: 'add_task', payload: { description: description } });
        taskDescInput.value = ''; // Clear input after sending
    } else {
        alert("Please enter a task description.");
    }
};

function terminateAgent(agentId) {
     console.log("Requesting termination for agent:", agentId);
     sendWsCommand({ command: 'terminate_agent', payload: { agent_id: agentId } });
}

function deleteTask(taskId) {
    // Use confirm dialog
    if (confirm(`Are you sure you want to delete task ${taskId.substring(0,8)}? This cannot be undone.`)) {
        console.log("Requesting deletion for task:", taskId);
        sendWsCommand({ command: 'delete_task', payload: { task_id: taskId } });
    }
}

function manualAssignTask(taskId, agentId) {
     console.log(`Requesting manual assignment of task ${taskId.substring(0,8)} to agent ${agentId.substring(0,8)}`);
     sendWsCommand({ command: 'manual_assign_task', payload: { task_id: taskId, agent_id: agentId } });
}

// --- Helper to Send Commands ---
function sendWsCommand(commandData) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(commandData));
    } else {
         console.error("WebSocket not connected. Cannot send command:", commandData);
    alert("WebSocket connection is not open. Please wait or refresh.");
    }
}

// --- Progress Panel Logic ---
function requestTaskProgress(taskId) {
    console.log(`Requesting progress for task: ${taskId}`);
    progressPanel.style.display = 'block'; // Show the panel
    progressTaskId.textContent = `Task ID: ${taskId.substring(0, 8)}`; // Display truncated ID
    progressContent.textContent = 'Loading...'; // Set loading state
    sendWsCommand({ command: 'get_progress', payload: { task_id: taskId } });
}

function updateProgressPanelFull(payload) {
    const receivedTaskId = payload.task_id;
    const history = payload.history;
    // Check if the received progress corresponds to the currently displayed task ID
    const displayedTaskIdShort = progressTaskId.textContent.replace('Task ID: ', '');
    if (receivedTaskId.startsWith(displayedTaskIdShort)) { // Compare with truncated ID
         progressContent.textContent = history; // Use textContent for <pre>
         // Scroll to bottom after loading full history
         progressContent.scrollTop = progressContent.scrollHeight;
    } else {
         console.log(`Received full progress for ${receivedTaskId}, but panel shows ${displayedTaskIdShort}. Ignoring.`);
    }
}

function updateProgressPanelDelta(payload) {
    const receivedTaskId = payload.task_id;
    const token = payload.token;
    // Check if the received progress corresponds to the currently displayed task ID
    const displayedTaskIdShort = progressTaskId.textContent.replace('Task ID: ', '');
    if (receivedTaskId.startsWith(displayedTaskIdShort)) { // Compare with truncated ID
        // Add separator if it's the first assistant token (history ends with user prompt)
        if (progressContent.textContent.split('\n|||\n').length < 3) {
             progressContent.textContent += "\n|||\n";
        }
        progressContent.textContent += token;
        // Scroll to bottom to show the latest token
        progressContent.scrollTop = progressContent.scrollHeight;
    } else {
         console.log(`Received delta progress for ${receivedTaskId}, but panel shows ${displayedTaskIdShort}. Ignoring.`);
    }
}

closeProgressPanel.onclick = () => {
    progressPanel.style.display = 'none';
    // Optional: Send a message to server to stop watching? Not implemented server-side yet.
};

// --- Layout Toggle Logic ---
toggleLayoutBtn.onclick = () => {
    if (mainContainer.classList.contains('layout-horizontal')) {
        mainContainer.classList.remove('layout-horizontal');
        mainContainer.classList.add('layout-vertical');
    } else {
        mainContainer.classList.remove('layout-vertical');
        mainContainer.classList.add('layout-horizontal');
    }
};


// --- Initial Connection ---
// connectWebSocket(); // Moved to window.onload
