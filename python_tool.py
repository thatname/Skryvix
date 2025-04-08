
from tool import Tool
import sys
from io import StringIO

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

    def use(self, args: str) -> str:
        # 保存原始的标准输出
        old_stdout = sys.stdout
        # 创建StringIO对象来捕获输出
        redirected_output = StringIO()
        sys.stdout = redirected_output

        try:
            # 执行Python代码
            exec(args)
            # 获取捕获的输出
            output = redirected_output.getvalue()
            return output if output else "Python code executed successfully, no output"
        except Exception as e:
            return f"Execution error: {str(e)}"
        finally:
            # 恢复原始的标准输出
            sys.stdout = old_stdout
            redirected_output.close()



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