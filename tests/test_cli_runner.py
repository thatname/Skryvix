import sys
import os

# Add parent directory to Python path to import cli_runner
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_runner import run_with_config

def test_openrouter():
    """
    Test the CLI runner with OpenRouter configuration
    """
    config_path = "model_configs/openrouter.yaml.example"
    prompt = "Hello! Can you tell me what model you are?"

    try:
        print("Testing OpenRouter configuration...")
        print(f"Using config: {config_path}")
        print(f"Prompt: {prompt}")
        print("-" * 50)
        
        result = run_with_config(config_path, prompt)
        
        print("Response:")
        print(result)
        print("-" * 50)
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_openrouter()