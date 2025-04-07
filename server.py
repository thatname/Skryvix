import asyncio
import json
import uuid
import os
import sys
import signal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse # Added FileResponse
from fastapi.staticfiles import StaticFiles # Added StaticFiles
from typing import Dict, List, Any, Optional
import asyncio.subprocess as subprocess # Added for process management

# --- Configuration ---
AGENT_CONFIG_PATH = os.getenv("AGENT_CONFIG_PATH", "config.yaml") # Default config path
AGENT_SCRIPT_PATH = "agent_runner.py" # Script to run for each agent

# --- FastAPI App ---
app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- State Management ---
# Store agent information: {agent_id: {"id": agent_id, "process": process_handle, "status": "idle/busy/starting/terminating/error", "websocket": websocket}}
agents: Dict[str, Dict[str, Any]] = {}
# Store task information: {task_id: {"id": task_id, "description": desc, "status": "new/running/completed/failed", "assigned_agent_id": agent_id, "result": result}}
tasks: Dict[str, Dict[str, Any]] = {}
# Store active UI connections
ui_connections: List[WebSocket] = []
# Store active agent connections: {agent_id: websocket}
agent_connections: Dict[str, WebSocket] = {}

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
    return {"type": "state", "agents": serializable_agents, "tasks": tasks}

