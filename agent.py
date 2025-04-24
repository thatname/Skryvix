
from typing import List, Optional, Tuple, Type, Dict, Any, Union
from jinja2 import Template
import asyncio
import re
import yaml
import importlib
import argparse
import sys
from pathlib import Path
from chat_streamer import ChatStreamer
from tool import Tool
from ask_tool import read_multiline_stdin
import sys
import asyncio
import argparse
from pathlib import Path

original_stdout = sys.stdout
    
def safe_write(text):
    """Safely write to original stdout"""
    original_stdout.write(text)
    original_stdout.flush()
    

class ToolAction(argparse.Action):
    """Custom action to handle --tool arguments"""
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, self.dest):
            setattr(namespace, self.dest, [])
        
        tools = getattr(namespace, self.dest)
        if not values:
            return
            
        # First value is the tool class path
        tool_class = values[0]
        
        # Remaining values are parameters in key=value format
        params = {}
        for param in values[1:]:
            try:
                key, value = param.split('=', 1)
                params[key] = value
            except ValueError:
                parser.error(f'Tool parameters must be in key=value format: {param}')
        
        tools.append({
            'class': tool_class,
            'params': params
        })

class Agent:
    @classmethod
    def create_from_args(cls, args: Union[argparse.Namespace, str]) -> 'Agent':
        """
        Create Agent instance from command line arguments or argument string

        Args:
            args (Union[argparse.Namespace, str]): Either parsed command line arguments 
                or a string of arguments to parse

        Returns:
            Agent: Configured Agent instance

        Raises:
            FileNotFoundError: If any required file is not found
            ImportError: If tool module import fails
        """
        if isinstance(args, str):
            # Create parser
            parser = argparse.ArgumentParser(description='Run the AI agent with specified tools')
            parser.add_argument('--model-config', required=True, help='Path to the model configuration file')
            parser.add_argument('--system-prompt-template', required=True, help='Path to the system prompt template file')
            parser.add_argument('--tool', nargs='+', action=ToolAction, default=[],
                              help='Tool configuration in format: module.ClassName param1=value1 param2=value2')
            parser.add_argument('--task', help='Task description for the agent (reads from stdin if not provided)')
            parser.add_argument('--worker-mode', action="store_true", help='Whether in worker mode')
            
            # Parse the string args
            args = parser.parse_known_args(args.split())[0]
        try:
            # Get the directory containing agent.py
            agent_dir = Path(__file__).parent.absolute()

            # Handle streamer_config path
            model_config_path = Path(args.model_config)
            if not model_config_path.is_absolute():
                model_config_path = agent_dir / model_config_path

            # Create ChatStreamer from config
            chat_streamer = ChatStreamer.create_from_yaml(str(model_config_path))

            # Handle system_prompt_template path
            system_prompt_path = Path(args.system_prompt_template)
            if not system_prompt_path.is_absolute():
                system_prompt_path = agent_dir / system_prompt_path

            # Load tools
            tools = []
            for tool_info in args.tool:
                # Split module and class name
                module_path, class_name = tool_info['class'].rsplit('.', 1)
                
                try:
                    # Import module and get class
                    module = importlib.import_module(module_path)
                    tool_class = getattr(module, class_name)
                    
                    # Create tool instance with parameters
                    tool = tool_class(**tool_info['params'])
                    tools.append(tool)
                except (ImportError, AttributeError) as e:
                    raise ImportError(f"Failed to load tool {tool_info['class']}: {str(e)}")

            # Read system prompt template
            try:
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    system_prompt_template = f.read()
            except FileNotFoundError as e:
                raise FileNotFoundError(f"System prompt template file not found: {system_prompt_path}")

            # Create Agent instance
            return cls(
                chat_streamer=chat_streamer,
                tools=tools,
                system_prompt_template=system_prompt_template
            )
        except Exception as e:
            raise
    def __init__(
        self,
        chat_streamer: ChatStreamer,
        tools: List[Tool],
        system_prompt_template: str
    ):
        """
        Initialize Agent

        Args:
            chat_streamer (ChatStreamer): Instance of ChatStreamer for communication
            tools (List[Tool]): List of available tools
            system_prompt_template (str): Jinja2 template for system prompt
        """
        self.chat_streamer = chat_streamer
        self.tools = tools
        self.system_prompt_template = Template(system_prompt_template)
        
        # Create tool name to tool instance mapping
        self.tool_map = {tool.name(): tool for tool in tools}
        
    def _prepare_system_prompt(self) -> str:
        """
        Prepare system prompt using template and tools
        """
        tool_descriptions = [tool.description() for tool in self.tools]
        return self.system_prompt_template.render(tools=tool_descriptions)
    
    async def _process_tool_call(self, content: str) -> str:
        """
        Process potential tool calls in the content using XML format
        
        Args:
            content (str): Content to process
            
        Yields:
            str: Output characters one by one
            
        Returns:
            str: True if a tool was called, False otherwise
        """
        # Match XML-style tool calls
        tool_pattern = r'```([a-z]*?)\n(.*?)```'
        matches = list(re.finditer(tool_pattern, content, re.DOTALL))
        tool_called = False # Flag to track if any tool was processed

        # Special case: Yield nothing for valid single 'finish' call
        if len(matches) == 1 and matches[0].group(1) == "finish":
            yield ""
            return

        for match in matches:
            tool_called = True # Mark that at least one tool was found
            tool_name = match.group(1)
            args = match.group(2)
            yield f"You invoked tool '{tool_name}'. The result is:\n"            
            if tool_name == "finish":
                # if any matches are 'finish' but there's more than 1 match
                yield "Error: 'finish' tool must be used alone without other tool calls.\n       You can check if the task is really finished, then invoke the finish tool again.\n"
            elif tool_name in self.tool_map:
                tool = self.tool_map[tool_name]
                try:
                    # Process tool output
                    async for output in tool.use(args):
                        yield output

                    # Add newline after tool output
                    yield "\n"

                except Exception as e:
                    yield f"\nError executing tool '{tool_name}': {str(e)}\n"
            else:
                # Handle unknown tool name
                yield f"""Error: ```{tool_name}
         ^ There is no such tool named {tool_name} !!!
"""
                
        if not tool_called:
            # This message is yielded only if the loop did not run (no matches)
            yield """I can not find the tool calling pattern in your response or syntax error!
The correct tool calling format is
```tool_name
# Inside the block, write the code or content.
```
Now you can try again, utilize tools to complete your task!
"""
        
    async def __call__(self, user_task: str):
        """
        Start agent with user task
        
        Args:
            user_task (str): User's task description
            
        Yields:
            str: Response tokens and tool outputs
        """
        try:
            # Set system prompt and configure chat streamer
            self.chat_streamer.system_prompt = self._prepare_system_prompt()
            # self.chat_streamer.stop = ['```\n']  # Tool calling by code
            self.chat_streamer.clear_history()
            
            # Initial prompt is the user's task
            prompt = user_task
            
            # Main conversation loop
            while True:
                buffer = []
                # Stream model's response and accumulate
                async for token, reasoning in self.chat_streamer(prompt):
                    if not reasoning:
                        buffer.append(token)
                    yield token
                yield "\n|||\n"
                
                # Process any tool calls in the response
                prompt = ""
                async for char in self._process_tool_call("".join(buffer)):
                    prompt += char
                    yield char
                
                if prompt != "":
                    yield "\n|||\n"
                else:
                    # No tool call found, end conversation
                    break
                    
        except Exception as e:
            yield f"Exception: {str(e)}"

