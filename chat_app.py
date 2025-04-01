
import os
import gradio as gr
from chat_streamer_factory import create_chat_streamer_from_yaml
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# 从 YAML 配置文件创建 ChatStreamer
try:
    # 获取当前文件所在目录
    current_dir = Path(__file__).parent
    config_path = current_dir / "config_example.yaml"
    
    # 创建 ChatStreamer 实例
    streamer = create_chat_streamer_from_yaml(
        config_path,
        # 可选：覆盖配置文件中的 API 密钥
        # override_api_key="your-api-key-here"
    )
except Exception as e:
    print(f"Error creating ChatStreamer: {e}")
    exit(1)

# 创建 Gradio 界面
def create_demo():
    with gr.Blocks(css="footer {display: none !important}") as demo:
        gr.Markdown("""
        # AI 聊天助手
        与 AI 助手进行实时对话。使用了 OpenAI API 的流式响应功能。
        """)

        # 聊天界面
        chatbot = gr.Chatbot(
            streamer.history,
            type="messages",
            height=600,
            allow_tags=True,
            render_markdown=False
        )
        
        # 用户输入
        msg = gr.Textbox(
            label="输入消息",
            placeholder="在这里输入你的消息...",
            lines=2
        )

        # 清空按钮
        clear = gr.Button("清空对话")

        # 处理用户输入和 AI 响应
        async def user(message):            
            async for content in streamer(message):
                yield streamer.history

        async def clear_history():
            streamer.history = []

        msg.submit(
            user,
            [msg],
            [chatbot],
        )

        # 设置清空按钮动作
        clear.click(
            clear_history,
            None,
            chatbot,
            queue=False
        )

    return demo

# 启动应用
if __name__ == "__main__":
    demo = create_demo()
    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        share=False,
        show_api=False,
    )