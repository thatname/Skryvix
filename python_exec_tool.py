
from tool import Tool
import sys
from io import StringIO
import os
class PythonTool(Tool):
    def name(self)->str:
        return "python"
    def description(self) -> str:
        return """* python - Execute python code. For example: 
```python
def display_file(path)
    with open(, 'r') as f:
        print(f.read())
display_file('c:/repository/file.cpp')
```
The python interpreter is persistent, You can reuse python funciton you've already written. 
In order to complete your development task, you can write python code to manipulate the code within this repository's source files.
"""

    async def use(self, args: str):
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        import threading
        import queue

        # 创建一个队列用于存储输出
        output_queue = queue.Queue()
        
        # 创建自定义的stdout来捕获输出
        class QueuedOutput:
            def __init__(self, queue):
                self.queue = queue
                
            def write(self, text):
                if text:  # 只处理非空文本
                    self.queue.put(text)
                    
            def flush(self):
                pass

        # 保存原始stdout
        old_stdout = sys.stdout
        # 设置新的stdout
        sys.stdout = QueuedOutput(output_queue)

        # 创建一个事件来标识执行是否完成
        execution_done = threading.Event()
        execution_error = None

        # 在线程中执行Python代码
        def execute_code():
            nonlocal execution_error
            try:
                exec(args)
            except Exception as e:
                execution_error = str(e)
            finally:
                execution_done.set()

        # 使用线程池执行代码
        with ThreadPoolExecutor() as executor:
            executor.submit(execute_code)

        # 跟踪是否有过任何输出
        had_output = False
        
        try:
            # 循环检查输出队列，直到执行完成
            while not execution_done.is_set() or not output_queue.empty():
                try:
                    # 每100ms检查一次队列
                    output = output_queue.get_nowait()
                    had_output = True
                    yield output
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue

            # 如果发生了异常，yield异常信息
            if execution_error:
                yield f"Exception: {execution_error}"
                had_output = True
            # 只有在完全没有输出时才显示成功消息
            elif not had_output:
                yield "Python code executed successfully, no output"

        finally:
            # 恢复原始stdout
            sys.stdout = old_stdout

async def test():
    # 保存原始的stdout
    original_stdout = sys.stdout
    
    def safe_write(text):
        """安全地写入到原始stdout"""
        original_stdout.write(text)
        original_stdout.flush()
    
    safe_write("Entering main function\n")
    # Create PythonTool instance
    python_tool = PythonTool()
    
    # Display tool description
    safe_write("Tool description: " + python_tool.description() + "\n")
    safe_write("\n=== Test Cases ===\n\n")

    # Test case 1: Simple print
    safe_write("Test 1 - Simple print:\n")
    code1 = 'print("Hello, Python Tool!")'
    safe_write(f"Code: {code1}\n")
    safe_write("Output:\n")
    async for output in python_tool.use(code1):
        safe_write(output)
    safe_write("\n\n")

    # Test case 2: Multiple lines of code
    safe_write("Test 2 - Multiple lines of code:\n")
    code2 = '''
for i in range(3):
    print(f"Count: {i}")
'''
    safe_write(f"Code: {code2}\n")
    safe_write("Output:\n")
    async for output in python_tool.use(code2):
        safe_write(output)
    safe_write("\n\n")

    # Test case 3: Mathematical calculation
    safe_write("Test 3 - Mathematical calculation:\n")
    code3 = '''
result = 0
for i in range(1, 5):
    result += i
print(f"Sum of 1 to 4 is: {result}")
'''
    safe_write(f"Code: {code3}\n")
    safe_write("Output:\n")
    async for output in python_tool.use(code3):
        safe_write(output)
    safe_write("\n\n")

    # Test case 4: Error handling
    safe_write("Test 4 - Error handling:\n")
    code4 = 'print(undefined_variable)'
    safe_write(f"Code: {code4}\n")
    safe_write("Output:\n")
    async for output in python_tool.use(code4):
        safe_write(output)
    safe_write("\n")

if __name__ == "__main__":
    # 保存原始的stdout
    original_stdout = sys.stdout
    def safe_write(text):
        """安全地写入到原始stdout"""
        original_stdout.write(text)
        original_stdout.flush()
    
    safe_write("Program started\n")
    import asyncio
    asyncio.run(test())
    safe_write("Program ended\n")