#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v3_subagent_glm.py - Mini Claude Code: 子代理机制 (~450 行，GLM 版本)

使用智谱 GLM-4.7 API 的版本

核心哲学: "分而治之，上下文隔离"
=============================================================
v2 添加了规划。但对于像"探索代码库然后重构认证"这样的大型任务，
单个代理会遇到问题：

问题 - 上下文污染：
-------------------------------
    单代理历史记录：
      [探索中...] cat file1.py -> 500 行
      [探索中...] cat file2.py -> 300 行
      ... 还有 15 个文件 ...
      [现在重构...] "等等，file1 里面有什么？"

模型的上下文充满了探索细节，留给实际任务的空间很少。
这就是"上下文污染"。

解决方案 - 带有隔离上下文的子代理：
----------------------------------------------
    主代理历史记录：
      [任务: 探索代码库]
        -> 子代理探索 20 个文件（在自己的上下文中）
        -> 仅返回："认证在 src/auth/，数据库在 src/models/"
      [现在使用干净的上下文重构]

每个子代理都有：
  1. 自己的全新消息历史
  2. 过滤的工具（explore 不能写）
  3. 专门的系统提示词
  4. 只向父代理返回最终摘要

关键洞察：
---------------
    进程隔离 = 上下文隔离

通过生成子任务，我们获得：
  - 主代理的干净上下文
  - 可能的并行探索
  - 自然的任务分解
  - 相同的代理循环，不同的上下文

代理类型注册表：
-------------------
    | 类型    | 工具               | 目的                     |
    |---------|---------------------|---------------------------- |
    | explore | bash, read_file     | 只读探索                  |
    | code    | 所有工具            | 完整实现访问               |
    | plan    | bash, read_file     | 设计而不修改               |

典型流程：
-------------
    用户: "重构认证以使用 JWT"

    主代理：
      1. Task(explore): "查找所有与认证相关的文件"
         -> 子代理读取 10 个文件
         -> 返回："认证在 src/auth/login.py..."

      2. Task(plan): "设计 JWT 迁移"
         -> 子代理分析结构
         -> 返回："1. 添加 jwt 库 2. 创建 utils..."

      3. Task(code): "实现 JWT 令牌"
         -> 子代理编写代码
         -> 返回："已创建 jwt_utils.py，更新了 login.py"

      4. 向用户总结更改

用法：
    python v3_subagent_glm.py
"""

import os
import sys
import json
import subprocess
import time
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
# 代理类型注册表 - 子代理机制的核心
# =============================================================================

AGENT_TYPES = {
    # Explore: 用于搜索和分析的只读代理
    # 不能修改文件 - 适合广泛探索
    "explore": {
        "description": "只读代理，用于探索代码、查找文件、搜索",
        "tools": ["bash", "read_file"],  # 没有写权限
        "prompt": "你是一个探索代理。搜索和分析，但永远不要修改文件。返回简洁的摘要。",
    },

    # Code: 用于实现的完全代理
    # 拥有所有工具 - 用于实际编码工作
    "code": {
        "description": "完整代理，用于实现功能和修复 bug",
        "tools": "*",  # 所有工具
        "prompt": "你是一个编码代理。高效地实现请求的更改。",
    },

    # Plan: 用于设计工作的分析代理
    # 只读，专注于生成计划和策略
    "plan": {
        "description": "规划代理，用于设计实现策略",
        "tools": ["bash", "read_file"],  # 只读
        "prompt": "你是一个规划代理。分析代码库并输出编号的实现计划。不要做更改。",
    },
}


def get_agent_descriptions() -> str:
    """为 Task 工具生成代理类型描述。"""
    return "\n".join(
        f"- {name}: {cfg['description']}"
        for name, cfg in AGENT_TYPES.items()
    )


# =============================================================================
# TodoManager（来自 v2，未改变）
# =============================================================================

class TodoManager:
    """任务列表管理器，带约束。详见 v2。"""

    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        validated = []
        in_progress = 0

        for i, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active = str(item.get("activeForm", "")).strip()

            if not content or not active:
                raise ValueError(f"第 {i} 项: content 和 activeForm 是必需的")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"第 {i} 项: 无效的 status")
            if status == "in_progress":
                in_progress += 1

            validated.append({
                "content": content,
                "status": status,
                "activeForm": active
            })

        if in_progress > 1:
            raise ValueError("一次只能有一个任务处于 in_progress 状态")

        self.items = validated[:20]
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "没有任务。"
        lines = []
        for t in self.items:
            mark = "[x]" if t["status"] == "completed" else \
                   "[>]" if t["status"] == "in_progress" else "[ ]"
            lines.append(f"{mark} {t['content']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        return "\n".join(lines) + f"\n({done}/{len(self.items)} 已完成)"


TODO = TodoManager()


# =============================================================================
# 系统提示词
# =============================================================================

SYSTEM = f"""你是位于 {WORKDIR} 的编码代理。

