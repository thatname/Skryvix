
import subprocess
import time
import threading
import queue
import asyncio
from tool import Tool

class SubProcessTool(Tool):
    """
    A tool for managing persistent subprocesses with continuous output monitoring.
    Maintains a long-running subprocess while providing a clean interface for interaction.
    Uses a background thread to continuously read and buffer process output.
    Supports UTF-8 encoded output with proper character boundary handling.
    """
    
    def name(self) -> str:
        return "subprocess"

    def description(self) -> str:
        return "Executes and manages long-running shell commands as persistent subprocesses. Provides real-time output streaming and proper process cleanup."

    def __init__(self, shell_cmd, command_end_marker=None, work_dir=None, timeout=0):
        """
        Initialize subprocess tool with specific shell command and end marker.

        Args:
            shell_cmd (str): Shell command to start the subprocess
            command_end_marker (str, optional): Marker that indicates command completion. Defaults to None.
            work_dir (str, optional): Working directory for the subprocess. Defaults to None.
            timeout (int, optional): Command execution timeout in seconds. Defaults to 0 (no timeout).
        """
        self.timeout = timeout
        self.command_end_marker = command_end_marker
        self.exit_code = None
        self.output_queue = queue.Queue()
        self.running = True
        
        # Create persistent process
        self.process = subprocess.Popen(
            shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=False,
            bufsize=0,
            cwd=work_dir
        )

        # Start output reader thread
        self.reader_thread = threading.Thread(target=self._output_reader, daemon=True)
        self.reader_thread.start()

    def _output_reader(self):
        """
        Background thread function, continuously reads process output.
        Accumulates bytes and decodes them as UTF-8 when complete characters are formed.
        """
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
                    # Set exit_code when process ends
                    self.exit_code = self.process.poll()
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
        self.running = False

    async def __call__(self, args):
        """
        Execute command in persistent process and return result.
        Continuously checks output until it stabilizes (no more changes) or times out.

        Args:
            args (str): Command to execute

        Returns:
            str: Command output result
        """
        no_change_timeout = 2  # Timeout for no output changes (seconds)
        try:
            start_time = time.time()
            last_change_time = start_time
            last_line = ""  # Initialize last_line
            
            # Split args into lines if not None
            command_lines = args.splitlines() if args else []
            current_line_index = 0

            # If no commands, send empty line to trigger prompt
            if not command_lines:
                self.process.stdin.write(b'\n')
                self.process.stdin.flush()

            while True:
                current_time = time.time()
                # Check if total timeout exceeded
                if self.timeout and current_time - start_time > self.timeout:
                    yield "Command execution timed out"
                    break
                
                # Clear all content in queue
                last_output = ""
                while not self.output_queue.empty():
                    try:
                        output = self.output_queue.get_nowait()
                        last_output += output
                        
                        if output == "\n":
                            last_line = ""
                        else:
                            last_line += output
                        last_change_time = current_time
                    except queue.Empty:
                        break
                
                yield last_output

                # Send next command if available and previous command is complete
                if current_line_index < len(command_lines):
                    if current_line_index == 0 or (
                        self.command_end_marker is not None and
                        current_time - last_change_time > no_change_timeout and
                        last_line.endswith(self.command_end_marker)
                    ):
                        next_command = command_lines[current_line_index] + '\n'
                        self.process.stdin.write(next_command.encode("utf-8"))
                        self.process.stdin.flush()
                        current_line_index += 1
                        last_change_time = current_time
                
                # Check if all commands are complete
                if (current_line_index >= len(command_lines) and
                    (self.exit_code is not None or
                     (self.command_end_marker is not None and
                      current_time - last_change_time > no_change_timeout and
                      last_line.endswith(self.command_end_marker)))
                ):
                    break

                # Brief sleep to avoid excessive CPU usage
                await asyncio.sleep(0.1)

        except Exception as e:
            yield f"Command execution failed: {str(e)}"

    def __del__(self):
        """
        Destructor, ensures process, thread and buffer are properly cleaned up.
        """
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