#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v2_todo_agent_glm.py - Mini Claude Code: 结构化规划 (~300 行，GLM 版本)

使用智谱 GLM-4.7 API 的版本

核心哲学: "让计划可见"
=====================================
v1 适用于简单任务。但要求它"重构认证、添加测试、更新文档"，
看看会发生什么。如果没有显式规划，模型会：
  - 在任务之间随机跳转
  - 忘记已完成的步骤
  - 中途失去焦点

问题 - "上下文淡化":
----------------------------
在 v1 中，计划只存在于模型的"脑海"中：

    v1: "我会做 A，然后 B，然后 C"  (不可见)
        10 轮工具调用后: "等等，我在做什么？"

解决方案 - TodoWrite 工具：
-----------------------------
v2 添加了一个新工具，从根本上改变了代理的工作方式：

    v2:
      [ ] 重构认证模块
      [>] 添加单元测试         <- 当前正在做这个
      [ ] 更新文档

现在你和模型都能看到计划。模型可以：
  - 工作时更新状态
  - 看到什么完成了、什么待做
  - 保持专注于一个任务

关键约束（不是随意的 - 这些是护栏）：
------------------------------------------------------
    | 规则              | 原因                              |
    |-------------------|----------------------------------|
    | 最多 20 项        | 防止无限任务列表                    |
    | 只有一个进行中    | 强制聚焦于一件事                    |
    | 必填字段          | 确保结构化输出                      |

深层洞察：
----------------
> "结构约束并使能。"

Todo 约束（最多项、一个进行中）使能（可见计划、跟踪进度）。

这个模式出现在代理设计的任何地方：
  - max_tokens 约束 -> 使能可管理的响应
  - Tool schemas 约束 -> 使能结构化调用
  - Todos 约束 -> 使能复杂任务完成

好的约束不是限制。它们是脚手架。

用法：
    python v2_todo_agent_glm.py
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
# TodoManager - v2 的核心新增内容
# =============================================================================

class TodoManager:
    """
    管理带有强制约束的结构化任务列表。

    关键设计决策：
    --------------------
    1. 最多 20 项：防止模型创建无限列表
    2. 只有一个 in_progress：强制聚焦 - 一次只能做一件事
    3. 必填字段：每项都需要 content、status 和 activeForm

    activeForm 字段需要解释：
    - 它是正在发生的事情的现在时态形式
    - 当 status 为 "in_progress" 时显示
    - 例如: content="添加测试", activeForm="正在添加单元测试..."

    这提供了对代理正在做什么的实时可见性。
    """

    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        """
        验证并更新 todo 列表。

        模型每次发送一个完整的新列表。我们验证它，
        存储它，并返回渲染后的视图，模型将看到该视图。

        验证规则：
        - 每个项目必须有: content, status, activeForm
        - Status 必须是: pending | in_progress | completed
        - 只能有一项可以处于 in_progress 状态
        - 最多允许 20 个项目

        返回:
            todo 列表的渲染文本视图
        """
        validated = []
        in_progress_count = 0

        for i, item in enumerate(items):
            # 提取并验证字段
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active_form = str(item.get("activeForm", "")).strip()

            # 验证检查
            if not content:
                raise ValueError(f"第 {i} 项: content 是必需的")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"第 {i} 项: 无效的 status '{status}'")
            if not active_form:
                raise ValueError(f"第 {i} 项: activeForm 是必需的")

            if status == "in_progress":
                in_progress_count += 1

            validated.append({
                "content": content,
                "status": status,
                "activeForm": active_form
            })

        # 强制约束
        if len(validated) > 20:
            raise ValueError("最多允许 20 个 todos")
        if in_progress_count > 1:
            raise ValueError("一次只能有一个任务处于 in_progress 状态")

        self.items = validated
        return self.render()

    def render(self) -> str:
        """
        将 todo 列表渲染为人类可读的文本。

        格式:
            [x] 已完成的任务
            [>] 进行中的任务 <- 正在做什么...
            [ ] 待办任务

            (2/3 已完成)

        这个渲染后的文本是模型看到的工具结果。
        然后它可以根据其当前状态更新列表。
        """
        if not self.items:
            return "没有 todos。"

        lines = []
        for item in self.items:
            if item["status"] == "completed":
                lines.append(f"[x] {item['content']}")
            elif item["status"] == "in_progress":
                lines.append(f"[>] {item['content']} <- {item['activeForm']}")
            else:
                lines.append(f"[ ] {item['content']}")

        completed = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({completed}/{len(self.items)} 已完成)")

        return "\n".join(lines)


# 全局 todo 管理器实例
TODO = TodoManager()


# =============================================================================
# 系统提示词 - v2 更新版
# =============================================================================

SYSTEM = f"""你是位于 {WORKDIR} 的编码代理。

工作流程：
1. 先用 TodoWrite 创建任务计划（必需！）
2. 标记当前任务为 in_progress
3. 使用工具执行任务
4. 完成后标记为 completed
5. 继续下一个任务

规则：
- **每个任务都必须先用 TodoWrite 规划**
- 一次只能有一个任务处于 in_progress 状态
- 优先使用工具而非文字。行动，而不只是解释。
- 完成所有任务后，总结更改内容。

注意：当前是 Windows 环境，常见命令已自动转换（ls→dir, cat→type, grep→findstr）。"""


# =============================================================================
# 系统提醒 - 软提示鼓励 todo 使用
# =============================================================================

# 在对话开始时显示
INITIAL_REMINDER = """<reminder>重要：请先使用 TodoWrite 工具创建任务计划，即使对于看似简单的任务也应先规划。

规划格式示例：
TodoWrite(items=[
  {"content": "列出目录文件", "status": "in_progress", "activeForm": "正在列出目录文件"},
  {"content": "读取关键文件", "status": "pending", "activeForm": "准备读取关键文件"},
  {"content": "总结项目结构", "status": "pending", "activeForm": "准备总结项目结构"}
])

养成先规划后执行的习惯！</reminder>"""

