import aiofiles
import os

class FileManager:
    def __init__(self):
        self.cache = {}
    
    async def read_file(self, path: str):
        """Read file content with caching.
        
        Args:
            path: Relative or absolute file path
            
        Returns:
            Content of the file 
        """
        # Resolve absolute path
        abs_path = os.path.abspath(path)
        
        # Check cache first
        if abs_path in self.cache:
            return self.cache[abs_path]
        else:

            async with aiofiles.open(abs_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                self.cache[abs_path] = content
                return content

    async def write_file(self, path: str, content: str):
        """Write content to a file.
        
        Args:
            path: Relative or absolute file path
            content: Content to write
        """          
        # Resolve absolute path
        abs_path = os.path.abspath(path)

        async with aiofiles.open(abs_path, mode='w', encoding='utf-8') as f:
            await f.write(content)
            
        # Update cache with the new content
        self.cache[abs_path] = content

    def clear_cache(self):
        """Clear the file cache."""
        self.cache.clear()
