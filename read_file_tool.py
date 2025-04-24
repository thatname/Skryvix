from tool import Tool
import aiofiles
import os
from typing import List, Optional
from chat_streamer import ChatStreamer

class ReadFileTool(Tool):
    def __init__(self, config_path = "model_configs/openrouter.yaml.example"):
        self.chat_streamer = ChatStreamer.create_from_yaml(config_path)
        self.all_files = self._get_all_files_recursive()
        
    def _get_all_files_recursive(self) -> List[str]:
        file_list = []
        for root, _, files in os.walk('.'):
            for file in files:
                file_list.append(os.path.join(root, file))
        return file_list
        
    async def _fuzzy_match(self, filename: str) -> Optional[str]:
        prompt = f"""Find the closest match to '{filename}' from these files:
{'\n'.join(self.all_files)}
Respond with just the best matching filename."""
        
        best_match = ""
        async for chunk, _ in self.chat_streamer(prompt):
            best_match += chunk
            
        return best_match.strip() if best_match else None

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
                matched = await self._fuzzy_match(path)
                if matched:
                    try:
                        async with aiofiles.open(matched, mode='r', encoding='utf-8') as f:
                            content = await f.read()
                            yield f"Matched: {matched}\n{content}"
                    except Exception as e:
                        yield f"Error reading matched file {matched}: {str(e)}"
                else:
                    yield f"Error: File not found - {path}"
            except PermissionError:
                yield f"Error: Permission denied - {path}"
            except Exception as e:
                yield f"Error reading {path}: {str(e)}"
