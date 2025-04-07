
from cmd_tool import CmdTool

def main():
    # Create command line tool instance
    cmd_tool = CmdTool()
    
    # Print tool description
    print("Tool description:", cmd_tool.description())
    print("\n" + "="*50 + "\n")

    # Test some basic commands
    commands = [
        "echo Hello, World!",
        "dir",  # List directory contents on Windows
        "type cmd_tool.py",  # View file contents on Windows
    ]

    # Execute each test command
    for cmd in commands:
        print(f"Executing command: {cmd}")
        print("-" * 30)
        result = cmd_tool.use(cmd)
        print(result)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()