async def assign_task_if_possible():
    """Assigns a new task to an idle agent if available."""
    idle_agent_id = next((agent_id for agent_id, data in agents.items() if data.get("status") == "idle" and agent_id in agent_connections), None)
    new_task_id = next((task_id for task_id, data in tasks.items() if data.get("status") == "new"), None)

    if idle_agent_id and new_task_id:
        print(f"Assigning task {new_task_id} to agent {idle_agent_id}")
        agent_ws = agent_connections.get(idle_agent_id)
        task = tasks[new_task_id]
        if agent_ws:
            try:
                # Update state
                agents[idle_agent_id]["status"] = "busy"
                task["status"] = "running"
                task["assigned_agent_id"] = idle_agent_id

                # Notify agent and UI
                await agent_ws.send_json({"type": "assign_task", "task_id": new_task_id, "description": task["description"]})
                await broadcast_to_ui(get_current_state())
                print(f"Task {new_task_id} assigned successfully.")
            except Exception as e:
                print(f"Error assigning task {new_task_id} to agent {idle_agent_id}: {e}")
                # Revert state if sending failed
                agents[idle_agent_id]["status"] = "idle" # Or maybe 'error'?
                task["status"] = "new"
                task["assigned_agent_id"] = None
                await broadcast_to_ui(get_current_state())
        else:
             print(f"Agent {idle_agent_id} websocket not found for task assignment.")
             # Consider setting agent status to error or removing if websocket is missing but should be there
             agents[idle_agent_id]["status"] = "error" # Example
             await broadcast_to_ui(get_current_state())


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

            if command == "spawn_agent":
                agent_id = str(uuid.uuid4())
                print(f"UI requested to spawn agent {agent_id}")
                agents[agent_id] = {"id": agent_id, "process": None, "status": "starting", "websocket": None}
                await broadcast_to_ui(get_current_state()) # Update UI immediately

                try:
                    # Determine server URL (adjust if running behind proxy etc.)
                    # For simplicity, assuming localhost for now.
                    # In production, might need request.base_url or config.
                    server_ws_url = "ws://localhost:8000" # Adjust as needed

                    # Command to run the agent runner script
                    cmd = [
                        sys.executable, # Use the same Python interpreter
                        AGENT_SCRIPT_PATH,
                        "--agent-id", agent_id,
                        "--server-url", server_ws_url
                    ]
                    print(f"Spawning agent {agent_id} with command: {' '.join(cmd)}")

                    # Spawn the process
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=subprocess.PIPE, # Capture stdout
                        stderr=subprocess.PIPE  # Capture stderr
                    )
                    agents[agent_id]["process"] = process
                    print(f"Agent {agent_id} process started with PID: {process.pid}")

                    # Start background tasks to monitor stdout/stderr and process exit
                    asyncio.create_task(monitor_process_output(agent_id, process.stdout, "stdout"))
                    asyncio.create_task(monitor_process_output(agent_id, process.stderr, "stderr"))
                    asyncio.create_task(monitor_process_exit(agent_id, process))

                    # Status will be updated to 'idle' when the agent connects via WebSocket
                except Exception as e:
                    print(f"Failed to spawn agent {agent_id}: {e}")
                    agents[agent_id]["status"] = "error"
                    agents[agent_id]["process"] = None # Ensure process is None on failure
                    await broadcast_to_ui(get_current_state())


            elif command == "terminate_agent":
                agent_id = payload.get("agent_id")
                if agent_id in agents and agents[agent_id].get("process"):
                    print(f"UI requested to terminate agent {agent_id}")
                    agents[agent_id]["status"] = "terminating"
                    await broadcast_to_ui(get_current_state()) # Update UI

                    process = agents[agent_id]["process"]
                    if process.returncode is None: # Check if process is still running
                        print(f"Terminating agent process {process.pid} for agent {agent_id}...")
                        try:
                            process.terminate() # Send SIGTERM
                            # Wait briefly for graceful shutdown
                            try:
                                await asyncio.wait_for(process.wait(), timeout=5.0)
                                print(f"Agent process {process.pid} terminated gracefully.")
                            except asyncio.TimeoutError:
                                print(f"Agent process {process.pid} did not terminate gracefully, sending SIGKILL...")
                                process.kill() # Force kill if terminate fails
                                await process.wait() # Wait for kill to complete
                                print(f"Agent process {process.pid} killed.")
                        except ProcessLookupError:
                             print(f"Process {process.pid} already exited.")
                        except Exception as e:
                            print(f"Error during termination of agent {agent_id} (PID {process.pid}): {e}")
                            # Attempt to kill again if error occurred during terminate
                            try:
                                if process.returncode is None:
                                    process.kill()
                                    await process.wait()
                            except Exception as kill_e:
                                print(f"Error during kill attempt for agent {agent_id}: {kill_e}")

                    else:
                        print(f"Agent process for {agent_id} already exited with code {process.returncode}.")

                    # Final cleanup handled by monitor_process_exit or websocket disconnect
                    # We just mark as terminating here. The monitor task will remove it.
                elif agent_id in agents:
                     print(f"Terminate request for agent {agent_id} but process not found or already exited.")
                     # Clean up if agent exists but process doesn't
                     if agents[agent_id]["status"] != "terminating": # Avoid race condition with monitor_process_exit
                         del agents[agent_id]
                         if agent_id in agent_connections: del agent_connections[agent_id]
                         await broadcast_to_ui(get_current_state())
                else:
                    print(f"Terminate request for unknown agent ID: {agent_id}")

            elif command == "add_task":
                task_desc = payload.get("description")
                if task_desc:
                    task_id = str(uuid.uuid4())
                    print(f"UI added task {task_id}: {task_desc}")
                    tasks[task_id] = {"id": task_id, "description": task_desc, "status": "new", "assigned_agent_id": None, "result": None}
                    await broadcast_to_ui(get_current_state())
                    await assign_task_if_possible() # Try assigning immediately
                else:
                    print("Add task request missing description.")

            else:
                print(f"Unknown command from UI: {command}")

    except WebSocketDisconnect:
        print("UI client disconnected.")
    except Exception as e:
        print(f"Error in UI websocket: {e}")
    finally:
        if websocket in ui_connections:
            ui_connections.remove(websocket)


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

    # Clean up agent state
    if agent_id in agents:
        # Update status if not already terminating (e.g., crashed)
        if agents[agent_id]["status"] != "terminating":
             agents[agent_id]["status"] = "exited_unexpectedly" if return_code != 0 else "exited_normally"
        agents[agent_id]["process"] = None # Remove process handle

        # If status is terminating, remove the agent entry completely after exit
        if agents[agent_id]["status"] == "terminating":
            print(f"Removing terminated agent {agent_id} from registry.")
            del agents[agent_id]
            if agent_id in agent_connections: # Should be cleaned by websocket disconnect, but double-check
                del agent_connections[agent_id]
        else:
             # Keep the entry but mark status if it exited unexpectedly
             print(f"Agent {agent_id} marked as exited with status: {agents[agent_id]['status']}")

        await broadcast_to_ui(get_current_state()) # Update UI about the exit/removal
    else:
        print(f"Agent {agent_id} (PID {process.pid}) exited but was already removed from registry.")


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
    agents[agent_id]["status"] = "idle"
    print(f"Agent {agent_id} connected and set to idle.")
    await broadcast_to_ui(get_current_state())
    await assign_task_if_possible() # Check if tasks are waiting

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received from Agent {agent_id}: {data}")
            message_type = data.get("type")
            payload = data.get("payload", {})

            if message_type == "status_update":
                new_status = payload.get("status")
                if new_status:
                    agents[agent_id]["status"] = new_status
                    print(f"Agent {agent_id} status updated to: {new_status}")
                    await broadcast_to_ui(get_current_state())

            elif message_type == "task_result":
                task_id = payload.get("task_id")
                result = payload.get("result")
                status = payload.get("status", "completed") # completed or failed
                if task_id in tasks:
                    tasks[task_id]["result"] = result
                    tasks[task_id]["status"] = status
                    tasks[task_id]["assigned_agent_id"] = None # Unassign
                    agents[agent_id]["status"] = "idle" # Agent becomes idle
                    print(f"Task {task_id} finished by agent {agent_id} with status: {status}")
                    await broadcast_to_ui(get_current_state())
                    await assign_task_if_possible() # Check for next task
                else:
                    print(f"Received result for unknown task ID: {task_id}")

            else:
                print(f"Unknown message type from agent {agent_id}: {message_type}")

    except WebSocketDisconnect:
        print(f"Agent {agent_id} disconnected.")
    except Exception as e:
        print(f"Error in agent {agent_id} websocket: {e}")
        agents[agent_id]["status"] = "error" # Mark agent as errored on exception
    finally:
        # Cleanup on disconnect or error
        if agent_id in agent_connections:
            del agent_connections[agent_id]
        if agent_id in agents:
            # Keep agent entry but mark as disconnected/error unless explicitly terminated
            if agents[agent_id]["status"] != "terminating":
                 agents[agent_id]["status"] = "disconnected_error"
            agents[agent_id]["websocket"] = None # Remove websocket object
            print(f"Cleaned up connection for agent {agent_id}. Status: {agents[agent_id]['status']}")
        await broadcast_to_ui(get_current_state())
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
