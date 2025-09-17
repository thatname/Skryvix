from tool import Tool
import aiofiles
from find_file_tool import FindFileTool
from agent import Agent
from file_manager import FileManager

class ReadFileTool(Tool):
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager

    def name(self) -> str:
        return "read_file"
    
    def description(self) -> str:
        return """* read_file - Reads one or more files. Example:
```read_file
path/to/file1.txt
path/to/file2.txt
```
The content of the files will be shown to you in the last message.
"""
    
    async def __call__(self, args: str):
        file_paths = args.split('\n')
        for path in file_paths:
            path = path.strip()
            if not path:
                continue
            try:
                await self.file_manager.read_file(path)
                yield f"Successfully read the file {path}"
            except Exception as e:
                yield f"Error reading {path}: {str(e)}"
