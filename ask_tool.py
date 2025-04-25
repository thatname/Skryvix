
from tool import Tool
import sys
import asyncio

async def read_multiline_stdin() -> str:
    """
    Reads multiline input from standard input until '@@@'.
    Returns the collected input as a string with the terminator removed.
    """
    lines = []
    while True:
        try:
            line = sys.stdin.readline()
            if line.endswith("@@@\n"):
                # Remove the trailing '@@@\n' before breaking
                lines.append(line[:-4])
                break
            if not line:  # EOF
                break
            lines.append(line)
        except EOFError:
            break
    return "".join(lines).strip()

class AskTool(Tool):
    """
    A tool for prompting users for input during agent interactions.
    Supports multiline input terminated by '@@@' on a new line.
    """

    def name(self) -> str:
        """
        Returns the name of the tool.
        
        Returns:
            str: The tool name 'ask'
        """
        return "ask"

    def description(self) -> str:
        """
        Returns the description of how to use the tool.
        
        Returns:
            str: Detailed description of the tool's usage
        """
        return """* ask - Prompt user for input and collect their response. For example:
```ask
Please enter your name:
```
The tool will:
- Display the specified prompt to the user
- Wait for user input (can be multiple lines)
- User must end their input with '@@@' on a new line
- Return the collected input for further processing

Example usage:
```ask
What programming languages do you know?
Please list them one per line:
```
"""

    async def __call__(self, args: str):
        """
        Prompts the user with the given message and collects their input.
        
        Args:
            args (str): The prompt message to display to the user
            
        Yields:
            str: First yields the prompt, then yields the user's input
        """
        try:
            # Display the prompt to the user
            yield f"{args}\n@@@\n"
            
            # Collect user input
            user_input = await read_multiline_stdin()
            
            # Yield the collected input
            yield f"Received input:\n{user_input}\n"
            
        except Exception as e:
            yield f"Error collecting user input: {str(e)}\n"

# Test code
async def test():
    """
    Test function to verify the AskTool functionality.
    """
    tool = AskTool()
    print("Testing AskTool...")
    print("\nTool name:", tool.name())
    print("\nTool description:")
    print(tool.description())
    print("\nTesting use method:")
    async for output in tool.__call__("Please enter your test input (end with @@@):"):
        print(output, end='')

if __name__ == "__main__":
    asyncio.run(test())