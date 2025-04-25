
from worker import Worker
from subprocess_tool import SubProcessTool
from jinja2 import Template
import asyncio
from task import Task, TaskState
import os
class SubprocessWorker(Worker):
    """
    A worker that executes shell commands based on a Jinja2 template.
    The template is rendered with the task description and executed as a subprocess.
    """
    
    def __init__(self, template: str):
        """
        Initialize the worker with a command template.
        
        Args:
            template (str): Jinja2 template string for the shell command.
                          The template should expect a 'task' variable.
        """
        self.template = Template(template)
        self.subprocess_tool = None
        self.task = None
        self.coroutine = None  # Track the current running task

    async def _execute_command(self, command: str, work_dir=None):
        """
        Internal method to execute the command using SubProcessTool.
        
        Args:
            command (str): The shell command to execute
        """
        try:
            # Create subprocess tool with command, end marker and work path
            self.subprocess_tool = SubProcessTool(
                command,
                None,
                work_dir=work_dir,
                0
            )
            # Execute command and process output tokens
            async for token in self.subprocess_tool.__call__(self.task.description + "\n@@@"):
                if token:
                    self.task.history += token
            # After process completes, set task state based on exit code
            exit_code = self.subprocess_tool.exit_code
            if exit_code == 0:
                self.task.state = TaskState.COMPLETE
            else:
                self.task.state = TaskState.PENDING
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            await self.stop()
            raise
        finally:
            self.task = None

    def start(self, task, work_dir):
        try:
            # Store task for potential future use
            self.task = task

            # Set task state to PROCESSING
            self.task.state = TaskState.PROCESSING
            
            # Render command template with task
            command = self.template.render(task=task, source_dir=os.path.dirname(os.path.realpath(__file__)))
            
            # Create and store coroutine
            self.coroutine = asyncio.create_task(self._execute_command(command, work_dir))
            
        except Exception as e:
            print(f"Error starting worker: {str(e)}")
            self.stop()
            raise

    async def stop(self):
        """
        Stop the worker and clean up resources.
        """
        # Set task state to PENDING if stopping early
        if self.task:
            self.task.state = TaskState.PENDING

        # Cancel the current task if it exists
        if self.coroutine:
            self.coroutine.cancel()
            try:
                await self.coroutine
            except asyncio.CancelledError:
                pass
            self.coroutine = None

        # Clean up subprocess tool
        if self.subprocess_tool:
            try:
                # Trigger subprocess tool cleanup
                self.subprocess_tool.__del__()
                self.subprocess_tool = None
            except Exception as e:
                print(f"Error stopping worker: {str(e)}")
        
        self.task = None

async def test():
    # 创建一个简单的命令模板
    # 在Windows下使用 dir 命令列出当前目录内容
    # 为了测试长时间运行的进程，我们让它每隔1秒重复执行
    """
    Asynchronous test function that demonstrates the usage of SubprocessWorker.
    
    Creates a worker instance with a command template to run an AI agent task.
    The worker executes a task to generate a snake game in HTML format.
    The process runs for 500 seconds before being stopped.
    
    Returns:
        None
    
    Raises:
        Exception: If any error occurs during worker execution
    """
    template = 'python agent.py --model-config model_configs/openrouter.yaml.example --system-prompt-template prompts/system.j2 --tool python_tool.PythonTool'
    
    try:
        # 创建 worker 实例
        worker = SubprocessWorker(template, False)
        
        # 创建 Task 实例
        task = Task(description="Write a snake game into a single HTM file.")
        
        # 启动 worker（使用 Task 对象）
        print("Starting worker...")
        worker.start(task, None)
        
        # 让进程运行5秒
        print("Worker running... will stop in 5 seconds")
        await asyncio.sleep(50)
        
        # 停止 worker
        print("Stopping worker...")
        await worker.stop()
        print("Worker stopped successfully")
        print(f"Task state: {task.state}, history: {task.history[:100]}...")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(test())