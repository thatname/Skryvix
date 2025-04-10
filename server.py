import asyncio
import json
import uuid
import os
import sys
import signal
from threading import Lock
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse # Added FileResponse
from fastapi.staticfiles import StaticFiles # Added StaticFiles
from typing import Dict, List, Any, Optional
import asyncio.subprocess as subprocess # Added for process management

# --- Configuration ---
AGENT_CONFIG_PATH = os.getenv("AGENT_CONFIG_PATH", "agent.yaml") # Default config path
AGENT_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "agent_runner.py") # Script to run for each agent
AGENT_WORKDIR_BASE = os.getenv("AGENT_WORKDIR_BASE", "agent_workspaces") # Base directory for agent working directories

AGENT_CONFIG_DIR = 'agent_configs'
available_agent_configs = []
try:
    config_dir_path = os.path.join(os.path.dirname(__file__), AGENT_CONFIG_DIR)
    if os.path.exists(config_dir_path) and os.path.isdir(config_dir_path):
        available_agent_configs = [
            os.path.abspath(os.path.join(config_dir_path, f))
            for f in os.listdir(config_dir_path)
            if f.endswith(('.yaml', '.yml'))
        ]
except Exception as e:
    print(f"Error loading agent configs: {e}")

# --- FastAPI App ---
app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- State Management ---
state_lock = Lock()

# Agent State
AGENT_TRANSITIONS = {
    'created': ['starting', 'terminating'],
    'starting': ['idle', 'error', 'terminating'],
    'idle': ['busy', 'stopping', 'terminating'],
    'busy': ['idle', 'stopping', 'error', 'terminating'], # Agent reports completion/failure -> idle, external stop -> stopping, crash -> error
    'stopping': ['stopped', 'error', 'terminating'],
    'stopped': ['starting', 'terminating'],
    'error': ['starting', 'terminating'], # Can retry from error
    'terminating': ['terminated'] # Final state (implicitly on removal)
}

def validate_agent_transition(old_state: str, new_state: str) -> bool:
    """Enforce valid agent state transitions"""
    return new_state in AGENT_TRANSITIONS.get(old_state, [])

def set_agent_state(agent_id: str, new_state: str):
    """Atomically update agent state with validation"""
    if agent_id not in agents:
        print(f"Warning: Attempted to set state for non-existent agent {agent_id}")
        return False
    with state_lock:
        old_state = agents[agent_id]['status']
        if not validate_agent_transition(old_state, new_state):
            print(f"Invalid agent state transition: {old_state} -> {new_state} for agent {agent_id}")
            return False
        agents[agent_id]['status'] = new_state
        print(f"Agent {agent_id} state changed: {old_state} -> {new_state}") # Added logging
        return True

# Task State
TASK_TRANSITIONS = {
    # 'new' state removed
    'running': ['completed', 'incomplete', 'terminating'], # Agent reports success -> completed, agent reports failure/crashes/disconnects -> incomplete
    'completed': ['terminating'],
    'incomplete': ['running', 'terminating'], # Can be retried, now the initial state
    'terminating': ['terminated'] # Final state (implicitly on removal)
}

def validate_task_transition(old_state: str, new_state: str) -> bool:
    """Enforce valid task state transitions"""
    return new_state in TASK_TRANSITIONS.get(old_state, [])

def set_task_state(task_id: str, new_state: str):
    """Atomically update task state with validation"""
    if task_id not in tasks:
        print(f"Warning: Attempted to set state for non-existent task {task_id}")
        return False
    with state_lock:
        # Ensure task exists within the lock
        if task_id not in tasks:
             print(f"Warning: Task {task_id} disappeared before state change.")
             return False
        old_state = tasks[task_id]['status']
        # Corrected logic:
        if not validate_task_transition(old_state, new_state):
            print(f"Invalid task state transition: {old_state} -> {new_state} for task {task_id}")
            return False
        tasks[task_id]['status'] = new_state
        print(f"Task {task_id} state changed: {old_state} -> {new_state}") # Added logging
        return True

