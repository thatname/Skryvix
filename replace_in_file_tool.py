from tool import Tool
import aiofiles
import re


class ReplaceInFileTool(Tool):
    def __init__(self):
        """Initialize ReplaceInFileTool"""
        pass

    def name(self) -> str:
        return "replace_in_file"
    
    def description(self) -> str:
        return """* replace_in_file - Replaces content in a file using SEARCH/REPLACE blocks. Example:
```replace_in_file
path/to/file.txt
<<<<<<< SEARCH
content to find
=======
content to replace with
>>>>>>> REPLACE
```
Replaces the first occurrence of the search content with the replacement content.
"""

    async def __call__(self, args: str):
        lines = args.strip().split('\n')
        if not lines:
            yield "Error: Empty input"
            return
            
        file_path = lines[0].strip()
        if not file_path:
            yield "Error: No file path provided"
            return

        # Read file content
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
        except FileNotFoundError:
            yield f"Error: File not found: {file_path}"
            return
        except Exception as e:
            yield f"Error reading file {file_path}: {str(e)}"
            return

        # Parse and apply SEARCH/REPLACE blocks
        current_pos = 1
        modified = False
        while current_pos < len(lines):
            try:
                # Find start of SEARCH block
                while current_pos < len(lines) and not lines[current_pos].strip() == "<<<<<<< SEARCH":
                    current_pos += 1
                if current_pos >= len(lines):
                    break
                
                search_lines = []
                current_pos += 1
                
                # Collect SEARCH content
                while current_pos < len(lines) and not lines[current_pos].strip() == "=======":
                    search_lines.append(lines[current_pos])
                    current_pos += 1
                if current_pos >= len(lines):
                    yield "Error: Unclosed SEARCH block"
                    return
                
                replace_lines = []
                current_pos += 1
                
                # Collect REPLACE content
                while current_pos < len(lines) and not lines[current_pos].strip() == ">>>>>>> REPLACE":
                    replace_lines.append(lines[current_pos])
                    current_pos += 1
                if current_pos >= len(lines):
                    yield "Error: Unclosed REPLACE block"
                    return
                
                # Perform replacement
                search_content = '\n'.join(search_lines)
                replace_content = '\n'.join(replace_lines)
                
                # Escape special regex characters in search string
                search_escaped = re.escape(search_content)
                # Replace newlines with regex pattern that matches both \n and \r\n
                search_escaped = search_escaped.replace('\\\n', '\\r?\\n')
                
                pattern = re.compile(search_escaped, re.MULTILINE)
                new_content, count = pattern.subn(replace_content, content, count=1)
                
                if count > 0:
                    content = new_content
                    modified = True
                else:
                    yield f"Warning: Search content not found:\n{search_content}\n"
                
                current_pos += 1
                
            except Exception as e:
                yield f"Error processing SEARCH/REPLACE block: {str(e)}"
                return

        if not modified:
            yield "No replacements were made"
            return

        # Write modified content back to file
        try:
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write(content)
            yield f"Successfully updated {file_path}"
        except Exception as e:
            yield f"Error writing to file {file_path}: {str(e)}"