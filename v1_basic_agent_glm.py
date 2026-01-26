#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v1_basic_agent_glm.py - Mini Claude Code: 模型即代理 (~250 行，GLM 版本)

使用智谱 GLM-4.7 API 的版本

核心哲学: "模型即代理"
=========================================
Claude Code、Cursor Agent、Codex CLI 的秘密是什么？没有秘密。

剥去 CLI 的华丽外衣、进度条、权限系统，剩下的是
惊人的简单：一个让模型调用工具直到完成的循环。

传统助手：
    User -> Model -> Text Response

代理系统：
    User -> Model -> [Tool -> Result]* -> Response
                          ^________|

星号 (*) 很重要！模型会重复调用工具，直到它认为
任务完成。这将聊天机器人转变为自主代理。

关键洞察：模型是决策者。代码只是提供工具并
运行循环。模型决定：
  - 调用哪些工具
  - 以什么顺序
  - 何时停止

四大核心工具：
------------------------
Claude Code 有约 20 个工具。但这 4 个覆盖了 90% 的用例：

    | Tool       | Purpose              | Example                    |
    |------------|----------------------|----------------------------|
    | bash       | 运行任何命令         | npm install, git status    |
    | read_file  | 读取文件内容         | 查看 src/index.ts          |
    | write_file | 创建/覆盖文件        | 创建 README.md             |
    | edit_file  | 精确修改             | 替换函数                   |

仅用这 4 个工具，模型可以：
  - 探索代码库（bash: find, grep, ls）
  - 理解代码（read_file）
  - 修改代码（write_file, edit_file）
  - 运行任何命令（bash: python, npm, make）

用法：
    python v1_basic_agent_glm.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# 修复 locale 编码问题（macOS/Linux）
if sys.platform != "win32":
    import locale
    if locale.getpreferredencoding().lower() != "utf-8":
        os.environ["LANG"] = "en_US.UTF-8"
        os.environ["LC_ALL"] = "en_US.UTF-8"

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)


# =============================================================================
# 配置
# =============================================================================

WORKDIR = Path.cwd()
client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", "your_api_key_here"),
    base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
)
MODEL = os.getenv("MODEL_ID", "glm-4.7")


# =============================================================================
# 系统提示词 - 模型唯一需要的"配置"
# =============================================================================

SYSTEM = f"""你是位于 {WORKDIR} 的编码代理。

循环：简短思考 -> 使用工具 -> 报告结果。

规则：
- 优先使用工具而非文字。行动，而不只是解释。
- 不要虚构文件路径。如果不确定，先使用 bash ls/find。
- 做最小化修改。不要过度设计。
- 完成后，总结更改内容。"""


# =============================================================================
# 工具定义 - 4 个工具覆盖 90% 的编码任务
# =============================================================================

TOOLS = [
    # 工具 1: Bash - 通向一切的入口
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "运行 shell 命令。用于：ls, find, grep, git, npm, python 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令"
                    }
                },
                "required": ["command"]
            }
        }
    },

    # 工具 2: 读取文件 - 用于理解现有代码
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。返回 UTF-8 文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件的相对路径"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大读取行数（默认：全部）"
                    },
                },
                "required": ["path"]
            }
        }
    },

    # 工具 3: 写入文件 - 用于创建新文件或完全重写
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "将内容写入文件。如需要会创建父目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件的相对路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的内容"
                    },
                },
                "required": ["path", "content"]
            }
        }
    },

    # 工具 4: 编辑文件 - 用于对现有代码进行精确修改
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "替换文件中的精确文本。用于精确修改。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件的相对路径"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "要查找的精确文本（必须完全匹配）"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "替换文本"
                    },
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
]


# =============================================================================
# 工具实现
# =============================================================================

def safe_path(p: str) -> Path:
    """
    确保路径保持在工作区内（安全措施）。

    防止模型访问项目目录之外的文件。
    解析相对路径并检查它们不会通过 '../' 逃逸。
    """
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """
    执行 shell 命令并进行安全检查。

    安全性：阻止明显的危险命令。
    超时：60 秒以防止挂起。
    输出：截断至 50KB 以防止上下文溢出。
    """
    # 基本安全 - 阻止危险模式
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out (60s)"
    except Exception as e:
        return f"Error: {e}"


