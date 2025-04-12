
import subprocess
import time
from tool import Tool
import os
import threading
import queue

class SubProcessTool(Tool):
    """
    Base class for subprocess-based tools.
    Maintains a persistent subprocess while keeping a clean interface.
    Uses a background thread to continuously read process output.
    """
    
    def __init__(self, shell_cmd: str, command_end_marker: str):
        """
        Initialize subprocess tool with specific shell command and end marker.

        Args:
            shell_cmd (str): Shell command to start the subprocess
            command_end_marker (str): Marker that indicates command completion
        """
        # Store command end marker
        self.command_end_marker = command_end_marker
        
        # Create output buffer queue
        self.output_queue = queue.Queue()
        self.running = True
        self.command_complete = threading.Event()
        
        # Create persistent process
        self.process = subprocess.Popen(
            shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=False,
            bufsize=0
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
            self.process.stdin.write((args + '\n').encode("utf-8"))
            self.process.stdin.flush()

            start_time = time.time()
            last_change_time = start_time

            last_line = ""
            while True:
                current_time = time.time()
                # Check if total timeout exceeded
                if current_time - start_time > timeout:
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

                # If output hasn't changed for a while and ends with the marker, consider command complete
                if current_time - last_change_time > no_change_timeout and last_line.endswith(self.command_end_marker):
                    break

                # Brief sleep to avoid excessive CPU usage
                time.sleep(0.1)

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