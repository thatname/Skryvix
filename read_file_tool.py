from tool import Tool
import aiofiles
from find_file_tool import FindFileTool
from agent import Agent

class ReadFileTool(Tool):
    def __init__(self):#, find_tool: FindFileTool):
        """Initialize ReadFileTool with a configuration path.
        
        Args:
            config_path (str): Path to the configuration file
        """
        #self.find_tool = find_tool

    def name(self) -> str:
        return "read_file"
    
    def description(self) -> str:
        return """* read_file - Reads one or more files and yields their contents. Example:
```read_file
path/to/file1.txt
path/to/file2.txt
```
Yields each file's content sequentially. Handles both relative and absolute paths.
Automatically attempts fuzzy matching if file not found.
"""
    
    async def __call__(self, args: str):
        file_paths = args.split('\n')
        for path in file_paths:
            path = path.strip()
            if not path:
                continue
                
            try:
                yield f"```Content of {path}\n"
                async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                    async for line in f:
                        yield line
                yield f"```\n\n"
            #except FileNotFoundError:
            #    # Try to find the file using FindFileTool
            #    async for matched in self.find_tool.__call__(path):
            #        if not matched.startswith("Error"):
            #            try:
            #                async with aiofiles.open(matched, mode='r', encoding='utf-8') as f:
            #                    content = await f.read()
            #                    yield f"Matched: {matched}\n{content}"
            #            except Exception as e:
            #                yield f"Error reading matched file {matched}: {str(e)}"
            #        else:
            #            yield matched
            except Exception as e:
                yield f"Error reading {path}: {str(e)}"