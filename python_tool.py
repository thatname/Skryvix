
from subprocess_tool import SubProcessTool

class PythonTool(SubProcessTool):
    """
    Python interactive shell tool class.
    Inherits from SubProcessTool to handle subprocess management.
    """
    
    def __init__(self):
        """
        Initialize Python tool with appropriate command and end marker.
        """
        shell_cmd = 'python -i'  # Python interactive mode
        command_end_marker = '>>> '  # Python REPL prompt
        super().__init__(shell_cmd, command_end_marker)

    def name(self) -> str:
        """
        Returns the tool's name.

        Returns:
            str: Tool name
        """
        return "python"

    def description(self) -> str:
        """
        Returns the tool's description.

        Returns:
            str: Tool description
        """
        return """* python - Python Interactive Shell. Example:
```python
x = 1 + 1
print(x)
import math
print(math.pi)
[i * 2 for i in range(5)]
```invoke
This tool provides an interactive Python shell for executing Python code and expressions.
"""


async def main():
    # Create Python tool instance
    python_tool = PythonTool()
    
    # Print tool description
    print("Tool description:", python_tool.description())
    print("\n" + "="*50 + "\n")

    # Test case 1: Basic arithmetic
    print("Test case 1: Basic arithmetic")
    commands = [
        "2 + 2",
        "3 * 4",
        "10 / 2"
    ]
    for cmd in commands:
        print(f"Executing: {cmd}")
        print("-" * 30)
        async for char in python_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

    # Test case 2: Variable assignment and usage
    print("Test case 2: Variable assignment and usage")
    commands = [
        "x = 42",
        "x * 2",
        "x + 8"
    ]
    for cmd in commands:
        print(f"Executing: {cmd}")
        print("-" * 30)
        async for char in python_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

    # Test case 3: List operations
    print("Test case 3: List operations")
    commands = [
        "lst = [1, 2, 3, 4, 5]",
        "lst.append(6)",
        "lst",
        "[x * 2 for x in lst]"
    ]
    for cmd in commands:
        print(f"Executing: {cmd}")
        print("-" * 30)
        async for char in python_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

    # Test case 4: Import and use module
    print("Test case 4: Import and use module")
    commands = [
        "import math",
        "math.pi",
        "math.cos(0)",
        "math.sin(math.pi/2)"
    ]
    for cmd in commands:
        print(f"Executing: {cmd}")
        print("-" * 30)
        async for char in python_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

    # Test case 5: String operations
    print("Test case 5: String operations")
    commands = [
        's = "Hello, World!"',
        'len(s)',
        's.upper()',
        's.split(", ")'
    ]
    for cmd in commands:
        print(f"Executing: {cmd}")
        print("-" * 30)
        async for char in python_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())