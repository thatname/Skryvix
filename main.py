import asyncio
import os
import uuid
import yaml
import argparse
import uvicorn
import json
from sse_starlette.sse import EventSourceResponse
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List, Dict, Any, Optional, AsyncGenerator

from workspace import WorkspaceManager, WorkSpace
from task import TaskManager, Task, TaskState
from worker import Worker
from enum import Enum

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Run the Task Runner FastAPI application.")
parser.add_argument(
    "--workspace-root",
    type=str,
    help="Path to the root directory for workspaces. Can be absolute or relative to the current working directory.",
    default=None # Default will be handled below, relative to script dir
)
args = parser.parse_args()

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent.resolve()
WORKER_CONFIGS_DIR = SCRIPT_DIR / "worker_configs"
STATIC_DIR = SCRIPT_DIR / "static"

# Determine Workspace Root
if args.workspace_root:
    workspace_path_arg = Path(args.workspace_root)
    if workspace_path_arg.is_absolute():
        WORKSPACE_ROOT = workspace_path_arg
    else:
        # Resolve relative paths against the current working directory
        WORKSPACE_ROOT = Path.cwd() / workspace_path_arg
else:
    # Default to a directory relative to the script location if not provided
    WORKSPACE_ROOT = SCRIPT_DIR / "workspace_root"

TASKS_YAML_PATH = WORKSPACE_ROOT / "tasks.yaml"

# --- Lifespan Management for Watchdog ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: Initialize and start watchdog
    print("Application startup: Initializing watchdog...")
    observer = Observer()
    try:
        loop = asyncio.get_running_loop()
        print(f"Lifespan startup: Using event loop {id(loop)}")
        event_handler = FileChangeHandler(websocket_manager, loop)
        observer.schedule(event_handler, str(WORKSPACE_ROOT), recursive=True)
        observer.start()
        app.state.observer = observer # Store observer in app state
        print("Watchdog observer started.")
    except Exception as e:
        print(f"Error starting watchdog observer: {e}")
        # Decide if the app should fail to start if observer fails
        raise # Re-raise to prevent app start if observer is critical

    yield # Application runs here

    # Shutdown: Stop watchdog
    print("Application shutdown: Stopping watchdog observer...")
    observer = getattr(app.state, "observer", None)
    if observer and observer.is_alive():
        observer.stop()
        observer.join() # Wait for the observer thread to finish
        print("Watchdog observer stopped.")
    else:
        print("Watchdog observer not found or already stopped.")


# --- Initialization ---
app = FastAPI(lifespan=lifespan) # Register the lifespan manager

# Ensure directories exist (using Path objects)
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
WORKER_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Managers (pass paths as strings if needed by the classes)
workspace_manager = WorkspaceManager(work_root=str(WORKSPACE_ROOT))
task_manager = TaskManager(yaml_path=str(TASKS_YAML_PATH))
try:
    task_manager.load()
    print(f"Loaded {len(task_manager.tasks)} tasks from {TASKS_YAML_PATH}")
except FileNotFoundError:
    print(f"Tasks file not found at {TASKS_YAML_PATH}, starting fresh.")
except Exception as e:
    print(f"Error loading tasks: {e}")

# --- State Tracking ---
active_workers: Dict[uuid.UUID, Dict[str, Any]] = {}  # {task_id: {"worker": Worker, "workspace": WorkSpace}}

