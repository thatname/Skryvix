import asyncio
import os
import uuid
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any, Optional

from workspace import WorkspaceManager, WorkSpace
from task import TaskManager, Task, TaskState
from worker import Worker
from enum import Enum
# --- Configuration ---
WORKSPACE_ROOT = "d:/Code/CodeAgent/workspace_root"
TASKS_YAML_PATH = os.path.join(WORKSPACE_ROOT, "tasks.yaml")
WORKER_CONFIGS_DIR = "d:/Code/CodeAgent/worker_configs"
STATIC_DIR = "d:/Code/CodeAgent/static"

# --- Initialization ---
app = FastAPI()

# Ensure directories exist
os.makedirs(WORKSPACE_ROOT, exist_ok=True)
os.makedirs(WORKER_CONFIGS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Initialize Managers
workspace_manager = WorkspaceManager(work_root=WORKSPACE_ROOT)
task_manager = TaskManager(yaml_path=TASKS_YAML_PATH)
try:
    task_manager.load()
    print(f"Loaded {len(task_manager.tasks)} tasks from {TASKS_YAML_PATH}")
except FileNotFoundError:
    print(f"Tasks file not found at {TASKS_YAML_PATH}, starting fresh.")
except Exception as e:
    print(f"Error loading tasks: {e}")

# --- State Tracking ---
active_workers: Dict[uuid.UUID, Dict[str, Any]] = {}  # {task_id: {"worker": Worker, "workspace": WorkSpace}}

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Potentially add tracking for which task details a client is interested in
        # self.task_subscriptions: Dict[WebSocket, uuid.UUID] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        try:
            websocket.close()           
        except Exception as e:
            print(f"Error closing {websocket.client}: {e}")
        finally:
            self.active_connections.remove(websocket)
            print(f"WebSocket disconnected: {websocket.client}")

    async def broadcast(self, message: dict):
        connections_to_remove: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {connection.client}: {e}")
                connections_to_remove.append(connection)
        for connection in connections_to_remove:
            self.disconnect(connection) # Use disconnect for consistent removal
        

    async def send_personal_message(self, message: dict, websocket: WebSocket):
         try:
             await websocket.send_json(message)
         except Exception as e:
             print(f"Error sending personal message to {websocket.client}: {e}")


websocket_manager = ConnectionManager()

# --- Task Change Listeners ---
async def notify_task_change(task_id: uuid.UUID, property_name: str, old_value: Any, new_value: Any):
    """Callback function to broadcast task changes via WebSocket."""
    print(f"Task {task_id} changed: {property_name} from {old_value} to {new_value}")
    update_data = {
        "type": "task_update",
        "task_id": str(task_id),
        "data": {property_name: new_value.value if isinstance(new_value, Enum) else new_value} # Send enum value
    }
    # If history changed, maybe send delta or full history based on strategy
    if property_name == "history":
         update_data["data"] = {"history": new_value} # Send full history for now

    await websocket_manager.broadcast(update_data)

# Register listeners for existing tasks
for task_id, task_obj in task_manager.tasks.items():
    task_obj.add_listener("state", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "state", old, new)))
    task_obj.add_listener("history", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "history", old, new)))
    # We don't usually notify on description changes unless required
    # task_obj.add_listener("description", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "description", old, new)))


# --- API Endpoints ---