def run_read(path: str, limit: int = None) -> str:
    """
    读取文件内容，支持可选的行数限制。

    对于大文件，使用 limit 仅读取前 N 行。
    输出截断至 50KB 以防止上下文溢出。
    """
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()

        if limit and limit < len(lines):
            lines = lines[:limit]
            lines.append(f"... ({len(text.splitlines()) - limit} more lines)")

        return "\n".join(lines)[:50000]

    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """
    将内容写入文件，如需要会创建父目录。

    这用于完整的文件创建/覆盖。
    对于部分编辑，请使用 edit_file。
    """
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"

    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    替换文件中的精确文本（精确编辑）。

    使用精确字符串匹配 - old_text 必须逐字出现。
    仅替换第一次出现以防止意外的大规模更改。
    """
    try:
        fp = safe_path(path)
        content = fp.read_text()

        if old_text not in content:
            return f"Error: Text not found in {path}"

        # 为安全起见，仅替换第一次出现
        new_content = content.replace(old_text, new_text, 1)
        fp.write_text(new_content)
        return f"Edited {path}"

    except Exception as e:
        return f"Error: {e}"


def execute_tool(name: str, args: dict) -> str:
    """
    将工具调用分发到相应的实现。

    这是模型的工具调用与实际执行之间的桥梁。
    每个工具返回一个字符串结果，该结果会返回给模型。
    """
    if name == "bash":
        return run_bash(args["command"])
    if name == "read_file":
        return run_read(args["path"], args.get("limit"))
    if name == "write_file":
        return run_write(args["path"], args["content"])
    if name == "edit_file":
        return run_edit(args["path"], args["old_text"], args["new_text"])
    return f"Unknown tool: {name}"


# =============================================================================
# 代理循环 - 这是一切的核心
# =============================================================================

def agent_loop(messages: list) -> list:
    """
    一个函数中的完整代理。

    这是所有编码代理共享的模式：

        while True:
            response = model(messages, tools)
            if no tool calls: return
            execute tools, append results, continue

    模型控制循环：
      - 持续调用工具直到没有更多工具调用
      - 结果成为上下文（作为 "tool" 消息反馈）
      - 内存是自动的（messages 列表累积历史记录）

    为什么这样有效：
      1. 模型决定调用哪些工具、以什么顺序、何时停止
      2. 工具结果为下一个决策提供反馈
      3. 对话历史在轮次之间维护上下文
    """
    while True:
        # 步骤 1: 调用模型
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=TOOLS,
            temperature=0.7
        )

        msg = response.choices[0].message

        # 步骤 2: 保存助手消息
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
        messages.append(assistant_msg)

        # 打印文本输出
        if msg.content:
            print(msg.content)

        # 步骤 3: 如果没有工具调用，任务完成
        if not msg.tool_calls:
            return messages

        # 步骤 4: 执行每个工具并收集结果
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            # 显示正在执行的内容
            print(f"\n> {func_name}: {func_args}")

            # 执行并显示结果预览
            output = execute_tool(func_name, func_args)
            preview = output[:200] + "..." if len(output) > 200 else output
            print(f"  {preview}")

            # 为模型收集结果
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })


# =============================================================================
# 主 REPL
# =============================================================================

def main():
    """
    用于交互使用的简单读取-求值-打印循环。

    history 列表在轮次之间维护对话上下文，
    允许具有内存的多轮对话。
    """
    print(f"Mini Claude Code v1 (GLM) - {WORKDIR}")
    print("Type 'exit' to quit.\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break

        # 将用户消息添加到历史记录
        history.append({"role": "user", "content": user_input})

        try:
            # 运行代理循环
            agent_loop(history)
        except Exception as e:
            print(f"Error: {e}")

        print()  # 轮次之间的空行


if __name__ == "__main__":
    main()
