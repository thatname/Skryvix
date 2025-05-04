from tool import Tool
import os
from typing import List, Optional
from agent import Agent

class FindFileTool(Tool):
    def __init__(self, agent: Agent):
        self.agent = agent
        
    def _get_all_files_recursive(self) -> List[str]:
        file_list = []
        for root, _, files in os.walk('.'):
            for file in files:
                file_list.append(os.path.join(root, file))
        return file_list
        
    async def _fuzzy_match(self, filename: str) -> Optional[str]:
        all_files = self._get_all_files_recursive()
        prompt = f"""Find the closest match to '{filename}' from these files:
{'\n'.join(all_files)}
Respond with just the best matching filename."""
        
        response = await self.agent(prompt)
        return response.strip() if response else None

    def name(self) -> str:
        return "find_file"
    
    def description(self) -> str:
        return """* find_file - Finds a file in the current directory and its subdirectories using fuzzy matching. Example:
```find_file
path/to/file.txt
```
Returns the path of the best matching file if found, or an error message if not found.
"""
    
    async def __call__(self, args: str):
        filename = args.strip()
        if not filename:
            yield "Error: No filename provided"
            return
            
        try:
            # First try exact match
            if os.path.exists(filename):
                yield filename
                return
                
            # If not found, try fuzzy matching
            #matched = await self._fuzzy_match(filename)
            #if matched and os.path.exists(matched):
            #    yield matched
            #else:
            #    yield f"Error: File not found - {filename}"
        except Exception as e:
            yield f"Error finding file {filename}: {str(e)}"