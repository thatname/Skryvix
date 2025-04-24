from tool import Tool
import aiofiles
import os

class ReadFileTool(Tool):
    def name(self) -> str:
        return "read_file"
    
    def description(self) -> str:
        return """* read_file - Reads one or more files and reads their contents. Example:
```read_file
path/to/file1.txt
path/to/file2.txt
```
Reads each file's content sequentially. Handles both relative and absolute paths.
"""
    
    async def use(self, args: str):
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
                yield f"Error: File not found - {path}"
            except PermissionError:
                yield f"Error: Permission denied - {path}"
            except Exception as e:
                yield f"Error reading {path}: {str(e)}"
