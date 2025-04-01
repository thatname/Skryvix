
import yaml
from typing import Optional, Dict, Any, Union
import os
from pathlib import Path
from chat_streamer import ChatStreamer

def create_chat_streamer_from_yaml(
    config_path: Union[str, Path],
    override_api_key: Optional[str] = None
) -> ChatStreamer:
    """
    从 YAML 配置文件创建 ChatStreamer 实例

    Args:
        config_path (Union[str, Path]): YAML 配置文件路径
        override_api_key (Optional[str]): 可选的 API 密钥，用于覆盖配置文件中的值

    Returns:
        ChatStreamer: 配置好的 ChatStreamer 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 解析错误
        ValueError: 配置验证错误
    """
    # 转换路径为 Path 对象
    config_path = Path(config_path)

    # 检查文件是否存在
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 读取并解析 YAML 文件
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML 解析错误: {e}")

    if not isinstance(config, dict):
        raise ValueError("配置文件必须是一个 YAML 字典")

    # 获取 API 密钥
    api_key = override_api_key or config.get('api_key') or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未提供 API 密钥。请在配置文件中设置 api_key，"
                        "通过 override_api_key 参数提供，或设置 OPENAI_API_KEY 环境变量。")

    # 移除 api_key，因为它会作为单独的参数传递
    config.pop('api_key', None)

    # 验证和清理配置
    validated_config = _validate_and_clean_config(config)

    # 创建 ChatStreamer 实例
    try:
        return ChatStreamer(api_key=api_key, **validated_config)
    except Exception as e:
        raise ValueError(f"创建 ChatStreamer 实例时出错: {e}")

def _validate_and_clean_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证和清理配置数据

    Args:
        config (Dict[str, Any]): 原始配置字典

    Returns:
        Dict[str, Any]: 验证和清理后的配置字典

    Raises:
        ValueError: 配置验证错误
    """
    validated = {}

    # 验证数值范围的辅助函数
    def validate_range(
        value: Optional[float],
        name: str,
        min_val: float,
        max_val: float
    ) -> Optional[float]:
        if value is not None:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{name} 必须是数字")
            if not min_val <= value <= max_val:
                raise ValueError(f"{name} 必须在 {min_val} 和 {max_val} 之间")
        return value

    # 基础配置
    if 'model_name' in config:
        validated['model_name'] = str(config['model_name'])
    
    if 'base_url' in config and config['base_url'] is not None:
        validated['base_url'] = str(config['base_url'])
    
    if 'system_prompt' in config:
        validated['system_prompt'] = str(config['system_prompt'])

    # 验证可选的数值参数（只在提供时进行验证和添加）
    if 'temperature' in config:
        validated['temperature'] = validate_range(
            config.get('temperature'), 'temperature', 0, 2
        )
    
    if 'top_p' in config:
        validated['top_p'] = validate_range(
            config.get('top_p'), 'top_p', 0, 1
        )
    
    if 'presence_penalty' in config:
        validated['presence_penalty'] = validate_range(
            config.get('presence_penalty'), 'presence_penalty', -2.0, 2.0
        )
    
    if 'frequency_penalty' in config:
        validated['frequency_penalty'] = validate_range(
            config.get('frequency_penalty'), 'frequency_penalty', -2.0, 2.0
        )

    # 其他可选参数
    if 'top_k' in config and config['top_k'] is not None:
        if not isinstance(config['top_k'], int) or config['top_k'] <= 0:
            raise ValueError("top_k 必须是正整数")
        validated['top_k'] = config['top_k']

    if 'max_tokens' in config and config['max_tokens'] is not None:
        if not isinstance(config['max_tokens'], int) or config['max_tokens'] <= 0:
            raise ValueError("max_tokens 必须是正整数")
        validated['max_tokens'] = config['max_tokens']

    if 'stop' in config and config['stop'] is not None:
        if not isinstance(config['stop'], list):
            raise ValueError("stop 必须是字符串列表")
        validated['stop'] = config['stop']

    if 'response_format' in config and config['response_format'] is not None:
        if not isinstance(config['response_format'], dict):
            raise ValueError("response_format 必须是字典")
        validated['response_format'] = config['response_format']

    if 'seed' in config and config['seed'] is not None:
        if not isinstance(config['seed'], int):
            raise ValueError("seed 必须是整数")
        validated['seed'] = config['seed']

    # 移除所有 None 值
    return {k: v for k, v in validated.items() if v is not None}
