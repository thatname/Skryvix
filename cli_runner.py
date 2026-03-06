import argparse
import asyncio
import sys
import os
from config_loader import load_from_file
from typing import Optional, Union
from ask_tool import read_multiline_stdin

original_stdout = sys.stdout
def safe_write(text):
    """Safely write to original stdout"""
    original_stdout.write(text)
    original_stdout.flush()

async def run_with_config(config_path: str, prompt: Optional[str], worker_mode: bool = False, work_dir: Optional[str] = None) -> Optional[str]:
    """
    Run the chat model with specified config and prompt.
    
    Args:
        config_path (str): Path to YAML config file
        prompt (str): Prompt string to pass to the object
        work_dir (str): Directory to switch to after loading config
        
    Returns:
        Optional[str]: The response from the model, or None if an error occurs
        
    Raises:
        Exception: If there's an error loading the config or running the model
    """
    try:
        # Record the current directory
        original_dir = os.getcwd()
        
        # Load the object from YAML config
        tool = load_from_file(config_path)
        
        # Switch to the specified directory if provided
        if work_dir:
            os.chdir(work_dir)
        
        if not prompt:
            if not worker_mode: # Prompt user in active mode (default)
                safe_write("Please enter the prompt (end with '@@@' on a new line):")
            # Read from stdin
            prompt = await read_multiline_stdin()
            if not prompt:
                safe_write("Error: No prompt provided either via --prompt argument or standard input.")
                sys.exit(1) # Exit if no prompt is available after trying stdin

        # Call the  with the determined prompt
        async for response in tool(prompt):
            safe_write(response)
        
        # Switch back to the original directory
        os.chdir(original_dir)
    except Exception as e:
        # Ensure we switch back to the original directory even if an error occurs
        os.chdir(original_dir)
        raise Exception(f"Error running with config: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='CLI Runner')
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--prompt', required=False, help='Prompt string to pass to the object')
    parser.add_argument('--worker-mode', action="store_true", help='Whether in worker mode')
    parser.add_argument('--work-dir', required=False, default=None, help='Directory to switch to after loading config')
    args = parser.parse_args()

    try:
        asyncio.run(run_with_config(args.config, args.prompt, args.worker_mode, args.work_dir))
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)

if __name__ == '__main__':
    main()