循环：规划 -> 使用工具行动 -> 报告。

你可以为复杂的子任务生成子代理：
{get_agent_descriptions()}

规则：
- 对需要专注探索或实现的子任务使用 Task 工具
- 使用 TodoWrite 跟踪多步工作
- 优先使用工具而非文字。行动，而不只是解释。
- 完成后，总结更改内容。"""


# =============================================================================
# 基础工具定义
# =============================================================================

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "运行 shell 命令。用于：ls, find, grep, git, npm, python 等",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。返回 UTF-8 文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["path"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "将内容写入文件。如需要会创建父目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "替换文件中的精确文本。用于精确修改。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": "更新任务列表。用于规划和跟踪进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"]
                                },
                                "activeForm": {"type": "string"},
                            },
                            "required": ["content", "status", "activeForm"],
                        }
                    }
                },
                "required": ["items"],
            },
        }
    },
]


# =============================================================================
# Task 工具 - v3 的核心新增内容
# =============================================================================

TASK_TOOL = {
    "type": "function",
    "function": {
        "name": "Task",
        "description": f"""生成一个子代理来处理专注的子任务。

子代理在隔离的上下文中运行 - 它们看不到父代理的历史。
使用此工具保持主对话干净。

代理类型：
{get_agent_descriptions()}

使用示例：
- Task(explore): "查找所有使用认证模块的文件"
- Task(plan): "设计数据库迁移策略"
- Task(code): "实现用户注册表单"
""",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "短任务名称（3-5 个词）用于进度显示"
                },
                "prompt": {
                    "type": "string",
                    "description": "子代理的详细指令"
                },
                "agent_type": {
                    "type": "string",
                    "enum": list(AGENT_TYPES.keys()),
                    "description": "要生成的代理类型"
                },
            },
            "required": ["description", "prompt", "agent_type"],
        },
    },
}

# 主代理获得所有工具包括 Task
ALL_TOOLS = BASE_TOOLS + [TASK_TOOL]


def get_tools_for_agent(agent_type: str) -> list:
    """
    根据代理类型过滤工具。

    每个代理类型都有一个允许的工具白名单。
    '*' 表示所有工具（但子代理不获取 Task 以防止无限递归）。
    """
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")

    if allowed == "*":
        return BASE_TOOLS  # 所有基础工具，但不包括 Task（演示中没有递归）

    return [t for t in BASE_TOOLS if t["name"] in allowed]


# =============================================================================
# 工具实现
# =============================================================================

def safe_path(p: str) -> Path:
    """确保路径保持在工作区内（安全措施）。"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"路径逃逸工作区: {p}")
    return path


def run_bash(cmd: str) -> str:
    """执行 shell 命令并进行安全检查。"""
    # Windows 命令转换
    if sys.platform == "win32":
        cmd_map = {
            "ls": "dir",
            "cat": "type",
            "grep": "findstr",
            "rm": "del",
            "mv": "move",
            "cp": "copy",
            "pwd": "cd",
        }
        for unix_cmd, win_cmd in cmd_map.items():
            if cmd.strip().startswith(unix_cmd + " ") or cmd.strip() == unix_cmd:
                cmd = cmd.replace(unix_cmd, win_cmd, 1)
                break

    if any(d in cmd for d in ["rm -rf /", "sudo", "shutdown", "reboot"]):
        return "错误: 危险命令被阻止"
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=60
        )
        return ((r.stdout + r.stderr).strip() or "(无输出)")[:50000]
    except Exception as e:
        return f"错误: {e}"


def run_read(path: str, limit: int = None) -> str:
    """读取文件内容。"""
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit:
            lines = lines[:limit]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"错误: {e}"


