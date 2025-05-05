from tool import Tool
import aiofiles
import re


class ReplaceInFileTool(Tool):
    def __init__(self):
        """Initialize ReplaceInFileTool"""
        pass

    def name(self) -> str:
        return "replace_in_files"
    
    def description(self) -> str:
        return """* replace_in_files -  A tool for making precise content replacements in one or multiple files using SEARCH/REPLACE blocks. Example:
```replace_in_files
path/to/file1.tsx
<<<<<<< SEARCH
old function name
=======
new function name
>>>>>>> REPLACE
<<<<<<< SEARCH
old variable name
=======
new variable name
>>>>>>> REPLACE
src/component2.tsx
<<<<<<< SEARCH
interface Props {
=======
interface ComponentProps {
>>>>>>> REPLACE
```
Replaces the first occurrence of the search content with the replacement content.
"""

    async def __call__(self, args: str):
        lines = args.strip().split('\n')
        if not lines:
            yield "Error: Empty input"
            return

        # Initialize overall statistics
        total_files = 0
        total_replacements = 0
        total_blocks = 0
        overall_report = []

        current_pos = 0
        while current_pos < len(lines):
            # Skip empty lines
            while current_pos < len(lines) and not lines[current_pos].strip():
                current_pos += 1
            if current_pos >= len(lines):
                break

            # Check if this line is a file path (not a SEARCH block)
            if not lines[current_pos].strip().startswith("<<<<<<< SEARCH"):
                file_path = lines[current_pos].strip()
                if not file_path:
                    current_pos += 1
                    continue

                # Initialize per-file tracking
                successful_replacements = 0
                messages = []
                block_number = 0
                modified = False

                # Read file content
                try:
                    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                        content = await f.read()
                except FileNotFoundError:
                    overall_report.append(f"\nError: File not found: {file_path}")
                    current_pos += 1
                    continue
                except Exception as e:
                    overall_report.append(f"\nError reading file {file_path}: {str(e)}")
                    current_pos += 1
                    continue

                current_pos += 1
                total_files += 1

                # Process SEARCH/REPLACE blocks for this file
                while current_pos < len(lines):
                    try:
                        # Check if we've reached a new file path
                        if current_pos < len(lines) and lines[current_pos].strip() and not lines[current_pos].strip().startswith("<<<<<<< SEARCH"):
                            break

                        # Find start of SEARCH block
                        while current_pos < len(lines) and not lines[current_pos].strip() == "<<<<<<< SEARCH":
                            current_pos += 1
                        if current_pos >= len(lines):
                            break

                        block_number += 1
                        total_blocks += 1
                        search_lines = []
                        current_pos += 1

                        # Collect SEARCH content
                        while current_pos < len(lines) and not lines[current_pos].strip() == "=======":
                            search_lines.append(lines[current_pos])
                            current_pos += 1
                        if current_pos >= len(lines):
                            overall_report.append(f"\nError in {file_path}: Unclosed SEARCH block")
                            break

                        replace_lines = []
                        current_pos += 1

                        # Collect REPLACE content
                        while current_pos < len(lines) and not lines[current_pos].strip() == ">>>>>>> REPLACE":
                            replace_lines.append(lines[current_pos])
                            current_pos += 1
                        if current_pos >= len(lines):
                            overall_report.append(f"\nError in {file_path}: Unclosed REPLACE block")
                            break

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
                            successful_replacements += 1
                            total_replacements += 1
                            messages.append(f"Block {block_number}: Successfully replaced content")
                        else:
                            messages.append(f"Block {block_number}: Warning - Search content not found")

                        current_pos += 1

                    except Exception as e:
                        overall_report.append(f"\nError processing SEARCH/REPLACE block {block_number} in {file_path}: {str(e)}")
                        break

                # Write modified content back to file if any changes were made
                if modified:
                    try:
                        async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                            await f.write(content)
                        
                        # Add file report to overall report
                        overall_report.append(f"\n```{file_path}```")
                        overall_report.append(f"""Replacements made in {file_path}: {successful_replacements}/{block_number}
After change, the file content
```
<-- -->
```
""")
                        overall_report.append("Detailed results:")
                        overall_report.extend(["  " + msg for msg in messages])
                    except Exception as e:
                        overall_report.append(f"\nError writing to file {file_path}: {str(e)}")
                else:
                    overall_report.append(f"\nNo replacements were made in {file_path}")

        # Generate final summary report
        if total_files == 0:
            yield "Error: No valid files processed"
        else:
            summary = [
                f"Total replacements made: {total_replacements}/{total_blocks}",
            ]
            summary.extend(overall_report)
            yield "\n".join(summary)