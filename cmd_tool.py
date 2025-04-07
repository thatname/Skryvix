
import subprocess
import time
from tool import Tool
from io import StringIO
import os
import threading
import queue
import sys
import locale
class CmdTool(Tool):
    """
    命令行工具类，用于执行 shell 命令。
    维护一个持久的命令行进程，同时保持简洁的接口。
    使用后台线程持续读取命令输出。
    """
    
    def __init__(self):
        """
        初始化命令行工具，创建一个持久的命令行进程和输出读取线程。
        """
        # 创建输出缓冲队列
        self.output_queue = queue.Queue()
        self.output_buffer = b""
        self.running = True
        self.command_complete = threading.Event()
        
        # 创建持久进程
        shell_cmd = 'cmd.exe /K chcp 65001' if os.name == 'nt' else 'bash'
        try:
            self.process = subprocess.Popen(
                shell_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并标准错误到标准输出
                text=False,
                bufsize=0,
                #universal_newlines=True
            )
            print(f"进程已启动: PID={self.process.pid}")
        except Exception as e:
            print(f"进程启动失败: {str(e)}")
            raise

        # 启动输出读取线程
        self.reader_thread = threading.Thread(target=self._output_reader, daemon=True)
        self.reader_thread.start()
        print("输出读取线程已启动")

    def _output_reader(self):
        """
        后台线程函数，持续读取进程输出。
        """
        print("开始读取输出")
        while self.running:
            try:
                char = self.process.stdout.read(1)
                if not char and self.process.poll() is not None:
                    print("进程已结束")
                    break
                if char:
                    self.output_queue.put(char)
            except Exception as e:
                print(f"读取输出时出错: {str(e)}")
                break
        print("输出读取线程结束")

    def description(self) -> str:
        """
        返回工具的描述信息。

        Returns:
            str: 工具的描述
        """
        return "命令行工具：执行 shell 命令并返回输出结果。输入为要执行的命令字符串。"

    def _getstdout(self) -> bytes:
        """
        获取当前缓冲区中的所有输出。

        Returns:
            str: 缓冲区中的输出内容
        """
        # 清空队列中的所有内容
        while not self.output_queue.empty():
            try:
                char = self.output_queue.get_nowait()
                self.output_buffer += char
            except queue.Empty:
                break
        
        return self.output_buffer
    
    def use(self, args: str) -> str:
        """
        在持久进程中执行命令并返回结果。
        会持续检查输出直到输出稳定（不再变化）或超时。

        Args:
            args (str): 要执行的命令

        Returns:
            str: 命令的输出结果
        """
        timeout = 300  # 总体超时时间
        no_change_timeout = 2  # 输出无变化的超时时间（秒）
        try:
            print(f"\n执行命令: {args}")

            self.process.stdin.write((args + '\n').encode("utf-8"))
            self.process.stdin.flush()
            print("命令已发送")

            start_time = time.time()
            last_output = b""
            last_change_time = start_time

            while True:
                current_time = time.time()
                # 检查是否超过总体超时时间
                if current_time - start_time > timeout:
                    print("命令执行超时")
                    break

                # 获取当前输出
                current_output = self._getstdout()
                
                # 如果输出有变化，更新最后变化时间
                if current_output != last_output:
                    last_output = current_output
                    last_change_time = current_time
                # 如果输出在一定时间内没有变化，认为命令执行完成
                elif current_time - last_change_time > no_change_timeout and current_output.endswith(b">"):
                    print("输出已稳定")
                    break

                # 短暂休眠以避免过度消耗CPU
                time.sleep(0.1)

            print(f"命令执行完成，输出长度: {len(last_output)}")
            return last_output.decode("utf-8")
#locale.getpreferredencoding()
        except Exception as e:
            print(f"命令执行失败: {str(e)}")
            return f"命令执行失败: {str(e)}"

    def __del__(self):
        """
        析构函数，确保进程、线程和缓冲区被正确清理。
        """
        print("开始清理资源")
        self.running = False
        
        if hasattr(self, 'process') and self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception as e:
                print(f"终止进程时出错: {str(e)}")
                self.process.kill()
            
        if hasattr(self, 'reader_thread') and self.reader_thread:
            self.reader_thread.join(timeout=1.0)
        
        print("资源清理完成")


def main():
    # 创建命令行工具实例
    cmd_tool = CmdTool()
    
    # 打印工具描述
    print("工具描述:", cmd_tool.description())
    print("\n" + "="*50 + "\n")

    # 测试一些基本命令
    commands = [
        "echo Hello, World!",
        "dir",  # Windows 下列出目录内容
        "type cmd_tool.py",  # Windows 下查看文件内容
    ]

    # 执行每个测试命令
    for cmd in commands:
        print(f"执行命令: {cmd}")
        print("-" * 30)
        result = cmd_tool.use(cmd)
        print(result)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()