# Store agent information: {agent_id: {"id": agent_id, "process": process_handle, "status": "idle/busy/starting/stopping/stopped/error/terminating", "websocket": websocket, "workdir": str, "config_path": str}}
agents: Dict[str, Dict[str, Any]] = {}
# Store task information: {task_id: {"id": task_id, "description": desc, "status": "new/running/completed/incomplete", "assigned_agent_id": agent_id | None, "result": result | None, "history": str, "watching_uis": set[WebSocket]}}
tasks: Dict[str, Dict[str, Any]] = {}
# Store active UI connections
ui_connections: List[WebSocket] = []
# Store active agent connections: {agent_id: websocket}
agent_connections: Dict[str, WebSocket] = {}
# Assignment Mode
auto_assign_mode: bool = True

@app.get('/get_configs')
async def get_configs():
    config_dir = os.path.join(os.path.dirname(__file__), AGENT_CONFIG_DIR)
    if not os.path.exists(config_dir) or not os.path.isdir(config_dir):
        return {"configs": []}
    filenames = [f for f in os.listdir(config_dir) if f.endswith(('.yaml', '.yml', '.yaml.example', '.yml.example'))]
    return {"configs": filenames}

# --- Helper Functions ---
async def broadcast_to_ui(message: Dict[str, Any]):
    """Sends a JSON message to all connected UI clients."""
    disconnected_uis = []
    for connection in ui_connections:
        try:
            await connection.send_json(message)
        except WebSocketDisconnect:
            disconnected_uis.append(connection)
        except Exception as e:
            print(f"Error sending message to UI: {e}")
            disconnected_uis.append(connection)
    # Clean up disconnected clients
    for connection in disconnected_uis:
        if connection in ui_connections:
            ui_connections.remove(connection)

def get_current_state() -> Dict[str, Any]:
    """Returns the current state of agents and tasks."""
    # Avoid sending process handles or websocket objects to UI
    serializable_agents = {
        agent_id: {k: v for k, v in agent_data.items() if k not in ["process", "websocket"]}
        for agent_id, agent_data in agents.items()
    }
    # Avoid sending large history or watcher sets in general state updates
    serializable_tasks = {
        task_id: {k: v for k, v in task_data.items() if k not in ["history", "watching_uis"]}
        for task_id, task_data in tasks.items()
    }
    return {
        "type": "state",
        "agents": serializable_agents,
        "tasks": serializable_tasks,
        "mode": "auto" if auto_assign_mode else "manual" # Include current mode
    }

async def broadcast_delta_to_watching_uis(task_id: str, message: Dict[str, Any]):
    """Sends a delta message only to UIs watching a specific task."""
    if task_id not in tasks or 'watching_uis' not in tasks[task_id]:
        return

    disconnected_watchers = set()
    # Iterate over a copy of the set in case it's modified during iteration (though unlikely here)
    watchers = list(tasks[task_id]['watching_uis'])

    for connection in watchers:
        try:
            await connection.send_json(message)
        except (WebSocketDisconnect, RuntimeError) as e: # Catch RuntimeError for 'WebSocket is closed'
            print(f"UI watcher for task {task_id} disconnected or error: {e}. Removing.")
            disconnected_watchers.add(connection)
        except Exception as e:
            print(f"Error sending delta to UI watcher for task {task_id}: {e}")
            disconnected_watchers.add(connection) # Assume disconnect on other errors too

    # Clean up disconnected watchers from the specific task's set
    if disconnected_watchers:
        tasks[task_id]['watching_uis'].difference_update(disconnected_watchers)


