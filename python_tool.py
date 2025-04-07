
from tool import Tool
import sys
from io import StringIO

class PythonTool(Tool):
    def description(self) -> str:
        return "执行Python代码并返回输出结果"

    def use(self, args: str) -> str:
        # 保存原始的标准输出
        old_stdout = sys.stdout
        # 创建StringIO对象来捕获输出
        redirected_output = StringIO()
        sys.stdout = redirected_output

        try:
            # 执行Python代码
            exec(args)
            # 获取捕获的输出
            output = redirected_output.getvalue()
            return output if output else "代码执行成功，无输出"
        except Exception as e:
            return f"执行出错: {str(e)}"
        finally:
            # 恢复原始的标准输出
            sys.stdout = old_stdout
            redirected_output.close()



def test():
    print("进入 main 函数")
    # 创建 PythonTool 实例
    python_tool = PythonTool()
    
    # 显示工具描述
    print("工具描述:", python_tool.description())
    print("\n=== 测试用例 ===\n")

    # 测试用例1：简单打印
    print("测试1 - 简单打印:")
    code1 = 'print("Hello, Python Tool!")'
    print("代码:", code1)
    print("输出:", python_tool.use(code1))
    print()

    # 测试用例2：多行代码
    print("测试2 - 多行代码:")
    code2 = '''
for i in range(3):
    print(f"计数: {i}")
'''
    print("代码:", code2)
    print("输出:", python_tool.use(code2))
    print()

    # 测试用例3：数学计算
    print("测试3 - 数学计算:")
    code3 = '''
result = 0
for i in range(1, 5):
    result += i
print(f"1到4的和是: {result}")
'''
    print("代码:", code3)
    print("输出:", python_tool.use(code3))
    print()

    # 测试用例4：错误处理
    print("测试4 - 错误处理:")
    code4 = 'print(undefined_variable)'
    print("代码:", code4)
    print("输出:", python_tool.use(code4))

if __name__ == "__main__":
    print("程序开始")
    test()
    print("程序结束")