# --- Connection Managers ---
class TaskHistoryConnectionManager:
    def __init__(self):
        # Store asyncio Queues for each task ID
        self.active_connections: Dict[uuid.UUID, List[asyncio.Queue]] = {}

    async def subscribe(self, task_id: uuid.UUID, queue: asyncio.Queue):
        """Subscribe a queue to receive updates for a specific task."""
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(queue)
        print(f"SSE queue subscribed for task {task_id}")

    def unsubscribe(self, task_id: uuid.UUID, queue: asyncio.Queue):
        """Unsubscribe a queue from task updates."""
        if task_id in self.active_connections:
            try:
                self.active_connections[task_id].remove(queue)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
                print(f"SSE queue unsubscribed for task {task_id}")
            except ValueError:
                print(f"Warning: Queue not found during unsubscribe for task {task_id}")
        else:
            print(f"Warning: Task ID {task_id} not found during unsubscribe")

    async def send_history_update(self, task_id: uuid.UUID, new_tokens: str):
        """Send history updates to all subscribed queues for a task."""
        queues_to_remove = []
        if task_id in self.active_connections:
            # Iterate safely over a copy in case unsubscribe modifies the list
            for queue in list(self.active_connections.get(task_id, [])):
                try:
                    await queue.put(new_tokens)
                except asyncio.QueueFull:
                    print(f"Warning: Queue full for a subscriber of task {task_id}. Update lost.")
                    # Optionally remove the queue if it's consistently full
                    # queues_to_remove.append(queue)
                except Exception as e:
                    print(f"Error putting update onto queue for task {task_id}: {e}")
                    # Decide if error warrants removal
                    # queues_to_remove.append(queue)

            # # Remove problematic queues if necessary
            # for queue in queues_to_remove:
            #     self.unsubscribe(task_id, queue)

            # The loop below is leftover from the old implementation and should be removed.
            # active_connections now holds queues, not response objects to send to directly.
            # for response in self.active_connections[task_id]:
            #     try:
            #         await response.send(f"data: {json.dumps({'tokens': new_tokens})}\n\n")
            #     except Exception as e:
            #         print(f"Error sending SSE update for task {task_id}: {e}")
            #         self.unsubscribe(task_id, response)

class WebSocketConnectionManager:
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


task_history_manager = TaskHistoryConnectionManager()
websocket_manager = WebSocketConnectionManager()

# --- Task Change Listeners ---
async def notify_task_change(task_id: uuid.UUID, property_name: str, old_value: Any, new_value: Any):
    """Callback function to broadcast task changes via WebSocket."""
    print(f"Task {task_id} changed: {property_name} from {old_value} to {new_value}")
    update_data = {
        "type": "task_update",
        "task_id": str(task_id),
        "data": {property_name: new_value.value if isinstance(new_value, Enum) else new_value}
    }
    await websocket_manager.broadcast(update_data)

async def notify_history_change(task_id: uuid.UUID, old_history: str, new_history: str):
    """Callback function to send history updates via SSE."""
    if old_history and new_history.startswith(old_history):
        # Only send the new tokens if it's an append operation
        new_tokens = new_history[len(old_history):]
        await task_history_manager.send_history_update(task_id, new_tokens)
    else:
        # Send full history if it's not an append or if old_history is empty
        await task_history_manager.send_history_update(task_id, new_history)

async def cleanup_worker_on_state_change(task_id: uuid.UUID, old_state: TaskState, new_state: TaskState):
    """Callback function to clean up worker resources when task leaves PROCESSING state."""
    if old_state == TaskState.PROCESSING and new_state != TaskState.PROCESSING:
        print(f"Task {task_id} left PROCESSING state ({old_state.value} -> {new_state.value}). Cleaning up worker.")
        try:
            if task_id in active_workers:
                worker_info = active_workers.pop(task_id) # Remove and get info
                workspace = worker_info["workspace"]
                workspace_manager.free(workspace)
                print(f"Cleaned up worker and freed workspace {workspace.id} for task {task_id}")
                # Notify clients about workspace being freed
                await websocket_manager.broadcast({"type": "workspaces_updated"})
            else:
                # This might happen if stop_task was called concurrently or if cleanup already occurred
                print(f"Task {task_id} not found in active_workers during cleanup listener execution.")
        except Exception as e:
            # Log error but don't prevent other operations
            print(f"Error during worker cleanup for task {task_id}: {e}")


# Register listeners for existing tasks
for task_id, task_obj in task_manager.tasks.items():
    # Ensure task is not stuck in PROCESSING state from a previous run without an active worker
    if task_obj.state == TaskState.PROCESSING and task_id not in active_workers:
        print(f"Correcting state for task {task_id}: Found PROCESSING but no active worker. Setting to PENDING.")
        task_obj.state = TaskState.PENDING # Reset state directly

    task_obj.add_listener("state", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "state", old, new)))
    task_obj.add_listener("state", lambda old, new, tid=task_id: asyncio.create_task(cleanup_worker_on_state_change(tid, old, new))) # Add cleanup listener
    # Correctly register notify_history_change for SSE updates on history changes for existing tasks
    task_obj.add_listener("history", lambda old, new, tid=task_id: asyncio.create_task(notify_history_change(tid, old, new)))
    # We don't usually notify on description changes unless required
    # task_obj.add_listener("description", lambda old, new, tid=task_id: asyncio.create_task(notify_task_change(tid, "description", old, new)))

