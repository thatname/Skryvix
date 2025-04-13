from enum import Enum
import uuid
import yaml
import os
from typing import Callable, Any, List, Dict

class TaskState(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"

class Task:
    def __init__(self, description: str, state: TaskState = TaskState.PENDING):
        self._listeners: Dict[str, List[Callable[[Any, Any], None]]] = {"description": [], "history": [], "state": []}
        # Initialize directly to avoid triggering listeners on creation
        self._description = description
        self._history = description + "\n|||\n"
        self._state = state

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, new_description: str):
        old_description = self._description
        if old_description != new_description:
            self._description = new_description
            self._notify_listeners("description", old_description, new_description)

    @property
    def history(self):
        return self._history

    @history.setter
    def history(self, new_history: str):
        old_history = self._history
        if old_history != new_history:
            self._history = new_history
            self._notify_listeners("history", old_history, new_history)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state: TaskState):
        old_state = self._state
        if old_state != new_state:
            # Example: Add transition validation here if needed
            self._state = new_state
            self._notify_listeners("state", old_state, new_state)

    def add_listener(self, property_name: str, callback: Callable[[Any, Any], None]):
        """Registers a listener for property changes."""
        if property_name in self._listeners:
            if callback not in self._listeners[property_name]:
                self._listeners[property_name].append(callback)
        else:
            raise ValueError(f"Invalid property name: {property_name}")

    def remove_listener(self, property_name: str, callback: Callable[[Any, Any], None]):
        """Unregisters a listener."""
        if property_name in self._listeners:
            try:
                self._listeners[property_name].remove(callback)
            except ValueError:
                # Callback not found, ignore
                pass
        else:
            raise ValueError(f"Invalid property name: {property_name}")

    def _notify_listeners(self, property_name: str, old_value: Any, new_value: Any):
        """Notifies registered listeners about a property change."""
        if property_name in self._listeners:
            # Iterate over a copy in case a listener modifies the list
            for callback in self._listeners[property_name][:]:
                try:
                    callback(old_value, new_value)
                except Exception as e:
                    # Handle listener errors appropriately, e.g., log them
                    print(f"Error in listener for {property_name}: {e}")

    def __str__(self):
        # Use properties in __str__
        return f"Task(description='{self.description}', history='{self.history}', state={self.state.value})"

class TaskManager:
    """
    Manages a collection of Tasks, each identified by a UUID.
    Supports creation, destruction, saving to YAML, and loading from YAML.
    """
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.tasks: dict[uuid.UUID, Task] = {}

    def create(self, description: str) -> uuid.UUID:
        """
        Create a new Task with the given description.
        Returns the UUID of the created task.
        """
        task_id = uuid.uuid4()
        task = Task(description) # Task creation uses __init__
        self.tasks[task_id] = task
        return task_id

    def destroy(self, task_id: uuid.UUID):
        """
        Remove the task with the given UUID.
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
        else:
            raise KeyError(f"Task ID {task_id} not found.")

    def save(self):
        """
        Serialize all tasks to YAML at self.yaml_path.
        """
        data = {}
        for tid, task in self.tasks.items():
            # Use properties to get current values
            data[str(tid)] = {
                "description": task.description,
                "history": task.history,
                "state": task.state.value
            }
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def load(self):
        """
        Load all tasks from YAML at self.yaml_path.
        Reconstructs the mapping of UUID to Task.
        """
        if not os.path.exists(self.yaml_path):
            self.tasks = {}
            return
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not data:
                self.tasks = {}
                return
            tasks = {}
            for tid_str, task_data in data.items():
                try:
                    tid = uuid.UUID(tid_str)
                    description = task_data["description"]
                    history = task_data.get("history", description + "\n|||\n") # Get raw history
                    state_str = task_data.get("state", TaskState.PENDING.value)
                    state = TaskState(state_str)
                    # Initialize task with description and state (uses __init__)
                    task = Task(description, state)
                    # Set history directly using the internal attribute to avoid triggering listener during load
                    task._history = history
                    tasks[tid] = task
                except Exception as e:
                    print(f"Error loading task {tid_str}: {e}") # Added logging
                    # Skip invalid tasks
                    continue
            self.tasks = tasks
