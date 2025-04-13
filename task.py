from enum import Enum

class TaskState(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"

class Task:
    def __init__(self, description: str, state: TaskState = TaskState.PENDING):
        self.description = description
        self.history = self.description + "\n|||\n"
        self._state = state

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state: TaskState):
        # Example: Add transition validation here if needed
        # For now, allow all transitions
        # You could add logic like:
        # if self._state == TaskState.COMPLETE:
        #     raise ValueError("Cannot change state from COMPLETE")
        self._state = new_state

    def __str__(self):
        return f"Task(description='{self.description}', history='{self.history}', state={self.state.value})"

# 使用示例
if __name__ == "__main__":
    # 创建一个新任务
    task = Task("完成项目报告")
    print(task)  # 默认状态为 PENDING
    
    # 更新任务状态
    task.state = TaskState.PROCESSING
    task.history = "开始处理任务"
    print(task)
    
    # 完成任务
    task.state = TaskState.COMPLETE
    task.history += "\n任务已完成"
    print(task)