# --- Directory Watchdog ---
class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, websocket_manager, loop): # Add loop parameter
        self.websocket_manager = websocket_manager
        self.loop = loop # Store the loop

    # Make it synchronous
    def on_any_event(self, event):
        print(f"[Watchdog] Event handler triggered for: {event.src_path} (type: {event.event_type})")
        # Optional: Filter out directory events if not needed
        # if event.is_directory:
        #     print("[Watchdog] Skipping directory event.")
        #     return

        try:
            print(f"[Watchdog] Preparing message for {event.src_path}")
            # Prepare the message payload
            message = {
                "type": "directory_changed",
                # Ensure path is relative and serializable
                "path": str(Path(event.src_path).relative_to(WORKSPACE_ROOT))
            }

            # Schedule the async broadcast call on the main loop
            print(f"[Watchdog] Scheduling broadcast for {event.src_path} on loop {id(self.loop)}")
            future = asyncio.run_coroutine_threadsafe(
                self.websocket_manager.broadcast(message),
                self.loop
            )

            # Define a callback to check the future's result
            def future_callback(fut):
                try:
                    result = fut.result() # Check for exceptions raised in the coroutine
                    print(f"[Watchdog] Broadcast future completed for {event.src_path}. Result: {result}")
                except Exception as exc:
                    print(f"[Watchdog] Broadcast future failed for {event.src_path}: {exc!r}")

            future.add_done_callback(future_callback)
            print(f"[Watchdog] Broadcast scheduled for {event.src_path}.")

        except Exception as e:
            # Log errors happening during event handling *before* scheduling
            print(f"[Watchdog] Error in FileChangeHandler.on_any_event for {event.src_path} BEFORE scheduling: {e!r}")


# Watchdog observer is now initialized and managed by the lifespan function

# --- API Endpoints ---
@app.get("/api/directory")
async def get_directory(path: str = ""):
    target_path = WORKSPACE_ROOT / path
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    contents = []
    for item in target_path.iterdir():
        contents.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else 0
        })
    
    return {
        "path": str(target_path.relative_to(WORKSPACE_ROOT)),
        "contents": contents
    }

