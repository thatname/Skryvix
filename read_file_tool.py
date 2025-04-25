from tool import Tool
import aiofiles
from find_file_tool import FindFileTool
from agent import Agent

class ReadFileTool(Tool):
    def __init__(self, config_path: str):
        """Initialize ReadFileTool with a configuration path.
        
        Args:
            config_path (str): Path to the configuration file
        """
        self.config_path = config_path
        # FindFileTool will be initialized when needed to ensure Agent is properly configured
        self.find_tool = None
        
    def _ensure_find_tool(self):
        if self.find_tool is None:
            agent = Agent.create_from_yaml(self.config_path)
            self.find_tool = FindFileTool(agent)

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
        self._ensure_find_tool()
        file_paths = args.split('\n')
        for path in file_paths:
            path = path.strip()
            if not path:
                continue
                
            try:
                async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                    yield f"File: {path}\n{content}"
            except FileNotFoundError:
                # Try to find the file using FindFileTool
                async for matched in self.find_tool.__call__(path):
                    if not matched.startswith("Error"):
                        try:
                            async with aiofiles.open(matched, mode='r', encoding='utf-8') as f:
                                content = await f.read()
                                yield f"Matched: {matched}\n{content}"
                        except Exception as e:
                            yield f"Error reading matched file {matched}: {str(e)}"
                    else:
                        yield matched
            except PermissionError:
                yield f"Error: Permission denied - {path}"
            except Exception as e:
                yield f"Error reading {path}: {str(e)}"