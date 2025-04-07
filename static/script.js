// --- DOM Elements ---
const agentList = document.getElementById('agentList');
const newTasksList = document.getElementById('newTasks');
const runningTasksList = document.getElementById('runningTasks');
const completedTasksList = document.getElementById('completedTasks');
const spawnAgentBtn = document.getElementById('spawnAgent');
const addTaskBtn = document.getElementById('addTask');
const taskDescInput = document.getElementById('taskDesc');

// --- WebSocket Setup ---
const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${location.host}/ws/ui`;
let ws = null;

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
            console.log("Received state:", data);
            if (data.type === 'state') {
                updateUI(data.agents, data.tasks);
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
function updateUI(agents, tasks) {
    // Update Agents
    agentList.innerHTML = ''; // Clear previous list
    const agentIds = Object.keys(agents).sort(); // Sort for consistent order

    if (agentIds.length === 0) {
        agentList.innerHTML = '<li>No active agents.</li>';
    } else {
        agentIds.forEach(agentId => {
            const agent = agents[agentId];
            const li = document.createElement('li');
            li.className = `status-${agent.status || 'unknown'}`; // Add default class

            // Agent Info Span
            const infoSpan = document.createElement('span');
            infoSpan.textContent = `Agent ${agentId.substring(0, 8)} (${agent.status})`;
            li.appendChild(infoSpan);

            // Terminate Button (only if not terminating/exited)
            if (!['terminating', 'exited_unexpectedly', 'exited_normally'].includes(agent.status)) {
                const terminateBtn = document.createElement('button');
                terminateBtn.textContent = 'Terminate';
                terminateBtn.onclick = (e) => {
                    e.stopPropagation(); // Prevent potential li click events
                    terminateAgent(agentId);
                };
                li.appendChild(terminateBtn);
            }
            agentList.appendChild(li);
        });
    }


    // Update Tasks
    newTasksList.innerHTML = '';
    runningTasksList.innerHTML = '';
    completedTasksList.innerHTML = '';
    const taskIds = Object.keys(tasks).sort((a, b) => tasks[a].id.localeCompare(tasks[b].id)); // Sort by ID

    let hasNew = false, hasRunning = false, hasCompleted = false;

    taskIds.forEach(taskId => {
        const task = tasks[taskId];
        const li = document.createElement('li');
        li.className = `status-${task.status || 'unknown'}`;

        let text = `Task ${taskId.substring(0, 8)}: ${task.description || 'No description'}`;
        if (task.status === 'running') {
            text += ` (Agent: ${task.assigned_agent_id ? task.assigned_agent_id.substring(0, 8) : 'N/A'})`;
        } else if (task.status === 'completed' || task.status === 'failed') {
            let resultText = 'N/A';
            if (task.result !== null && task.result !== undefined) {
                try {
                    // Attempt to stringify; limit length
                    resultText = JSON.stringify(task.result);
                    if (resultText.length > 100) {
                         resultText = resultText.substring(0, 100) + '...';
                    }
                } catch (e) {
                    resultText = String(task.result).substring(0, 100) + '...'; // Fallback to string conversion
                }
            }
             text += ` (Result: ${resultText})`;
        }
        li.textContent = text;
        li.title = `ID: ${taskId}\nStatus: ${task.status}\nDescription: ${task.description}\nResult: ${JSON.stringify(task.result, null, 2)}`; // Tooltip with full details

        if (task.status === 'new') {
            newTasksList.appendChild(li);
            hasNew = true;
        } else if (task.status === 'running') {
            runningTasksList.appendChild(li);
            hasRunning = true;
        } else { // completed or failed
            completedTasksList.appendChild(li);
            hasCompleted = true;
        }
    });

    // Add placeholder if lists are empty
    if (!hasNew) newTasksList.innerHTML = '<li>No new tasks.</li>';
    if (!hasRunning) runningTasksList.innerHTML = '<li>No tasks running.</li>';
    if (!hasCompleted) completedTasksList.innerHTML = '<li>No completed tasks.</li>';
}

// --- Event Handlers ---
spawnAgentBtn.onclick = () => {
    console.log("Requesting agent spawn");
    sendWsCommand({ command: 'spawn_agent' });
};

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

// --- Helper to Send Commands ---
function sendWsCommand(commandData) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(commandData));
    } else {
         console.error("WebSocket not connected. Cannot send command:", commandData);
         alert("WebSocket connection is not open. Please wait or refresh.");
    }
}

// --- Initial Connection ---
connectWebSocket();
