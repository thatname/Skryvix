
from subprocess_tool import SubProcessTool

class LLDBTool(SubProcessTool):
    """
    LLDB debugger tool class for debugging applications.
    Inherits from SubProcessTool to handle subprocess management.
    """
    
    def __init__(self):
        """
        Initialize LLDB tool with appropriate command and end marker.
        """
        shell_cmd = 'lldb'  # LLDB debugger command
        command_end_marker = ''# '(lldb) '  # LLDB prompt
        super().__init__(shell_cmd, command_end_marker)

    def name(self) -> str:
        """
        Returns the tool's name.

        Returns:
            str: Tool name
        """
        return "lldb"

    def description(self) -> str:
        """
        Returns the tool's description.

        Returns:
            str: Tool description
        """
        return """* lldb - LLDB Debugger. Example:
```lldb
file ./myprogram  # Load program
breakpoint set --name main  # Set breakpoint at main function
run  # Run program
frame variable  # Display variables in current frame
next  # Step over
continue  # Continue execution
quit  # Exit debugger
```
This tool provides an interactive interface to the LLDB debugger for debugging C/C++/Objective-C programs.
"""


async def main():
    # Create LLDB tool instance
    lldb_tool = LLDBTool()
    
    # Print tool description
    print("Tool description:", lldb_tool.description())
    print("\n" + "="*50 + "\n")

    # Test some basic commands
    commands = [
        "version",  # Show LLDB version
        "help",  # Show help information
        """script
import sys
print(sys.version)
        """
    ]

    # Execute each test command
    for cmd in commands:
        print(f"Executing command: {cmd}")
        print("-" * 30)
        # Use async for loop to process each character output
        async for char in lldb_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())