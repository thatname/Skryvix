
from typing import List, Tuple, Optional, AsyncGenerator, Any, Dict, Union
from openai import AsyncOpenAI
import asyncio
import yaml
import json
import os
from pathlib import Path

class ChatStreamer:
    def __init__(
        self,
        api_key_env_var: str,
        model_name: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
        system_prompt: str = "You are a helpful AI assistant.",
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        response_format: Optional[Dict[str, str]] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize ChatStreamer

        Args:
            api_key (str): OpenAI API key
            model_name (str): Model name, defaults to "gpt-3.5-turbo"
            base_url (Optional[str]): API base URL for custom endpoints
            system_prompt (str): System prompt
            temperature (Optional[float]): Sampling temperature, controls randomness, range 0-2, default 1.0
            top_p (Optional[float]): Nucleus sampling threshold, range 0-1, default 1.0
            top_k (Optional[int]): Number of highest probability tokens to consider at each step
            presence_penalty (Optional[float]): Presence penalty, range -2.0 to 2.0, default 0.0
            frequency_penalty (Optional[float]): Frequency penalty, range -2.0 to 2.0, default 0.0
            max_tokens (Optional[int]): Maximum number of tokens to generate
            stop (Optional[List[str]]): List of tokens to stop generation
            response_format (Optional[Dict[str, str]]): Response format settings, e.g., {"type": "json_object"}
            seed (Optional[int]): Random seed for reproducible results
        """
        self.system_prompt = system_prompt
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.max_tokens = max_tokens
        self.stop = stop
        self.response_format = response_format
        self.seed = seed

        # Initialize conversation history
        self.clear_history()

        api_key = os.getenv(api_key_env_var)
        if not api_key:
                raise ValueError("${api_key_env_var} environment variable not found. Please set it in the .env file")
    
        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
                    
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)
    def clear_history(self):
        self.history = [{"role": "system", "content": self.system_prompt}]

    def _build_completion_params(self) -> Dict[str, Any]:
        """
        Build completion request parameters

        Returns:
            Dict[str, Any]: API request parameters
        """
        params = {
            "model": self.model_name,
            "stream": True,
        }

        # Add optional parameters (only non-default values)
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        if self.presence_penalty is not None:
            params["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            params["frequency_penalty"] = self.frequency_penalty
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        if self.stop is not None:
            params["stop"] = self.stop
        if self.response_format is not None:
            params["response_format"] = self.response_format
        if self.seed is not None:
            params["seed"] = self.seed

        return params

    @classmethod
    def create_from_yaml(cls, config_path: Union[str, Path]) -> 'ChatStreamer':
        """
        Create ChatStreamer instance from YAML config file

        Args:
            config_path (Union[str, Path]): YAML config file path

        Returns:
            ChatStreamer: Configured ChatStreamer instance

        Raises:
            FileNotFoundError: Config file not found
            yaml.YAMLError: YAML parsing error
        """

        # Convert path to Path object and check if file exists
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Read and parse YAML file
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                # Get API key
        
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML parsing error: {e}")

        # Create ChatStreamer instance
        return cls(**config)

    async def __call__(
        self,
        message
    ):
        try:
            user = True
            for msg in message.split("\n|||\n"):
                if msg != "":
                    self.history.push({"role": "user" if user else "assistant", "content": msg})
                    user = not user

            # Build messages and parameters
            params = self._build_completion_params()
            params["messages"] = self.history

            # Create streaming response
            stream = await self.client.chat.completions.create(**params)
            
            self.history.append({"role": "assistant", "content": ""})

        
            # Process response token by token
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    self.history[-1]["content"] += content
                    yield content

        except Exception as e:
            yield f"Exception :{e}"