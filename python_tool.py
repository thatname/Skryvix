
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
```invoke
The python interpreter is persistent, You can reuse python funciton you've already written. 
In order to complete your development task, you can write python code to manipulate the code within this repository's source files.
"""

    async def use(self, args: str):
        # Create pipe for output capture
        r, w = os.pipe()
        # Save original stdout
        old_stdout = sys.stdout
        # Create StringIO object to capture output
        redirected_output = StringIO()
        sys.stdout = redirected_output

        try:
            # Execute Python code
            exec(args)
            # Get captured output
            output = redirected_output.getvalue()
            if not output:
                output = "Python code executed successfully, no output"
        except Exception as e:
            output = f"Exception : {str(e)}"
        finally:
            # Restore original stdout
            sys.stdout = old_stdout
            redirected_output.close()
        yield output

def test():
    print("Entering main function")
    # Create PythonTool instance
    python_tool = PythonTool()
    
    # Display tool description
    print("Tool description:", python_tool.description())
    print("\n=== Test Cases ===\n")

    # Test case 1: Simple print
    print("Test 1 - Simple print:")
    code1 = 'print("Hello, Python Tool!")'
    print("Code:", code1)
    print("Output:", python_tool.use(code1))
    print()

    # Test case 2: Multiple lines of code
    print("Test 2 - Multiple lines of code:")
    code2 = '''
for i in range(3):
    print(f"Count: {i}")
'''
    print("Code:", code2)
    print("Output:", python_tool.use(code2))
    print()

    # Test case 3: Mathematical calculation
    print("Test 3 - Mathematical calculation:")
    code3 = '''
result = 0
for i in range(1, 5):
    result += i
print(f"Sum of 1 to 4 is: {result}")
'''
    print("Code:", code3)
    print("Output:", python_tool.use(code3))
    print()

    # Test case 4: Error handling
    print("Test 4 - Error handling:")
    code4 = 'print(undefined_variable)'
    print("Code:", code4)
    print("Output:", python_tool.use(code4))

if __name__ == "__main__":
    print("Program started")
    test()
    print("Program ended")