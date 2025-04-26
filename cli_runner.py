import argparse
import sys
from config_loader import load_from_yaml
from typing import Optional, Union

def run_with_config(config_path: str, prompt: str) -> Optional[str]:
    """
    Run the chat model with specified config and prompt.
    
    Args:
        config_path (str): Path to YAML config file
        prompt (str): Prompt string to pass to the object
        
    Returns:
        Optional[str]: The response from the model, or None if an error occurs
        
    Raises:
        Exception: If there's an error loading the config or running the model
    """
    try:
        # Load the object from YAML config
        obj = load_from_yaml(config_path)
        
        # Call the object with the prompt
        result = obj(prompt)
        return result
    except Exception as e:
        raise Exception(f"Error running with config: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='CLI Runner')
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--prompt', required=True, help='Prompt string to pass to the object')
    args = parser.parse_args()

    try:
        result = run_with_config(args.config, args.prompt)
        print(result)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()