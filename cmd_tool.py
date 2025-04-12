
import os
from subprocess_tool import SubProcessTool

class CmdTool(SubProcessTool):
    """
    Command line tool class for executing shell commands.
    Inherits from SubProcessTool to handle subprocess management.
    """
    
    def __init__(self):
        """
        Initialize command line tool with appropriate shell command and end marker.
        """
        self.is_windows = os.name == 'nt'
        shell_cmd = 'cmd.exe /K chcp 65001' if self.is_windows else 'bash'
        command_end_marker = '>' if self.is_windows else '$'
        super().__init__(shell_cmd, command_end_marker)

    def name(self) -> str:
        """
        Returns the tool's name based on the operating system.

        Returns:
            str: Tool name ('cmd' for Windows, 'bash' for Unix-like systems)
        """
        return "cmd" if self.is_windows else "bash"

    def description(self) -> str:
        """
        Returns the tool's description based on the operating system.

        Returns:
            str: Tool description
        """
        if self.is_windows:
            return """* cmd - Windows command prompt. Example:
```cmd
dir
git add -A
git commit -m "feat: add splash screen (#173)"
```
Response of this tool will include all the file names inside current direction, followed by the git commit result.
"""
        else:
            return """* bash - Unix shell. Example:
```bash
ls
git add -A
git commit -m "feat: add splash screen (#173)"
```
Response of this tool will include all the file names inside current directory, followed by the git commit result.
"""


async def main():
    # Create command line tool instance
    cmd_tool = CmdTool()
    
    # Print tool description
    print("Tool description:", cmd_tool.description())
    print("\n" + "="*50 + "\n")

    # Test some basic commands
    commands = [
        "echo Hello, World!",
        "dir" if os.name == 'nt' else "ls",  # List directory contents
        "type cmd_tool.py" if os.name == 'nt' else "cat cmd_tool.py",  # View file contents
    ]

    # Execute each test command
    for cmd in commands:
        print(f"Executing command: {cmd}")
        print("-" * 30)
        # Use async for loop to process each character output
        async for char in cmd_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())