def run_write(path: str, content: str) -> str:
    """将内容写入文件。"""
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"写入 {len(content)} 字节到 {path}"
    except Exception as e:
        return f"错误: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """替换文件中的精确文本。"""
    try:
        fp = safe_path(path)
        text = fp.read_text()
        if old_text not in text:
            return f"错误: 在 {path} 中未找到文本"
        fp.write_text(text.replace(old_text, new_text, 1))
        return f"已编辑 {path}"
    except Exception as e:
        return f"错误: {e}"


def run_todo(items: list) -> str:
    """更新 todo 列表。"""
    try:
        return TODO.update(items)
    except Exception as e:
        return f"错误: {e}"


# =============================================================================
# 子代理执行 - v3 的核心
# =============================================================================

def run_task(description: str, prompt: str, agent_type: str) -> str:
    """
    执行带有隔离上下文的子代理任务。

    这是子代理机制的核心：

    1. 创建隔离的消息历史（关键：没有父上下文！）
    2. 使用代理特定的系统提示词
    3. 根据代理类型过滤可用工具
    4. 运行与主代理相同的查询循环
    5. 只返回最终文本（不是中间细节）

    父代理只看到摘要，保持其上下文干净。

    进度显示：
    ----------------
    运行时，我们显示：
      [explore] 查找认证文件 ... 5 个工具，3.2秒

    这提供了可见性，而不会污染主对话。
    """
    if agent_type not in AGENT_TYPES:
        return f"错误: 未知的代理类型 '{agent_type}'"

    config = AGENT_TYPES[agent_type]

    # 代理特定的系统提示词
    sub_system = f"""你是位于 {WORKDIR} 的 {agent_type} 子代理。

{config["prompt"]}

完成任务并返回清晰、简洁的摘要。"""

    # 为此代理类型过滤的工具
    sub_tools = get_tools_for_agent(agent_type)

    # 隔离的消息历史 - 这是关键！
    # 子代理重新开始，看不到父对话
    sub_messages = [{"role": "user", "content": prompt}]

    # 进度跟踪
    print(f"  [{agent_type}] {description}")
    start = time.time()
    tool_count = 0

    # 运行相同的代理循环（静默 - 不打印到主聊天）
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": sub_system}] + sub_messages,
            tools=sub_tools,
            temperature=0.7
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            break

        # 保存助手消息
        sub_messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
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
        })

        results = []

        for tc in msg.tool_calls:
            tool_count += 1
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments)
            output = execute_tool(func_name, func_args)
            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output
            })

            # 更新进度行（就地）
            elapsed = time.time() - start
            sys.stdout.write(
                f"\r  [{agent_type}] {description} ... {tool_count} 工具, {elapsed:.1f}秒"
            )
            sys.stdout.flush()

        sub_messages.append({"role": "user", "content": results})

    # 最终进度更新
    elapsed = time.time() - start
    sys.stdout.write(
        f"\r  [{agent_type}] {description} - 完成 ({tool_count} 工具, {elapsed:.1f}秒)\n"
    )

    # 提取并只返回最终文本
    # 这是父代理看到的 - 干净的摘要
    if msg.content:
        return msg.content

    return "(子代理没有返回文本)"


def execute_tool(name: str, args: dict) -> str:
    """将工具调用分发到实现。"""
    if name == "bash":
        return run_bash(args["command"])
    if name == "read_file":
        return run_read(args["path"], args.get("limit"))
    if name == "write_file":
        return run_write(args["path"], args["content"])
    if name == "edit_file":
        return run_edit(args["path"], args["old_text"], args["new_text"])
    if name == "TodoWrite":
        return run_todo(args["items"])
    if name == "Task":
        return run_task(args["description"], args["prompt"], args["agent_type"])
    return f"未知工具: {name}"


# =============================================================================
# 主代理循环
# =============================================================================

def agent_loop(messages: list) -> list:
    """
    支持子代理的主代理循环。

    与 v1/v2 相同的模式，但现在包括 Task 工具。
    当模型调用 Task 时，它生成一个带有隔离上下文的子代理。
    """
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=ALL_TOOLS,
            temperature=0.7
        )

        msg = response.choices[0].message

        # 保存助手消息
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

        # 如果没有工具调用，任务完成
        if not msg.tool_calls:
            return messages

        # 执行每个工具并收集结果
        results = []
        for tc in msg.tool_calls:
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments)

            # Task 工具有特殊的显示处理
            if func_name == "Task":
                print(f"\n> Task: {func_args.get('description', '子任务')}")
            else:
                print(f"\n> {func_name}: {func_args}")

            output = execute_tool(func_name, func_args)

            # 不打印完整的 Task 输出（它管理自己的显示）
            if func_name != "Task":
                preview = output[:200] + "..." if len(output) > 200 else output
                print(f"  {preview}")

            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output
            })

        # 分别添加每个工具结果到消息历史
        for result in results:
            messages.append(result)


# =============================================================================
# 主 REPL
# =============================================================================

def main():
    print(f"Mini Claude Code v3 (带子代理) - {WORKDIR}")
    print(f"代理类型: {', '.join(AGENT_TYPES.keys())}")
    print("输入 'exit' 退出。\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break

        history.append({"role": "user", "content": user_input})

        try:
            agent_loop(history)
        except Exception as e:
            print(f"错误: {e}")

        print()


if __name__ == "__main__":
    main()
