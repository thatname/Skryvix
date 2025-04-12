
import subprocess
import time
from tool import Tool
from io import StringIO
import os
import threading
import queue
import sys
import locale
class CmdTool(Tool):
    """
    Command line tool class for executing shell commands.
    Maintains a persistent command line process while keeping a clean interface.
    Uses a background thread to continuously read command output.
    """
    def name(self)->str:
        return "cmd"
    
    def __init__(self):
        """
        Initialize command line tool, create a persistent command line process and output reader thread.
        """
        # Create output buffer queue
        self.output_queue = queue.Queue()
        self.running = True
        self.command_complete = threading.Event()
        
        # Create persistent process
        shell_cmd = 'cmd.exe /K chcp 65001' if os.name == 'nt' else 'bash'
        try:
            self.process = subprocess.Popen(
                shell_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=False,
                bufsize=0,
                #universal_newlines=True
            )
            print(f"Process started: PID={self.process.pid}")
        except Exception as e:
            print(f"Process start failed: {str(e)}")
            raise

        # Start output reader thread
        self.reader_thread = threading.Thread(target=self._output_reader, daemon=True)
        self.reader_thread.start()
        print("Output reader thread started")

    def _output_reader(self):
        """
        Background thread function, continuously reads process output.
        Accumulates bytes and decodes them as UTF-8 when complete characters are formed.
        """
        print("Started reading output")
        # Buffer for accumulating bytes
        byte_buffer = bytearray()
        
        while self.running:
            try:
                byte = self.process.stdout.read(1)
                if not byte and self.process.poll() is not None:
                    # Process remaining bytes in buffer
                    if byte_buffer:
                        try:
                            final_str = byte_buffer.decode('utf-8')
                            self.output_queue.put(final_str)
                        except UnicodeDecodeError:
                            pass  # Ignore possibly incomplete characters at the end
                    break
                
                if byte:
                    byte_buffer.extend(byte)
                    # Try to decode accumulated bytes
                    try:
                        decoded = byte_buffer.decode('utf-8')
                        # If decoding succeeds, put characters into queue and clear buffer
                        self.output_queue.put(decoded)
                        byte_buffer.clear()
                    except UnicodeDecodeError:
                        # If decoding fails, continue accumulating bytes
                        continue
                        
            except Exception as e:
                self.output_queue.put(f"Error reading output: {str(e)}")
                break

    def description(self) -> str:
        """
        Returns the tool's description.

        Returns:
            str: Tool description
        """
        return """* cmd - Windows command prompt. Example:
```cmd
dir
git add -A
git commit -m "feat: add splash screen (#173)"
```invoke
Response of this tool will include all the file names inside current direction, followed by the git commit result.
"""
    
    async def use(self, args: str):
        """
        Execute command in persistent process and return result.
        Continuously checks output until it stabilizes (no more changes) or times out.

        Args:
            args (str): Command to execute

        Returns:
            str: Command output result
        """
        timeout = 300  # Total timeout
        no_change_timeout = 2  # Timeout for no output changes (seconds)
        try:
            #print(f"\nExecuting command: {args}")

            self.process.stdin.write((args + '\n').encode("utf-8"))
            self.process.stdin.flush()
            #print("Command sent")

            start_time = time.time()
            last_output = ""
            last_change_time = start_time

            while True:
                current_time = time.time()
                # Check if total timeout exceeded
                if current_time - start_time > timeout:
                    yield "Command execution timed out"
                    break
                        # Clear all content in queue
                while not self.output_queue.empty():
                    try:
                        output = self.output_queue.get_nowait()
                        yield output
                        last_change_time = current_time
                    except queue.Empty:
                        break

                # If output hasn't changed for a while, consider command complete
                if current_time - last_change_time > no_change_timeout and output.endswith(">"):
                    break

                # Brief sleep to avoid excessive CPU usage
                time.sleep(0.5)

        except Exception as e:
            yield f"Command execution failed: {str(e)}"

    def __del__(self):
        """
        Destructor, ensures process, thread and buffer are properly cleaned up.
        """
        print("Starting resource cleanup")
        self.running = False
        
        if hasattr(self, 'process') and self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception as e:
                print(f"Error terminating process: {str(e)}")
                self.process.kill()
            
        if hasattr(self, 'reader_thread') and self.reader_thread:
            self.reader_thread.join(timeout=1.0)
        
        print("Resource cleanup completed")


async def main():
    # Create command line tool instance
    cmd_tool = CmdTool()
    
    # Print tool description
    print("Tool description:", cmd_tool.description())
    print("\n" + "="*50 + "\n")

    # Test some basic commands
    commands = [
        "echo Hello, World!",
        "dir",  # List directory contents on Windows
        "type cmd_tool.py",  # View file contents on Windows
    ]

    # Execute each test command
    for cmd in commands:
        print(f"Executing command: {cmd}")
        print("-" * 30)
        # Use async for loop to process each character output
        async for char in cmd_tool.use(cmd):
            print(char, end='', flush=True)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())