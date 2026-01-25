#!/usr/bin/env python
"""
v0_bash_agent.py - Mini Claude Code: Bash 就是一切 (~50 行核心代码)

核心哲学："Bash 就是一切"
======================================
这是编码代理的终极简化版本。在构建 v1-v3 之后，
我们问：代理的本质是什么？

答案：一个工具 + 一个循环 = 完整的代理能力。

为什么 Bash 就足够了：
------------------
Unix 哲学说一切皆文件，一切皆可管道。
Bash 是这个世界的入口：

    | 你需要        | Bash 命令                              |
    |---------------|----------------------------------------|
    | 读文件        | cat, head, tail, grep                  |
    | 写文件        | echo '...' > file, cat << 'EOF' > file |
    | 搜索          | find, grep, rg, ls                     |
    | 执行          | python, npm, make, 任何命令            |
    | **子代理**    | python v0_bash_agent.py "task"         |

最后一行是关键洞察：通过 bash 调用自身实现子代理！
不需要 Task 工具，不需要 Agent Registry —— 只需要进程递归。

子代理如何工作：
------------------
    主代理
      |-- bash: python v0_bash_agent.py "分析架构"
           |-- 子代理（独立进程，全新历史）
                |-- bash: find . -name "*.py"
                |-- bash: cat src/main.py
                |-- 通过 stdout 返回摘要

进程隔离 = 上下文隔离：
- 子进程有自己的 history=[]
- 父进程捕获 stdout 作为工具结果
- 递归调用实现无限嵌套

用法：
    # 交互模式
    python v0_bash_agent.py

    # 子代理模式（由父代理调用或直接调用）
    python v0_bash_agent.py "探索 src/ 并总结"
"""

from anthropic import Anthropic
from dotenv import load_dotenv
import subprocess
import sys
import os

load_dotenv(override=True)

# 初始化 Anthropic 客户端（使用 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL 环境变量）
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.getenv("MODEL_ID", "claude-sonnet-4-5-20250929")

# 唯一的工具，可以做任何事情
# 注意：描述中既教授了模型常用模式，也教了如何生成子代理
TOOL = [{
    "name": "bash",
    "description": """执行 shell 命令。常用模式：
- 读取: cat/head/tail, grep/find/rg/ls, wc -l
- 写入: echo 'content' > file, sed -i 's/old/new/g' file
- 子代理: python v0_bash_agent.py 'task description' (生成独立代理，返回摘要)""",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"]
    }
}]

# System prompt 教模型如何有效地使用 bash
# 注意子代理的指导 —— 这是我们实现层级任务分解的方式
SYSTEM = f"""你是一个位于 {os.getcwd()} 的 CLI 代理。使用 bash 命令解决问题。

规则：
- 优先使用工具而非文字。先行动，后简要解释。
- 读文件: cat, grep, find, rg, ls, head, tail
- 写文件: echo '...' > file, sed -i, 或 cat << 'EOF' > file
- 子代理：对于复杂的子任务，生成子代理以保持上下文干净：
  python v0_bash_agent.py "探索 src/ 并总结架构"

何时使用子代理：
- 任务需要读取很多文件（隔离探索过程）
- 任务是独立且自包含的
- 你希望避免用中间细节污染当前对话

子代理在隔离中运行，仅返回最终摘要。"""


def chat(prompt, history=None):
    """
    一个函数中的完整代理循环。

    这是所有编码代理共享的核心模式：
        while not done:
            response = model(messages, tools)
            if no tool calls: return
            execute tools, append results

    Args:
        prompt: 用户的请求
        history: 对话历史（可变，在交互模式中跨调用共享）

    Returns:
        模型的最终文本响应
    """
    if history is None:
        history = []

    history.append({"role": "user", "content": prompt})

    while True:
        # 1. 调用模型（带工具）
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=history,
            tools=TOOL,
            max_tokens=8000
        )

        # 2. 构建助手消息内容（保留 text 和 tool_use 两种 block）
        content = []
        for block in response.content:
            if hasattr(block, "text"):
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        history.append({"role": "assistant", "content": content})

        # 3. 如果模型没有调用工具，我们就完成了
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if hasattr(b, "text"))

        # 4. 执行每个工具调用并收集结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                cmd = block.input["command"]
                print(f"\033[33m$ {cmd}\033[0m")  # 黄色显示命令

                try:
                    out = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        cwd=os.getcwd()
                    )
                    output = out.stdout + out.stderr
                except subprocess.TimeoutExpired:
                    output = "(300秒后超时)"

                print(output or "(空)")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output[:50000]  # 截断过长的输出
                })

        # 5. 追加结果并继续循环
        history.append({"role": "user", "content": results})


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 子代理模式：执行任务并打印结果
        # 这是父代理通过 bash 生成子进程的方式
        print(chat(sys.argv[1]))
    else:
        # 交互式 REPL 模式
        history = []
        while True:
            try:
                query = input("\033[36m>> \033[0m")  # 青色提示符
            except (EOFError, KeyboardInterrupt):
                break
            if query in ("q", "exit", ""):
                break
            print(chat(query, history))
