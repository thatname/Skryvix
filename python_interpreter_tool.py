
from tool import Tool
import sys
from io import StringIO
import os
import code
import traceback
import threading
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor

class PythonInterpreterTool(Tool):
    def __init__(self):
        # Create a dictionary to store the interpreter's namespace
        self.namespace = {}
        # Create an InteractiveInterpreter instance
        self.interpreter = code.InteractiveInterpreter(self.namespace)

    def name(self) -> str:
        return "python"

    def description(self) -> str:
        return """* python - Execute Python code using an interactive interpreter. For example:
```python
# Import and use modules
import math
print(math.pi)

# Define and use functions
def calculate_area(radius):
    return math.pi * radius ** 2
print(calculate_area(5))
```
The interpreter maintains state between executions, allowing you to:
- Import modules once and reuse them
- Define functions and classes that persist
- Access previously defined variables
- Get detailed error information including stack traces
"""

    async def __call__(self, args: str):
        # Create queues for stdout and stderr
        output_queue = queue.Queue()
        
        class CombinedOutput:
            def __init__(self, queue):
                self.queue = queue
                
            def write(self, text):
                if text:  # Only process non-empty text
                    self.queue.put(text)
                    
            def flush(self):
                pass

        # Save original stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        # Create and set new output captures
        combined_output = CombinedOutput(output_queue)
        sys.stdout = combined_output
        sys.stderr = combined_output

        # Create an event to signal execution completion
        execution_done = threading.Event()
        execution_error = None

        def execute_code():
            nonlocal execution_error
            try:
                # Use runcode which handles multi-line statements, compilation, and execution
                incomplete = self.interpreter.runcode(args)
                if incomplete:
                    execution_error = "Incomplete code block: More input is needed."
            except Exception as e:
                # Capture any exception during compilation or execution
                execution_error = ''.join(traceback.format_exc())
            finally:
                # Signal that execution has finished
                execution_done.set()

        # Use thread pool to execute code
        with ThreadPoolExecutor() as executor:
            executor.submit(execute_code)

        had_output = False
        
        try:
            # Check output queue until execution is complete
            while not execution_done.is_set() or not output_queue.empty():
                try:
                    # Check queue every 100ms
                    output = output_queue.get_nowait()
                    if output.strip():
                        had_output = True
                    yield output
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue

            # If there was an error, yield the error information
            if execution_error:
                yield f"{execution_error}"
                had_output = True
            # Only show success message if there was no output
            elif not had_output:
                yield "Code executed successfully with no output\n"

        finally:
            # Restore original stdout and stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

async def test():
    # Save original stdout
    original_stdout = sys.stdout
    
    def safe_write(text):
        """Safely write to original stdout"""
        original_stdout.write(text)
        original_stdout.flush()
    
    safe_write("Starting PythonInterpreterTool tests\n")
    
    # Create tool instance
    interpreter_tool = PythonInterpreterTool()
    
    # Test cases
    test_cases = [
        ("Test 1 - Simple print", 'print("Hello from interpreter!")'),
        
        ("Test 2 - Mathematical calculation", '''
import math
result = math.sqrt(16)
print(f"Square root of 16 is: {result}")
'''),
        
        ("Test 3 - State persistence", '''
x = 42
print(f"Setting x to {x}")
'''),
        
        ("Test 4 - State verification", '''
print(f"Previously set x value: {x}")
'''),
        
        ("Test 5 - Error handling", '''
def bad_function():
    raise ValueError("This is a test error")
bad_function()
'''),
        
        ("Test 6 - Syntax error", '''
if True
    print("This has invalid syntax")
''')
    ]

    for test_name, code in test_cases:
        safe_write(f"\n=== {test_name} ===\n")
        safe_write(f"Code:\n{code}\n")
        safe_write("Output:\n")
        async for output in interpreter_tool.__call__(code):
            safe_write(output)
        safe_write("\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