# Serve Static Files (HTML, CSS, JS) - Use Path object directly if supported, else convert to string
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/workspace_root", StaticFiles(directory=str(WORKSPACE_ROOT)), name="workspace_root")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Serve the main index.html
    index_path = STATIC_DIR / "index.html" # Use Path object
    if not index_path.exists():
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
         index_path.write_text(placeholder_content) # Use Path object method

    html_content = index_path.read_text() # Use Path object method
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
    new_task.add_listener("state", lambda old, new, tid=task_id: asyncio.create_task(cleanup_worker_on_state_change(tid, old, new))) # Add cleanup listener
    # Correctly register notify_history_change for SSE updates on history changes
    new_task.add_listener("history", lambda old, new, tid=task_id: asyncio.create_task(notify_history_change(tid, old, new)))

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

    # Ensure worker_config_name doesn't contain path traversal characters for security
    if ".." in worker_config_name or "/" in worker_config_name or "\\" in worker_config_name:
         raise HTTPException(status_code=400, detail="Invalid worker configuration name")

    worker_config_path = WORKER_CONFIGS_DIR / f"{worker_config_name}.yaml" # Assume .yaml extension or adjust as needed
    if not worker_config_path.exists():
        # Try without .yaml if that's the convention
        worker_config_path = WORKER_CONFIGS_DIR / worker_config_name
        if not worker_config_path.exists():
             raise HTTPException(status_code=400, detail=f"Worker configuration '{worker_config_name}' not found in {WORKER_CONFIGS_DIR}")


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
        pass # Cleanup is now handled by the state change listener

    # worker.stop() should trigger the state change listener which handles cleanup
    # We might still want to ensure the state becomes PENDING if stop() fails silently
    # but the listener is the primary cleanup mechanism.
    # If worker.stop() successfully changes state, the listener handles active_workers and workspace.

    # Optional: Force state check if stop() might fail without state change
    # task = task_manager.tasks[task_id]
    # if task_id not in active_workers and task.state == TaskState.PROCESSING:
    #     print(f"Forcing task {task_id} state to PENDING after stop attempt.")
    #     task.state = TaskState.PENDING # This would trigger listeners again if not already PENDING

    return {"message": f"Stop request sent for task {task_id}. Cleanup occurs on state change."}


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
        # Use pathlib for listing files
        configs = [f.name for f in WORKER_CONFIGS_DIR.iterdir() if f.is_file() and f.suffix == '.yaml']
        # Optionally remove the .yaml suffix if the API expects just the name
        # configs = [f.stem for f in WORKER_CONFIGS_DIR.iterdir() if f.is_file() and f.suffix == '.yaml']
        return {"configs": configs}
    except FileNotFoundError:
        # WORKER_CONFIGS_DIR is created at startup, so this shouldn't happen unless deleted manually
        print(f"Warning: Worker config directory not found at {WORKER_CONFIGS_DIR}")
        return {"configs": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading worker configs: {e}")


# --- SSE Endpoint ---
@app.get("/task-history/{task_id}")
async def task_history_stream(request: Request, task_id: uuid.UUID):
    # Check if task exists
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get the task
    task = task_manager.tasks[task_id]
    
    # SSE response setup using asyncio Queue
    async def event_generator():
        queue = asyncio.Queue()
        await task_history_manager.subscribe(task_id, queue)
        print(f"SSE EventSource subscribed and queue registered for task {task_id}")
        try:
            # Send initial full history immediately after subscribing
            yield {
                "event": "message", # Use "message" or a custom event type like "initial"
                "data": json.dumps({
                    "type": "initial_history",
                    "history": task.history
                })
            }

            # Listen for updates from the queue
            while True:
                # Check connection status before waiting indefinitely
                if await request.is_disconnected():
                    print(f"SSE client disconnected (checked before queue.get) for task {task_id}")
                    break

                try:
                    # Wait for new tokens from the queue
                    new_tokens = await queue.get()
                    yield {
                        "event": "message", # Use "message" or a custom event type like "update"
                        "data": json.dumps({
                            "type": "history_update", # More specific type
                            "tokens": new_tokens
                        })
                    }
                    queue.task_done() # Mark the item as processed
                except asyncio.CancelledError:
                    # This occurs if the client disconnects while queue.get() is waiting
                    print(f"SSE queue.get() cancelled for task {task_id}, likely client disconnect.")
                    break # Exit the loop on cancellation
                except Exception as e:
                    print(f"Error getting from SSE queue for task {task_id}: {e}")
                    # Decide if we should break or continue
                    break # Example: break on error

        except asyncio.CancelledError:
            # This catches cancellation if it happens outside the queue.get() wait
            print(f"SSE event_generator task cancelled for task {task_id}")
        finally:
            # Ensure unsubscribe happens regardless of how the loop exits
            print(f"SSE unsubscribing queue for task {task_id}")
            task_history_manager.unsubscribe(task_id, queue)
            print(f"SSE EventSource connection closed and queue unsubscribed for task {task_id}")

    return EventSourceResponse(event_generator())

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
def run_server():
    # Watchdog observer is now managed by the lifespan context manager
    # The old @app.on_event("shutdown") is also replaced by the lifespan's shutdown phase

    # Run Uvicorn
    # Pass remaining args (like host/port) to uvicorn if needed, or configure here
    # Explicitly tell uvicorn to use the asyncio loop standard.
    # Uvicorn will use the loop set for the current thread if available.
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000, loop="asyncio", reload=False)
    server = uvicorn.Server(config)

    # Run the server (this blocks until shutdown)
    # Uvicorn's run method handles the loop lifecycle properly
    server.run()


if __name__ == "__main__":
    run_server()
