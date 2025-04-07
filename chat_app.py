
import os
import gradio as gr
from chat_streamer_factory import create_chat_streamer_from_yaml
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# Create ChatStreamer from YAML config file
try:
    # Get current directory
    current_dir = Path(__file__).parent
    config_path = current_dir / "config_example.yaml"
    
    # Create ChatStreamer instance
    streamer = create_chat_streamer_from_yaml(
        config_path,
        # Optional: Override API key from config file
        # override_api_key="your-api-key-here"
    )
except Exception as e:
    print(f"Error creating ChatStreamer: {e}")
    exit(1)

# 创建 Gradio 界面
def create_demo():
    with gr.Blocks(css="footer {display: none !important}") as demo:
        gr.Markdown("""
        # AI Chat Assistant
        Real-time conversation with AI assistant. Using OpenAI API streaming response.
        """)

        # Chat interface
        chatbot = gr.Chatbot(
            streamer.history,
            type="messages",
            height=600,
            allow_tags=True,
            render_markdown=False
        )
        
        # User input
        msg = gr.Textbox(
            label="Enter message",
            placeholder="Type your message here...",
            lines=2
        )

        # Clear button
        clear = gr.Button("Clear Chat")

        # Handle user input and AI response
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

        # Set clear button action
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