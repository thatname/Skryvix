
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
        self.output_buffer = b""
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
        """
        print("Started reading output")
        while self.running:
            try:
                char = self.process.stdout.read(1)
                if not char and self.process.poll() is not None:
                    print("Process ended")
                    break
                if char:
                    self.output_queue.put(char)
            except Exception as e:
                print(f"Error reading output: {str(e)}")
                break
        print("Output reader thread ended")

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
```
Response of this tool will include all the file names inside current direction, followed by the git commit result.
"""


    def _getstdout(self) -> bytes:
        """
        Get all output from current buffer.

        Returns:
            str: Output content in buffer
        """
        # Clear all content in queue
        while not self.output_queue.empty():
            try:
                char = self.output_queue.get_nowait()
                self.output_buffer += char
            except queue.Empty:
                break
        
        return self.output_buffer
    
    def use(self, args: str) -> str:
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
            print(f"\nExecuting command: {args}")

            self.process.stdin.write((args + '\n').encode("utf-8"))
            self.process.stdin.flush()
            print("Command sent")

            start_time = time.time()
            last_output = b""
            last_change_time = start_time

            while True:
                current_time = time.time()
                # Check if total timeout exceeded
                if current_time - start_time > timeout:
                    print("Command execution timed out")
                    break

                # 获取当前输出
                current_output = self._getstdout()
                
                # If output changed, update last change time
                if current_output != last_output:
                    last_output = current_output
                    last_change_time = current_time
                # If output hasn't changed for a while, consider command complete
                elif current_time - last_change_time > no_change_timeout and current_output.endswith(b">"):
                    print("Output stabilized")
                    break

                # Brief sleep to avoid excessive CPU usage
                time.sleep(0.1)

            print(f"Command execution completed, output length: {len(last_output)}")
            return last_output.decode("utf-8")
#locale.getpreferredencoding()
        except Exception as e:
            print(f"Command execution failed: {str(e)}")
            return f"Command execution failed: {str(e)}"

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


def main():
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
        result = cmd_tool.use(cmd)
        print(result)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()