# Serve Static Files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Serve the main index.html
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
         # Create a basic placeholder if it doesn't exist
         placeholder_content = """
         <!DOCTYPE html>
         <html>
         <head>
             <title>Task Runner</title>
             <link rel="stylesheet" href="/static/style.css">
         </head>
         <body>
             <h1>Task Runner Interface</h1>
             <p>Frontend not fully implemented yet.</p>
             <div id="workspace-panel"><h2>Workspaces</h2></div>
             <div id="task-panel"><h2>Tasks</h2></div>
             <div id="details-panel"><h2>Details</h2></div>
             <script src="/static/script.js"></script>
         </body>
         </html>
         """
         with open(index_path, "w") as f:
             f.write(placeholder_content)

    with open(index_path, "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# --- Workspace API ---
@app.get("/api/workspaces")
async def get_workspaces():
    # Return detailed workspace info including taskid if occupied
    return [
        {"id": ws.id, "path": ws.path, "is_occupied": ws.is_occupied, "taskid": str(ws.taskid) if ws.taskid else None}
        for ws in workspace_manager.workspaces
    ]

@app.post("/api/workspaces", status_code=201)
async def create_workspace():
    workspace = workspace_manager.create()
    if workspace is None:
        raise HTTPException(status_code=500, detail="Failed to create workspace")
    await websocket_manager.broadcast({"type": "workspaces_updated"})
    return {"id": workspace.id, "path": workspace.path, "is_occupied": False, "taskid": None}

@app.put("/api/workspaces/count")
async def set_workspace_count(request: Request):
    body = await request.json()
    count = body.get("count")
    if count is None or not isinstance(count, int) or count < 0:
        raise HTTPException(status_code=400, detail="Invalid count provided")

    success = workspace_manager.set_workspace_count(count)
    if not success:
        raise HTTPException(status_code=409, detail="Cannot set workspace count (possibly due to occupied workspaces)")
    await websocket_manager.broadcast({"type": "workspaces_updated"})
    return {"message": f"Workspace count set to {count}"}

@app.delete("/api/workspaces/{ws_id}")
async def delete_workspace(ws_id: int):
    workspace_to_delete = next((ws for ws in workspace_manager.workspaces if ws.id == ws_id), None)
    if workspace_to_delete is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace_to_delete.is_occupied:
         raise HTTPException(status_code=409, detail="Cannot delete occupied workspace")

    success = workspace_manager.delete(workspace_to_delete)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete workspace")
    await websocket_manager.broadcast({"type": "workspaces_updated"})
    return {"message": f"Workspace {ws_id} deleted"}

# --- Task API ---
@app.get("/api/tasks")
async def get_tasks():
    tasks_by_state = {state.value: [] for state in TaskState}
    for tid, task in task_manager.tasks.items():
        tasks_by_state[task.state.value].append({
            "id": str(tid),
            "description": task.description,
            "history": task.history, # Consider if history should be fetched separately
            "state": task.state.value
        })
    return tasks_by_state

@app.post("/api/tasks", status_code=201)
async def create_task(request: Request):
    body = await request.json()
    description = body.get("description")
    if not description:
        raise HTTPException(status_code=400, detail="Task description is required")

    task_id = task_manager.create(description)
    new_task = task_manager.tasks[task_id]

    # Register listeners for the new task
    new_task.add_listener("state", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "state", old, new)))
    new_task.add_listener("history", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "history", old, new)))

    task_manager.save() # Persist the new task
    await websocket_manager.broadcast({
        "type": "task_created",
        "task": {
            "id": str(task_id),
            "description": new_task.description,
            "history": new_task.history,
            "state": new_task.state.value
        }
    })
    return {"id": str(task_id)}