async def _assign_task_to_agent(task_id: str, agent_id: str) -> bool:
    """Assigns a specific task to a specific agent, updates states, and notifies."""
    if task_id not in tasks or agent_id not in agents:
        print(f"Error: Task {task_id} or Agent {agent_id} not found for assignment.")
        return False

    agent_ws = agent_connections.get(agent_id)
    task = tasks[task_id]
    agent = agents[agent_id]

    if not agent_ws:
         print(f"Agent {agent_id} websocket not found for task assignment.")
         set_agent_state(agent_id, "error")
         await broadcast_to_ui(get_current_state())
         return False
    if agent['status'] != 'idle':
         print(f"Error: Agent {agent_id} is not idle (status: {agent['status']}). Cannot assign task {task_id}.")
         return False
    # Only assign tasks that are 'incomplete'
    if task['status'] != 'incomplete':
         print(f"Error: Task {task_id} is not incomplete (status: {task['status']}). Cannot assign.")
         return False

    print(f"Assigning task {task_id} to agent {agent_id}")
    try:
        # Update state using the new setters
        if not set_agent_state(agent_id, "busy"): return False # Check if transition failed
        if not set_task_state(task_id, "running"):
            set_agent_state(agent_id, "idle") # Revert agent state if task transition fails
            return False

        task["assigned_agent_id"] = agent_id
        # Initialize/Reset history and watchers
        task["history"] = f"{task['description']}\n|||\n" # Start history
        task["watching_uis"] = set()

        # Notify agent and UI
        await agent_ws.send_json({"type": "assign_task", "task_id": task_id, "description": task["description"]})
        await broadcast_to_ui(get_current_state()) # Broadcast general state update
        print(f"Task {task_id} assigned successfully to {agent_id}.")
        return True # Indicate success
    except Exception as e:
        print(f"Error assigning task {task_id} to agent {agent_id}: {e}")
        # Revert state if sending failed
        set_agent_state(agent_id, "idle") # Revert agent state
        # Attempt to revert task state, check if task still exists
        if task_id in tasks:
            # Revert to 'incomplete' as it's the only valid starting state now
            set_task_state(task_id, 'incomplete')
            tasks[task_id]["assigned_agent_id"] = None
        await broadcast_to_ui(get_current_state())
        return False

async def assign_task_if_possible():
    """Assigns a new task to an idle agent if available AND in auto mode."""
    if not auto_assign_mode:
        # print("Auto-assign disabled.") # Optional logging
        return

    idle_agent_id = next(
        (a_id for a_id, data in agents.items()
         if data.get("status") == "idle"
         and a_id in agent_connections # Check if websocket connection exists
         and data.get("process")
         and data["process"].returncode is None), # Check if process is running
        None
    )
    # Find an 'incomplete' task for auto-assignment
    incomplete_task_id = next((task_id for task_id, data in tasks.items() if data.get("status") == "incomplete"), None)


    if idle_agent_id and incomplete_task_id:
        await _assign_task_to_agent(task_id=incomplete_task_id, agent_id=idle_agent_id)