# 如果模型有一段时间没有更新 todos，则显示
NAG_REMINDER = "<reminder>10+ 轮没有更新 todo。请更新 todos。</reminder>"


# =============================================================================
# 工具定义 (v1 工具 + TodoWrite)
# =============================================================================

TOOLS = [
    # v1 工具（未改变）
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "运行 shell 命令。用于：ls, find, grep, git, npm, python 等。（Windows 上会自动转换 Unix 命令：ls→dir, cat→type, grep→findstr）",
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
                    }
                },
                "required": ["path"]
            }
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
                    "path": {
                        "type": "string",
                        "description": "文件的相对路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的内容"
                    }
                },
                "required": ["path", "content"]
            }
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
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },

    # v2 新增: TodoWrite
    # 这是使能结构化规划的关键添加
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
                        "description": "完整任务列表（替换现有）",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "任务描述"
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "任务状态"
                                },
                                "activeForm": {
                                    "type": "string",
                                    "description": "现在时态动作，例如 '正在读取文件'"
                                },
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
# 工具实现 (v1 + TodoWrite)
# =============================================================================

def safe_path(p: str) -> Path:
    """确保路径保持在工作区内（安全措施）。"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"路径逃逸工作区: {p}")
    return path


def run_bash(cmd: str) -> str:
    """执行 shell 命令并进行安全检查。"""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    if any(d in cmd for d in dangerous):
        return "错误: 危险命令被阻止"

    # Windows 命令转换（模型习惯用 Unix 命令）
    if sys.platform == "win32":
        # 将常见 Unix 命令转换为 Windows 等效命令
        cmd_map = {
            "ls": "dir",
            "cat": "type",
            "grep": "findstr",
            "rm": "del",
            "mv": "move",
            "cp": "copy",
            "pwd": "cd",
        }
        # 简单替换（只替换命令开头的）
        for unix_cmd, win_cmd in cmd_map.items():
            if cmd.strip().startswith(unix_cmd + " ") or cmd.strip() == unix_cmd:
                cmd = cmd.replace(unix_cmd, win_cmd, 1)
                break

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=60
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "错误: 超时"
    except Exception as e:
        return f"错误: {e}"


def run_read(path: str, limit: int = None) -> str:
    """读取文件内容。"""
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(text.splitlines()) - limit} 更多行)"]
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
        content = fp.read_text()
        if old_text not in content:
            return f"错误: 在 {path} 中未找到文本"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"已编辑 {path}"
    except Exception as e:
        return f"错误: {e}"


def run_todo(items: list) -> str:
    """
    更新 todo 列表。

    模型发送一个完整的新列表（不是差异）。
    我们验证它并返回渲染后的视图。
    """
    try:
        return TODO.update(items)
    except Exception as e:
        return f"错误: {e}"


def execute_tool(name: str, args: dict) -> str:
    """将工具调用分发到相应的实现。"""
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
    return f"未知工具: {name}"


# =============================================================================
# 代理循环（带 todo 跟踪）
# =============================================================================

# 跟踪自上次 todo 更新以来的轮数
rounds_without_todo = 0


def agent_loop(messages: list) -> list:
    """
    带 todo 使用跟踪的代理循环。

    与 v1 相同的核心循环，但现在我们跟踪模型是否使用 todos。
    如果太久没有更新，我们在下一条用户消息中注入提醒。
    """
    global rounds_without_todo

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
        results = []
        used_todo = False

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
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })

            # 追踪 todo 使用
            if func_name == "TodoWrite":
                used_todo = True

        # 更新计数器：如果使用了 todo 则重置，否则递增
        if used_todo:
            rounds_without_todo = 0
        else:
            rounds_without_todo += 1

        # 如果模型超过 10 轮没有使用 todos，注入 NAG_REMINDER
        # 这发生在 agent_loop 内部，所以模型在任务执行期间看到它
        if rounds_without_todo > 10:
            messages.append({"role": "user", "content": NAG_REMINDER})

        # 分别添加每个工具结果到消息历史
        # GLM API 不支持 content 作为列表
        for result in results:
            messages.append(result)


# =============================================================================
# 主 REPL
# =============================================================================

def main():
    """
    带提醒注入的 REPL。

    v2 关键添加：我们注入"reminder"消息来鼓励
    todo 使用而不强制它。这是一个软约束。

    - INITIAL_REMINDER: 在对话开始时注入
    - NAG_REMINDER: 在 agent_loop 中当 10+ 轮没有 todo 时注入
    """
    global rounds_without_todo

    print(f"Mini Claude Code v2 (带 Todos) - {WORKDIR}")
    print("输入 'exit' 退出。\n")

    history = []
    first_message = True

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("exit", "quit", "q"):
            break

        # 构建用户消息内容
        content = []

        if first_message:
            # 在对话开始时温柔提醒
            content.append({"type": "text", "text": INITIAL_REMINDER})
            first_message = False

        content.append({"type": "text", "text": user_input})

        # 注意：GLM API 的消息格式需要调整
        # 对于带有 content 数组的消息，我们需要特殊处理
        if len(content) == 1:
            # 只有用户输入，直接使用字符串
            history.append({"role": "user", "content": user_input})
        else:
            # 有提醒，合并为字符串
            combined = "\n".join(c["text"] for c in content)
            history.append({"role": "user", "content": combined})

        try:
            # 运行代理循环
            agent_loop(history)
        except Exception as e:
            print(f"错误: {e}")

        print()  # 轮次之间的空行


if __name__ == "__main__":
    main()