@app.post("/api/tasks/{task_id}/start")
async def start_task(task_id: uuid.UUID, request: Request):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    if task_id in active_workers:
        raise HTTPException(status_code=409, detail="Task is already running")

    task = task_manager.tasks[task_id]
    if task.state != TaskState.PENDING:
         raise HTTPException(status_code=409, detail=f"Task is not in PENDING state (state: {task.state.value})")

    body = await request.json()
    worker_config_name = body.get("worker_config")
    if not worker_config_name:
        raise HTTPException(status_code=400, detail="Worker configuration name is required")

    worker_config_path = os.path.join(WORKER_CONFIGS_DIR, worker_config_name)
    if not os.path.exists(worker_config_path):
        raise HTTPException(status_code=400, detail=f"Worker configuration '{worker_config_name}' not found")

    # Allocate workspace
    workspace = workspace_manager.alloc(str(task_id))
    if workspace is None:
        raise HTTPException(status_code=503, detail="No available workspaces")

    try:
        # Load worker config
        with open(worker_config_path, 'r') as f:
            config_content = yaml.safe_load(f)

        # Create worker instance
        worker = Worker.create(config_content)

        # Start worker (runs in background)
        # The worker's start method should handle setting the task state to PROCESSING
        # and update history/state via the task object's setters (triggering listeners)
        worker.start(task, workspace.path)

        # Store worker and task info
        active_workers[task_id] = {"worker": worker, "workspace": workspace}

        # Notify clients about workspace allocation change
        await websocket_manager.broadcast({"type": "workspaces_updated"})
        # Task state change will be broadcast by the listener

        return {"message": f"Task {task_id} started in workspace {workspace.id}"}

    except Exception as e:
        # Clean up if worker creation/start fails
        print(f"Error starting task {task_id}: {e}")
        workspace_manager.free(workspace) # Free the workspace
        task.state = TaskState.PENDING # Reset state if it was changed
        await websocket_manager.broadcast({"type": "workspaces_updated"}) # Notify workspace freed
        await websocket_manager.broadcast({ # Notify state reset
            "type": "task_update",
            "task_id": str(task_id),
            "data": {"state": TaskState.PENDING.value}
        })
        raise HTTPException(status_code=500, detail=f"Failed to start worker: {e}")


@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: uuid.UUID):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    if task_id not in active_workers:
        raise HTTPException(status_code=409, detail="Task is not running")

    worker_info = active_workers[task_id]
    worker = worker_info["worker"]
    workspace = worker_info["workspace"]

    try:
        await worker.stop() # This should ideally set the task state via listener
    except Exception as e:
        print(f"Error stopping worker for task {task_id}: {e}")
        # Continue cleanup even if stop fails

    # Clean up
    del active_workers[task_id]
    workspace_manager.free(workspace)

    # Ensure state is PENDING after stop (worker.stop might already do this via listener)
    task = task_manager.tasks[task_id]
    if task.state != TaskState.PENDING:
         task.state = TaskState.PENDING # Force state if needed

    await websocket_manager.broadcast({"type": "workspaces_updated"})
    # Task state change should have been broadcast by listener during worker.stop()

    return {"message": f"Task {task_id} stopped"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: uuid.UUID):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    # Stop the task if it's running
    if task_id in active_workers:
        await stop_task(task_id) # Reuse stop logic for cleanup

    task = task_manager.tasks[task_id]
    # Remove listeners before deleting? (Might not be strictly necessary if object is garbage collected)
    # task.remove_listener(...)

    try:
        task_manager.destroy(task_id)
        task_manager.save() # Persist deletion
    except KeyError:
         raise HTTPException(status_code=404, detail="Task not found (race condition?)")
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to delete task: {e}")

    await websocket_manager.broadcast({"type": "task_deleted", "task_id": str(task_id)})
    return {"message": f"Task {task_id} deleted"}

# --- Worker Config API ---
@app.get("/api/worker_configs")
async def get_worker_configs():
    try:
        configs = [f for f in os.listdir(WORKER_CONFIGS_DIR) if os.path.isfile(os.path.join(WORKER_CONFIGS_DIR, f)) and f.endswith('.yaml')]
        return {"configs": configs}
    except FileNotFoundError:
        return {"configs": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading worker configs: {e}")


# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        # Send initial state? Or let client fetch via API?
        # await websocket_manager.send_personal_message({"type": "welcome"}, websocket)
        while True:
            # Keep connection open, listen for client messages (optional)
            # data = await websocket.receive_text()
            # Handle client messages if needed (e.g., subscribing to specific task details)
            await asyncio.sleep(3600) # Keep alive, prevent timeout if no messages
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket)


# --- Server Startup ---
if __name__ == "__main__":
    import uvicorn
    # Ensure reload is False for production or when state needs persistence across restarts
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    # Note: reload=True is convenient for development but will reset in-memory state (like active_workers)
    # For production, use reload=False and potentially handle graceful shutdowns to save state.