# --- WebSocket Endpoints ---
@app.websocket("/ws/ui")
async def websocket_ui_endpoint(websocket: WebSocket):
    """Handles WebSocket connections from the frontend UI."""
    await websocket.accept()
    ui_connections.append(websocket)
    print("UI client connected.")
    # Send initial state
    await websocket.send_json(get_current_state())

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received from UI: {data}")
            command = data.get("command")
            payload = data.get("payload", {})

            if command == "create_agent":
                agent_id = str(uuid.uuid4())
                print(f"UI requested to create agent {agent_id}")
                
                # Create agent work directory
                workdir = os.path.join(AGENT_WORKDIR_BASE, agent_id)
                os.makedirs(workdir, exist_ok=True)
                
                # Store agent config path
                config_filename = payload.get("config", "example_agent.yaml")
                config_dir_path = os.path.join(os.path.dirname(__file__), AGENT_CONFIG_DIR)
                config_path = os.path.join(config_dir_path, config_filename)
                
                # Initialize agent with 'created' status
                agents[agent_id] = {
                    "id": agent_id,
                    "process": None,
                    "status": "created",
                    "websocket": None,
                    "workdir": workdir,
                    "config_path": config_path
                }
                await broadcast_to_ui(get_current_state())

            elif command == "start_agent":
                agent_id = payload.get("agent_id")
                if agent_id in agents and agents[agent_id]["status"] in ["created", "stopped", "error"]:
                    print(f"UI requested to start agent {agent_id}")
                    set_agent_state(agent_id, "starting")
                    await broadcast_to_ui(get_current_state())

                    try:
                        # Determine server URL
                        server_ws_url = "ws://localhost:8000" # Adjust as needed
                        
                        cmd = [
                            sys.executable,
                            AGENT_SCRIPT_PATH,
                            "--agent-id", agent_id,
                            "--server-url", server_ws_url,
                            "--config-path", agents[agent_id]["config_path"]
                        ]
                        print(f"Starting agent {agent_id} with command: {' '.join(cmd)}")

                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=agents[agent_id]["workdir"]
                        )
                        agents[agent_id]["process"] = process
                        print(f"Agent {agent_id} process started with PID: {process.pid}")

                        # Start monitoring tasks
                        asyncio.create_task(monitor_process_output(agent_id, process.stdout, "stdout"))
                        asyncio.create_task(monitor_process_output(agent_id, process.stderr, "stderr"))
                        asyncio.create_task(monitor_process_exit(agent_id, process))

                    except Exception as e:
                        print(f"Failed to start agent {agent_id}: {e}") # Indentation fixed here
                        set_agent_state(agent_id, "error") # Use setter
                        agents[agent_id]["process"] = None
                        await broadcast_to_ui(get_current_state())

            elif command == "stop_agent":
                agent_id = payload.get("agent_id")
                if agent_id in agents and agents[agent_id].get("process"):
                    print(f"UI requested to stop agent {agent_id}")
                    if set_agent_state(agent_id, "stopping"): # Use setter
                        await broadcast_to_ui(get_current_state())
                        process = agents[agent_id]["process"]
                        if process.returncode is None:
                            try:
                                # Send SIGINT (Ctrl+C equivalent) first for graceful shutdown
                                process.terminate()
                                print(f"Sent SIGTERM to agent {agent_id} process {process.pid}")
                                # Monitor_process_exit will handle the state change to 'stopped' or 'error'
                            except ProcessLookupError:
                                print(f"Process {process.pid} already exited.")
                                set_agent_state(agent_id, "stopped") # Mark as stopped if process gone
                                await broadcast_to_ui(get_current_state())
                            except Exception as e:
                                print(f"Error sending SIGTERM to agent {agent_id}: {e}")
                                set_agent_state(agent_id, "error") # Mark agent as error if signal fails
                                await broadcast_to_ui(get_current_state())
                    else:
                         print(f"Agent {agent_id} process already exited.")
                         set_agent_state(agent_id, "stopped") # Ensure state is correct
                         await broadcast_to_ui(get_current_state())

            elif command == "terminate_agent":
                agent_id = payload.get("agent_id")
                if agent_id in agents:
                    print(f"UI requested to terminate agent {agent_id}")
                    original_status = agents[agent_id]['status']
                    if set_agent_state(agent_id, "terminating"):
                        await broadcast_to_ui(get_current_state())

                        process = agents[agent_id].get("process")
                        if process and process.returncode is None:
                            print(f"Terminating agent process {process.pid} for agent {agent_id}...")
                            try:
                                process.terminate() # SIGTERM
                                try:
                                    await asyncio.wait_for(process.wait(), timeout=5.0)
                                    print(f"Agent process {process.pid} terminated gracefully.")
                                except asyncio.TimeoutError:
                                    print(f"Agent process {process.pid} did not terminate gracefully, killing...")
                                    process.kill() # SIGKILL
                                    await process.wait()
                                    print(f"Agent process {process.pid} killed.")
                            except ProcessLookupError:
                                print(f"Process {process.pid} already exited.")
                            except Exception as e:
                                print(f"Error terminating agent {agent_id}: {e}")
                                # State remains 'terminating', cleanup happens below

                        # Clean up agent resources regardless of process state
                        if agent_id in agent_connections:
                            await agent_connections[agent_id].close()
                            del agent_connections[agent_id]

                        # Mark associated task as incomplete if agent was busy
                        if original_status == 'busy':
                            task_id_to_incomplete = next((tid for tid, tdata in tasks.items() if tdata.get("assigned_agent_id") == agent_id), None)
                            if task_id_to_incomplete:
                                print(f"Marking task {task_id_to_incomplete} as incomplete due to agent termination.")
                                set_task_state(task_id_to_incomplete, "incomplete")
                                tasks[task_id_to_incomplete]["assigned_agent_id"] = None

                        # Clean up work directory
                        if "workdir" in agents[agent_id]:
                            workdir = agents[agent_id]["workdir"]
                            try:
                                import shutil
                                shutil.rmtree(workdir)
                                print(f"Deleted work directory for agent {agent_id}: {workdir}")
                            except Exception as e:
                                print(f"Error deleting work directory for agent {agent_id}: {e}")

                        # Remove agent entry AFTER cleanup
                        del agents[agent_id]
                        await broadcast_to_ui(get_current_state()) # Broadcast final state after removal
                    else:
                        print(f"Could not transition agent {agent_id} to terminating state.")
                else:
                    print(f"Terminate request for unknown agent ID: {agent_id}")

            elif command == "add_task":
                task_desc = payload.get("description")
                if task_desc:
                    task_id = str(uuid.uuid4())
                    print(f"UI added task {task_id}: {task_desc}")
                    tasks[task_id] = {
                        "id": task_id,
                        "description": task_desc,
                        "status": "incomplete", # Initial state is now incomplete
                        "assigned_agent_id": None,
                        "result": None,
                        "history": "",
                        "watching_uis": set()
                    }
                    await broadcast_to_ui(get_current_state())
                    await assign_task_if_possible() # Try assigning if in auto mode
                else:
                    print("Add task request missing description.")

            elif command == "delete_task":
                task_id = payload.get("task_id")
                if task_id in tasks:
                    print(f"UI requested to delete task {task_id}")
                    # Add validation? e.g., prevent deleting 'running' tasks? For now, allow deletion.
                    if set_task_state(task_id, "terminating"): # Mark for termination first
                        # Clean up watchers
                        if 'watching_uis' in tasks[task_id]:
                            tasks[task_id]['watching_uis'].clear()
                        del tasks[task_id]
                        print(f"Task {task_id} deleted.")
                        await broadcast_to_ui(get_current_state())
                    else:
                         print(f"Could not transition task {task_id} to terminating for deletion.")
                else:
                    print(f"Delete request for unknown task ID: {task_id}")

            elif command == "set_assignment_mode":
                global auto_assign_mode
                mode = payload.get("mode")
                if mode == "auto":
                    auto_assign_mode = True
                    print("Assignment mode set to AUTO")
                    await broadcast_to_ui({"type": "mode_update", "mode": "auto"})
                    await assign_task_if_possible() # Try assigning immediately
                elif mode == "manual":
                    auto_assign_mode = False
                    print("Assignment mode set to MANUAL")
                    await broadcast_to_ui({"type": "mode_update", "mode": "manual"})
                else:
                    print(f"Invalid assignment mode received: {mode}")

            elif command == "manual_assign_task":
                task_id = payload.get("task_id")
                agent_id = payload.get("agent_id")
                if auto_assign_mode:
                    print("Warning: Manual assignment attempted while in AUTO mode.")
                    # Optionally send an error back to UI
                    await websocket.send_json({"type": "error", "payload": {"message": "Cannot manually assign in AUTO mode."}})
                elif task_id and agent_id:
                    print(f"UI requested manual assignment of task {task_id} to agent {agent_id}")
                    success = await _assign_task_to_agent(task_id, agent_id)
                    if not success:
                        print(f"Manual assignment failed for task {task_id} to agent {agent_id}")
                        # Optionally send failure feedback to UI
                        await websocket.send_json({"type": "error", "payload": {"message": f"Failed to assign task {task_id} to agent {agent_id}."}})
                else:
                    print("Manual assign request missing task_id or agent_id.")
                    await websocket.send_json({"type": "error", "payload": {"message": "Missing task_id or agent_id for manual assignment."}})


            elif command == "get_progress":
                task_id = payload.get("task_id")
                if task_id in tasks:
                    # Ensure watching_uis set exists
                    if 'watching_uis' not in tasks[task_id]: tasks[task_id]['watching_uis'] = set()
                    # Add this UI to the watchers for this task
                    tasks[task_id]['watching_uis'].add(websocket)
                    print(f"UI client {websocket.client} started watching task {task_id}")
                    # Send the full current history back to the requesting UI only
                    history = tasks[task_id].get('history', f"History not available for task {task_id}.")
                    await websocket.send_json({
                        "type": "task_progress_full",
                        "payload": {"task_id": task_id, "history": history}
                    })
                else:
                    print(f"UI requested progress for unknown task: {task_id}")
                    # Optionally send an error back to the UI
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Task {task_id} not found."}
                    })
            else:
                print(f"Unknown command from UI: {command}")

    except WebSocketDisconnect:
        print(f"UI client {websocket.client} disconnected.")
    except Exception as e:
        print(f"Error in UI websocket: {e}")
    finally:
        # Remove UI from general list and any task watching sets
        if websocket in ui_connections:
            ui_connections.remove(websocket)
        for task_id in tasks:
            if 'watching_uis' in tasks[task_id] and websocket in tasks[task_id]['watching_uis']:
                tasks[task_id]['watching_uis'].remove(websocket)
                print(f"Removed disconnected UI {websocket.client} from watching task {task_id}")