async def async_main(args: argparse.Namespace):
    """
    Async main function to run the agent
    
    Args:
        args (argparse.Namespace): Parsed command line arguments
    """
    #try:
    agent = Agent.create_from_args(args)
    # Determine the task: use arg or read from stdin
    task_description = args.task
    if not task_description:
        if not args.worker_mode: # Prompt user in active mode (default)
            safe_write("Please enter the task description (end with '@@@' on a new line):")
        # Read from stdin
        task_description = await read_multiline_stdin()
        if not task_description:
            safe_write("Error: No task provided either via --task argument or standard input.")
            sys.exit(1) # Exit if no task is available after trying stdin

    # Call the agent with the determined task
    async for response in agent(task_description):
        safe_write(response)

def main():
    """Main entry point for the agent CLI"""
    #try:
    parser = argparse.ArgumentParser(description='Run the AI agent with specified tools')
    parser.add_argument('--model-config', required=True, help='Path to the model configuration file')
    parser.add_argument('--system-prompt-template', required=True, help='Path to the system prompt template file')
    parser.add_argument('--tool', nargs='+', action=ToolAction, default=[],
                        help='Tool configuration in format: module.ClassName param1=value1 param2=value2')
    # Task argument is now optional, handled in async_main
    parser.add_argument('--task', help='Task description for the agent (reads from stdin if not provided)')
    parser.add_argument('--worker-mode', action="store_true", help='Whether in worker mode')
    args = parser.parse_args()
    # Run the async main function
    asyncio.run(async_main(args))

if __name__ == '__main__':
    main()
