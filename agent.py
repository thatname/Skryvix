
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

        # Read prompt templates
        try:
            with open(config_path.parent / config['system_prompt_template'], 'r', encoding='utf-8') as f:
                system_prompt_template = f.read()
            with open(config_path.parent / config['user_prompt_template'], 'r', encoding='utf-8') as f:
                user_prompt_template = f.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Prompt template file not found: {str(e)}")

        # Create Agent instance
        return cls(
            chat_streamer=chat_streamer,
            tools=tools,
            system_prompt_template=system_prompt_template,
            user_prompt_template=user_prompt_template
        )

    def __init__(
        self,
        chat_streamer: ChatStreamer,
        tools: List[Tool],
        system_prompt_template: str,
        user_prompt_template: str
    ):
        """
        Initialize Agent

        Args:
            chat_streamer (ChatStreamer): Instance of ChatStreamer for communication
            tools (List[Tool]): List of available tools
            system_prompt_template (str): Jinja2 template for system prompt
            user_prompt_template (str): Jinja2 template for user prompt
        """
        self.chat_streamer = chat_streamer
        self.tools = tools
        self.system_prompt_template = Template(system_prompt_template)
        self.user_prompt_template = Template(user_prompt_template)
        
        # Create tool name to tool instance mapping
        self.tool_map = {tool.__class__.__name__: tool for tool in tools}
        
    def _prepare_system_prompt(self) -> str:
        """
        Prepare system prompt using template and tools
        """
        tool_descriptions = [tool.description() for tool in self.tools]
        return self.system_prompt_template.render(tools=tool_descriptions)
        
    def _prepare_user_prompt(self, task: str) -> str:
        """
        Prepare user prompt using template and task
        """
        return self.user_prompt_template.render(task=task)
    
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
        tool_pattern = r'<(\w+)>(.*?)</\1>'
        match = re.search(tool_pattern, content, re.DOTALL)
        
        if match:
            tool_name = match.group(1)
            args = match.group(2).strip()
            
            if tool_name in self.tool_map:
                tool = self.tool_map[tool_name]
                try:
                    result = tool.use(args)
                    # Return result and remaining content after tool call
                    remaining = content[match.end():]
                    return result, remaining
                except Exception as e:
                    return f"Error executing tool {tool_name}: {str(e)}", content[match.end():]
                    
        return None, None
        
    async def start(self, user_task: str):
        """
        Start agent with user task
        
        Args:
            user_task (str): User's task description
        """
        # Set system prompt
        self.chat_streamer.system_prompt = self._prepare_system_prompt()
        
        # Clear chat history
        self.chat_streamer.clear_history()
        
        # Prepare initial user prompt
        initial_prompt = self._prepare_user_prompt(user_task)
        
        # Start streaming conversation
        buffer = ""
        async for token in self.chat_streamer(initial_prompt):
            buffer += token
            # Check for complete tool calls
            if '>' in token:  # Potential end of XML tag
                result, remaining = await self._process_tool_call(buffer)
                if result:
                    # Feed tool result back to chat
                    buffer = remaining or ""  # Use remaining content or empty string
                    async for response_token in self.chat_streamer(f"Tool execution result: {result}"):
                        yield response_token
            yield token
            
    async def query(self, message: str):
        """
        Query agent with a message
        
        Args:
            message (str): Message to send to agent
        """
        buffer = ""
        async for token in self.chat_streamer(message):
            buffer += token
            # Check for complete tool calls
            if '>' in token:  # Potential end of XML tag
                result, remaining = await self._process_tool_call(buffer)
                if result:
                    # Feed tool result back to chat
                    buffer = remaining or ""  # Use remaining content or empty string
                    async for response_token in self.chat_streamer(f"Tool execution result: {result}"):
                        yield response_token
            yield token