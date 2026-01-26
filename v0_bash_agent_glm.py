#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v0_bash_agent_glm.py - Mini Claude Code: Bash 就是一切 (GLM-4 版本)

使用智谱 GLM-4.7 API 的版本
"""

import sys
import os
import json

# 修复 locale 编码问题（macOS/Linux）
if sys.platform != "win32":
    import locale
    if locale.getpreferredencoding().lower() != "utf-8":
        os.environ["LANG"] = "en_US.UTF-8"
        os.environ["LC_ALL"] = "en_US.UTF-8"

from openai import OpenAI
from dotenv import load_dotenv
import subprocess

load_dotenv(override=True)

# 初始化 OpenAI 客户端（兼容智谱 API）
client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", "your_api_key_here"),
    base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
)
MODEL = os.getenv("MODEL_ID", "glm-4.7")

# 唯一的工具，可以做任何事情
TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": """执行 shell 命令。常用模式：
- 读取: cat/head/tail, grep/find/rg/ls, wc -l
- 写入: echo 'content' > file, sed -i 's/old/new/g' file
- 子代理: python3 v0_bash_agent_glm.py 'task description' (生成独立代理，返回摘要)""",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "要执行的 shell 命令"}},
            "required": ["command"]
        }
    }
}

# System prompt
SYSTEM = f"""你是一个位于 {os.getcwd()} 的 CLI 代理。使用 bash 命令解决问题。

规则：
- 优先使用工具而非文字。先行动，后简要解释。
- 读文件: cat, grep, find, rg, ls, head, tail
- 写文件: echo '...' > file, sed -i, 或 cat << 'EOF' > file
- 子代理：对于复杂的子任务，生成子代理以保持上下文干净：
  python3 v0_bash_agent_glm.py "探索 src/ 并总结架构"

何时使用子代理：
- 任务需要读取很多文件（隔离探索过程）
- 任务是独立且自包含的
- 你希望避免用中间细节污染当前对话

子代理在隔离中运行，仅返回最终摘要。"""


def fix_surrogates(text):
    """修复包含代理字符的字符串"""
    if not text:
        return text
    # 编码为 utf-8，忽略错误，再解码回来
    return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')


def chat(prompt, history=None):
    """
    一个函数中的完整代理循环。
    """
    if history is None:
        history = []

    # 清理输入中的编码问题
    prompt = fix_surrogates(prompt)

    # 添加用户消息
    history.append({"role": "user", "content": prompt})

    while True:
        # 1. 调用模型
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + history,
            tools=[TOOL],
            temperature=0.7
        )

        msg = response.choices[0].message

        # 2. 保存助手消息
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]
        history.append(assistant_msg)

        # 3. 如果没有工具调用，返回结果
        if not msg.tool_calls:
            return msg.content or ""

        # 4. 执行工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            if func_name == "bash":
                cmd = func_args["command"]
                print(f"\033[33m$ {cmd}\033[0m")

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
                except Exception as e:
                    output = f"(错误: {e})"

                print(output or "(空)")

                # 添加工具结果
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": output[:50000]
                })


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 子代理模式
        print(chat(sys.argv[1]))
    else:
        # 交互式 REPL 模式
        history = []
        while True:
            try:
                query = input("\033[36m>> \033[0m")
            except (EOFError, KeyboardInterrupt):
                break
            if query in ("q", "exit", ""):
                break
            print(chat(query, history))
