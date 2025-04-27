
from typing import List
from jinja2 import Template
import asyncio
import re
import argparse
import sys
from chat_streamer import ChatStreamer
from tool import Tool
from ask_tool import read_multiline_stdin
import sys
import asyncio

original_stdout = sys.stdout
    
def safe_write(text):
    """Safely write to original stdout"""
    original_stdout.write(text)
    original_stdout.flush()

class Agent(Tool):
    def __init__(
        self,
        chat_streamer: ChatStreamer,
        tools: List[Tool],
        system_prompt_template: Template
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
        self.system_prompt_template = system_prompt_template
        
        # Create tool name to tool instance mapping
        self.tool_map = {tool.name(): tool for tool in tools}
    
    def name(self) -> str:
        """
        Get the name identifier for this agent
        
        Returns:
            str: The agent's name identifier
        """
        return "agent"
    
    def description(self) -> str:
        """
        Get the description of this agent's capabilities
        
        Returns:
            str: Detailed description of the agent's capabilities
        """
        return "A general-purpose agent that can handle various tasks. Can understand requirements, coordinate multiple tools, and solve different types of problems effectively."
        
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
                    async for output in tool.__call__(args):
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
                async for token, reasoning in self.chat_streamer.chat(prompt):
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