# --- Process Monitoring ---
async def monitor_process_output(agent_id: str, stream, stream_name: str):
    """Monitors stdout/stderr of an agent process."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            print(f"Agent {agent_id} [{stream_name}]: {line.decode().rstrip()}")
        print(f"Agent {agent_id} [{stream_name}] stream ended.")
    except Exception as e:
        print(f"Error monitoring {stream_name} for agent {agent_id}: {e}")

async def monitor_process_exit(agent_id: str, process):
    """Monitors an agent process for exit and cleans up."""
    return_code = await process.wait()
    print(f"Agent process {process.pid} for agent {agent_id} exited with code {return_code}.")

    if agent_id not in agents:
        print(f"Agent {agent_id} (PID {process.pid}) exited but was already removed/terminated.")
        return

    agent_current_status = agents[agent_id]['status']

    # Determine final agent state based on exit code and current status
    final_agent_state = 'stopped' # Default assumption
    if agent_current_status == 'terminating':
        # Termination was requested, cleanup already handled by terminate_agent command
        print(f"Agent {agent_id} process exited during termination.")
        # Agent entry should have been removed by terminate_agent, but check just in case
        if agent_id in agents: del agents[agent_id]
        if agent_id in agent_connections: del agent_connections[agent_id]
        await broadcast_to_ui(get_current_state())
        return # Exit early, termination handles cleanup
    elif agent_current_status == 'stopping':
        # For stopping state, exit code 1 is expected (SIGTERM)
        final_agent_state = 'stopped'
        print(f"Agent {agent_id} stopped normally (exit code {return_code})")
    elif return_code != 0:
        final_agent_state = 'error' # Process crashed or exited unexpectedly

    # Set final agent state
    set_agent_state(agent_id, final_agent_state)

    # If agent was busy and didn't exit cleanly, mark task as incomplete
    if agent_current_status == 'busy' and final_agent_state == 'error':
        task_id_to_incomplete = next((tid for tid, tdata in tasks.items() if tdata.get("assigned_agent_id") == agent_id), None)
        if task_id_to_incomplete:
            print(f"Marking task {task_id_to_incomplete} as incomplete due to agent {agent_id} error exit.")
            if set_task_state(task_id_to_incomplete, "incomplete"):
                 tasks[task_id_to_incomplete]["assigned_agent_id"] = None
            else:
                 print(f"Failed to set task {task_id_to_incomplete} to incomplete.")

    # Clean up websocket connection if it still exists
    if agent_id in agent_connections:
        await agent_connections[agent_id].close()
        del agent_connections[agent_id]
        agents[agent_id]["websocket"] = None # Clear reference

    await broadcast_to_ui(get_current_state())
    await assign_task_if_possible() # Check if the now stopped/errored agent frees up a task slot (unlikely but check)


@app.websocket("/ws/agent/{agent_id}")
async def websocket_agent_endpoint(websocket: WebSocket, agent_id: str):
    """Handles WebSocket connections from individual agent processes."""
    if agent_id not in agents:
        print(f"Agent {agent_id} connected but not found in registry. Closing.")
        await websocket.close(code=1008)
        return

    await websocket.accept()
    agent_connections[agent_id] = websocket
    agents[agent_id]["websocket"] = websocket # Store websocket object
    
    # Set state to idle if it was starting
    if agents[agent_id]["status"] == "starting":
        set_agent_state(agent_id, "idle")
    else:
        # If agent reconnects unexpectedly (e.g. after error), reset to idle if possible
        if agents[agent_id]["status"] in ['error', 'stopped']:
             print(f"Agent {agent_id} reconnected with status {agents[agent_id]['status']}, setting to idle.")
             set_agent_state(agent_id, "idle")
        else:
             print(f"Agent {agent_id} connected with unexpected status: {agents[agent_id]['status']}")
             # Consider closing connection or setting to error? For now, allow but log.

    await broadcast_to_ui(get_current_state())
    await assign_task_if_possible() # Check if tasks are waiting for this now idle agent

    try:
        while True:
            data = await websocket.receive_json()
            # print(f"Received from Agent {agent_id}: {data}")
            message_type = data.get("type")
            payload = data.get("payload", {})

            # Note: Agent should not send status_update, server manages state based on events/commands
            # if message_type == "status_update": ... (Removed)

            if message_type == "task_result":
                task_id = payload.get("task_id")
                result = payload.get("result")
                agent_reported_status = payload.get("status", "completed") # completed or failed

                if task_id in tasks and tasks[task_id].get("assigned_agent_id") == agent_id:
                    final_task_status = "completed" if agent_reported_status == "completed" else "incomplete"

                    tasks[task_id]["result"] = result
                    set_task_state(task_id, final_task_status) # Use setter
                    tasks[task_id]["assigned_agent_id"] = None # Unassign
                    if 'watching_uis' in tasks[task_id]: tasks[task_id]["watching_uis"].clear() # Clear watchers

                    set_agent_state(agent_id, "idle")  # Agent becomes idle

                    print(f"Task {task_id} finished by agent {agent_id}. Agent reported: {agent_reported_status}, Final status: {final_task_status}.")
                    await broadcast_to_ui(get_current_state()) # Broadcast general state
                    await assign_task_if_possible() # Check for next task
                elif task_id not in tasks:
                    print(f"Agent {agent_id} sent result for unknown task ID: {task_id}")
                else: # Task exists but not assigned to this agent
                     print(f"Agent {agent_id} sent result for task {task_id} which is assigned to {tasks[task_id].get('assigned_agent_id')}. Ignoring.")


            elif message_type == "progress_update":
                task_id = payload.get("task_id")
                token = payload.get("token")
                if task_id in tasks and token is not None:
                    if 'history' not in tasks[task_id]:
                        tasks[task_id]['history'] = "" # Initialize if missing (edge case)
                        print(f"Warning: Initialized missing history for task {task_id} during progress update.")

                    tasks[task_id]['history'] += token # Correctly indented line

                    # Broadcast the token delta ONLY to UIs watching this task
                    delta_message = {
                        "type": "task_progress_delta",
                        "payload": {"task_id": task_id, "token": token}
                    }
                    # Use create_task to avoid blocking the agent message loop
                    asyncio.create_task(broadcast_delta_to_watching_uis(task_id, delta_message))

                elif task_id not in tasks:
                    print(f"Warning: Received progress update for unknown task {task_id}.")
                # Ignore if token is None

            else:
                print(f"Unknown message type from agent {agent_id}: {message_type}")

    except WebSocketDisconnect:
        print(f"Agent {agent_id} disconnected.")
    except Exception as e:
        print(f"Error in agent {agent_id} websocket: {e}")
        # State transition and task incompletion handled by finally block
    finally:
        print(f"Agent {agent_id} websocket handler closing.")
        original_status = agents[agent_id]['status'] if agent_id in agents else 'unknown'

        # Mark agent as error on unexpected disconnect, unless terminating/stopping
        if agent_id in agents and agents[agent_id]['status'] not in ['terminating', 'stopping', 'stopped']:
             set_agent_state(agent_id, "error")

        # If agent was busy, mark its task as incomplete
        if original_status == 'busy':
            task_id_to_incomplete = next((tid for tid, tdata in tasks.items() if tdata.get("assigned_agent_id") == agent_id), None)
            if task_id_to_incomplete:
                print(f"Marking task {task_id_to_incomplete} as incomplete due to agent {agent_id} disconnect.")
                if set_task_state(task_id_to_incomplete, "incomplete"):
                    tasks[task_id_to_incomplete]["assigned_agent_id"] = None
                else:
                    print(f"Failed to set task {task_id_to_incomplete} to incomplete.")

        # Cleanup connection reference
        if agent_id in agent_connections:
            del agent_connections[agent_id]
        if agent_id in agents: # Check agent wasn't deleted by termination
             agents[agent_id]["websocket"] = None
             print(f"Cleaned up connection for agent {agent_id}. Final status: {agents[agent_id]['status']}")
        else:
             print(f"Agent {agent_id} already removed, skipping final status log.")

        await broadcast_to_ui(get_current_state())
        # Don't try to assign task here, monitor_process_exit handles agent state changes more reliably

# --- Root Endpoint ---
@app.get("/")
async def get_root():
    """Serves the main index.html file."""
    return FileResponse('static/index.html')

# --- Server Lifecycle Events ---
@app.on_event("shutdown")
async def shutdown_event():
    print("Server shutting down. Terminating active agent processes...")
    # Create a list of agent IDs to terminate to avoid modifying dict during iteration
    agent_ids_to_terminate = list(agents.keys())
    termination_tasks = []

    for agent_id in agent_ids_to_terminate:
        if agent_id in agents and agents[agent_id].get("process"):
            process = agents[agent_id]["process"]
            if process.returncode is None:
                print(f"Sending terminate signal to agent {agent_id} (PID {process.pid})...")
                process.terminate()
                termination_tasks.append(process.wait()) # Add wait task

    # Wait for processes to terminate (with a timeout)
    if termination_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*termination_tasks), timeout=10.0)
            print("Agent processes terminated.")
        except asyncio.TimeoutError:
            print("Timeout waiting for agent processes to terminate. Forcing kill...")
            # Force kill any remaining processes
            for agent_id in agent_ids_to_terminate:
                 if agent_id in agents and agents[agent_id].get("process"):
                     process = agents[agent_id]["process"]
                     if process.returncode is None:
                         try:
                             process.kill()
                         except Exception as e:
                             print(f"Error killing process {process.pid} for agent {agent_id}: {e}")
        except Exception as e:
            print(f"Error during shutdown termination: {e}")
    print("Shutdown complete.")


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    print("Starting Agent Manager Server...")
    # Ensure AGENT_CONFIG_PATH exists or provide guidance
    if not os.path.exists(AGENT_CONFIG_PATH):
         print(f"Warning: Default agent config file '{AGENT_CONFIG_PATH}' not found.")
         print("Ensure the config file exists or set the AGENT_CONFIG_PATH environment variable.")
         # Optionally exit if config is critical for startup
         # sys.exit(f"Error: Agent config file '{AGENT_CONFIG_PATH}' not found.")

    uvicorn.run(app, host="0.0.0.0", port=8000)
