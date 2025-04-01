
from typing import List, Tuple, Optional, AsyncGenerator, Any, Dict
from openai import AsyncOpenAI
import asyncio

class ChatStreamer:
    def __init__(
        self,
        api_key: str,
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
        初始化 ChatStreamer

        Args:
            api_key (str): OpenAI API 密钥
            model_name (str): 模型名称，默认为 "gpt-3.5-turbo"
            base_url (Optional[str]): API 基础 URL，用于自定义端点
            system_prompt (str): 系统提示词
            temperature (Optional[float]): 采样温度，控制输出的随机性，范围 0-2，默认 1.0
            top_p (Optional[float]): 核采样阈值，范围 0-1，默认 1.0
            top_k (Optional[int]): 每个步骤考虑的最高概率标记数
            presence_penalty (Optional[float]): 存在惩罚，范围 -2.0 到 2.0，默认 0.0
            frequency_penalty (Optional[float]): 频率惩罚，范围 -2.0 到 2.0，默认 0.0
            max_tokens (Optional[int]): 生成的最大标记数
            stop (Optional[List[str]]): 停止生成的标记列表
            response_format (Optional[Dict[str, str]]): 响应格式设置，如 {"type": "json_object"}
            seed (Optional[int]): 随机数种子，用于可重复的结果
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

        # 初始化对话历史
        self.clear_history()

        # 初始化 OpenAI 客户端
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)
    def clear_history(self):
        self.history = [{"role": "system", "content": self.system_prompt}]
        
    def _build_messages(self, message: str) -> List[Dict[str, str]]:
        """
        构建消息历史列表

        Args:
            message (str): 当前用户消息

        Returns:
            List[Dict[str, str]]: 格式化的消息列表
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 添加历史消息
        for user_msg, assistant_msg in self._history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        return messages

    def _build_completion_params(self) -> Dict[str, Any]:
        """
        构建完成请求参数

        Returns:
            Dict[str, Any]: API 请求参数
        """
        params = {
            "model": self.model_name,
            "stream": True,
        }

        # 添加可选参数（只添加非默认值）
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

    async def __call__(
        self,
        message
    ):

        self.history.append({"role": "user", "content": message})

        # 构建消息和参数
        params = self._build_completion_params()
        params["messages"] = self.history

        # 创建流式响应
        stream = await self.client.chat.completions.create(**params)
        
        self.history.append({"role": "assistant", "content": ""})

        try:
            # 逐个 token 处理响应
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    self.history[-1]["content"] += content
                    yield content

        except Exception as e:
            raise