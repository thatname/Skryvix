
from typing import List, Optional, Tuple, Type, Dict, Any, Union
from jinja2 import Template
import asyncio
import re
import yaml
import importlib
from pathlib import Path
from chat_streamer import ChatStreamer
from tool import Tool

class Agent:
    @classmethod
    def create(cls, config_path: Union[str, Path]) -> 'Agent':
        """
        Create Agent instance from configuration file

        Args:
            config_path (Union[str, Path]): Path to the configuration file

        Returns:
            Agent: Configured Agent instance

        Raises:
            FileNotFoundError: If any required file is not found
            ImportError: If tool module import fails
            yaml.YAMLError: If YAML parsing fails
        """
        # Convert path to Path object
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Read and parse main configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Create ChatStreamer from config
        streamer_config_path = config_path.parent / config['streamer_config']
        chat_streamer = ChatStreamer.create_from_yaml(streamer_config_path)

        # Load tools
        tools = []
        for tool_info in config['tools']:
            # Split module and class name
            module_path, class_name = tool_info['class'].rsplit('.', 1)
            
            try:
                # Import module and get class
                module = importlib.import_module(module_path)
                tool_class = getattr(module, class_name)
                
                # Create tool instance with optional parameters
                tool_params = tool_info.get('params', {})
                tool = tool_class(**tool_params)
                tools.append(tool)
            except (ImportError, AttributeError) as e:
                raise ImportError(f"Failed to load tool {tool_info['class']}: {str(e)}")

        # Read system prompt template
        try:
            with open(config_path.parent / config['system_prompt_template'], 'r', encoding='utf-8') as f:
                system_prompt_template = f.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"System prompt template file not found: {str(e)}")

        # Create Agent instance
        return cls(
            chat_streamer=chat_streamer,
            tools=tools,
            system_prompt_template=system_prompt_template
        )

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
    
    async def _process_tool_call(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Process potential tool calls in the content using XML format
        
        Args:
            content (str): Content to process
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (Tool execution result, Remaining content after tool call)
                                               or (None, None) if no tool call found
        """
        # Match XML-style tool calls
        tool_pattern = r'```(.*?)\n(.*?)```\n'
        match = re.search(tool_pattern, content, re.DOTALL)
        if match:
            tool_name = match.group(1).strip()
            args = match.group(2)
            
            if tool_name in self.tool_map:
                tool = self.tool_map[tool_name]
                try:
                    result = tool.use(args)
                    return f"You invoked tool {tool_name}, result is:\n" + result
                except Exception as e:
                    return f"Error executing tool {tool_name}: {str(e)}"
                    
        return None
        
    async def __call__(self, user_task: str):
        """
        Start agent with user task
        
        Args:
            user_task (str): User's task description
        """
        # assert user_task.endswith("\n|||\n")
        # Set system prompt
        self.chat_streamer.system_prompt = self._prepare_system_prompt()
        self.chat_streamer.stop = ['```\n'] # Tool calling by code.
        # Clear chat history
        self.chat_streamer.clear_history()
        
        # Prepare initial user prompt
        prompt = user_task
        
        # Start streaming conversation
        while True:
            buffer = ""
            
            async for token in self.chat_streamer(prompt):
                buffer += token
                yield token
            yield "\n|||\n"
            
            #if buffer.endswith("`"):
            result = await self._process_tool_call(buffer + '```\n')
            if result:
                prompt = result
                yield prompt + "\n|||\n"
            else:
                break
        
        print(buffer)
