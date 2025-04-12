
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

import sys
import asyncio
import argparse
from pathlib import Path

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
    def create_from_args(cls, args: argparse.Namespace) -> 'Agent':
        """
        Create Agent instance from command line arguments

        Args:
            args (argparse.Namespace): Parsed command line arguments

        Returns:
            Agent: Configured Agent instance

        Raises:
            FileNotFoundError: If any required file is not found
            ImportError: If tool module import fails
        """
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
        tool_pattern = r'```(.*?)\n(.*?)```invoke'
        match = re.search(tool_pattern, content, re.DOTALL)
        if match:
            tool_name = match.group(1)
            args = match.group(2).strip()
            if tool_name == "final":
                yield ""
            elif tool_name in self.tool_map:
                tool = self.tool_map[tool_name]
                
                try:
                    # Start message
                    yield f"You invoked tool '{tool_name}' result is:\n"

                    # Process tool output
                    async for output in tool.use(args):
                        for char in output:
                            yield char

                    # Add newline after tool output
                    yield "\n"

                except Exception as e:
                    yield f"\nError executing tool '{tool_name}': {str(e)}\n"
            else:
                yield f"""Error: The tool name "{tool_name}" is wrong."""
        else:
            yield """I can not find the tool calling pattern in your response or syntax error!
The correct tool calling format is
```tool_name
# Inside the block, write the code or content.
```invoke
Remember the 'invoke' at the end!
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
                buffer = ""
                # Stream model's response and accumulate
                async for token, reasoning in self.chat_streamer(prompt):
                    if not reasoning:
                        buffer += token
                    yield token
                yield "\n|||\n"
                
                # Process any tool calls in the response
                prompt = ""
                async for char in self._process_tool_call(buffer + '```\n'):
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
    async for response in agent(args.task):
        print(response, end='', flush=True)
    #except Exception as e:
    #    print(f"Error in async_main: {str(e)}", file=sys.stderr)
    #    raise  # Re-raise the exception to be caught by main()

def main():
    """Main entry point for the agent CLI"""
    #try:
    parser = argparse.ArgumentParser(description='Run the AI agent with specified tools')
    parser.add_argument('--model-config', required=True, help='Path to the model configuration file')
    parser.add_argument('--system-prompt-template', required=True, help='Path to the system prompt template file')
    parser.add_argument('--tool', nargs='+', action=ToolAction, default=[], 
                        help='Tool configuration in format: module.ClassName param1=value1 param2=value2')
    parser.add_argument('--task', required=True, help='Task description for the agent')
    
    args = parser.parse_args()
    # Run the async main function
    asyncio.run(async_main(args))
    #except Exception as e:
    #    print(f"Error: {str(e)}", file=sys.stderr)
    #    sys.exit(1)

if __name__ == '__main__':
    main()