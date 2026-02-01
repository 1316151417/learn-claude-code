#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v4_skills_agent_glm.py - Mini Claude Code: 技能机制 (~550 行，GLM 版本)

使用智谱 GLM-4.7 API 的版本

核心哲学: "知识外部化"
============================================
v3 给了我们用于任务分解的子代理。但有一个更深层的问题：

    模型如何知道如何处理领域特定的任务？

- 处理 PDF？它需要知道 pdftotext vs PyMuPDF
- 构建 MCP 服务器？它需要协议规范和最佳实践
- 代码审查？它需要系统化的检查清单

这些知识不是工具 - 它是专业知识。技能通过让
模型按需加载领域知识来解决这个问题。

范式转移：知识外部化
--------------------------------------------
传统 AI：知识锁定在模型参数中
  - 要教授新技能：收集数据 -> 训练 -> 部署
  - 成本：$10K-$1M+，时间线：数周
  - 需要 ML 专业知识，GPU 集群

技能：知识存储在可编辑文件中
  - 要教授新技能：编写 SKILL.md 文件
  - 成本：免费，时间线：数分钟
  - 任何人都可以做到

这就像附加一个可热插拔的 LoRA 适配器，而无需任何训练！

工具 vs 技能：
---------------
    | 概念    | 它是什么              | 示例                    |
    |---------|---------------------|---------------------------|
    | **工具** | 模型**能**做什么       | bash, read_file, write    |
    | **技能** | 模型**知道如何**做     | PDF 处理，MCP 开发       |

工具是能力。技能是知识。

渐进式披露：
----------------------
    第 1 层：元数据（始终加载）      ~100 tokens/skill
             只有 name + description

    第 2 层：SKILL.md 主体（按需触发） ~2000 tokens
             详细指令

    第 3 层：资源（按需）              无限制
             scripts/、references/、assets/

这保持上下文精简，同时允许任意深度。

SKILL.md 标准：
-----------------
    skills/
    |-- pdf/
    |   |-- SKILL.md          # 必需：YAML frontmatter + Markdown 主体
    |-- mcp-builder/
    |   |-- SKILL.md
    |   |-- references/       # 可选：文档、规范
    |-- code-review/
        |-- SKILL.md
        |-- scripts/          # 可选：辅助脚本

缓存友好注入：
--------------------------
关键洞察：技能内容进入 tool_result（用户消息），
而不是 system prompt。这保留提示词缓存！

    错误：每次编辑 system prompt（缓存失效，成本增加 20-50 倍）
    正确：将技能作为 tool_result 追加（前缀不变，缓存命中）

这就是生产版 Claude Code 的工作方式 - 也是它成本高效的原因。

用法：
    python v4_skills_agent_glm.py
"""

import os
import sys
import json
import re
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
SKILLS_DIR = WORKDIR / "skills"

client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", "your_api_key_here"),
    base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
)
MODEL = os.getenv("MODEL_ID", "glm-4.7")


# =============================================================================
# SkillLoader - v4 的核心新增内容
# =============================================================================

class SkillLoader:
    """
    从 SKILL.md 文件加载和管理技能。

    一个技能是一个包含以下内容的文件夹：
    - SKILL.md (必需)：YAML frontmatter + markdown 指令
    - scripts/ (可选)：模型可以运行的辅助脚本
    - references/ (可选)：额外文档
    - assets/ (可选)：输出的模板、文件

    SKILL.md 格式：
    ----------------
        ---
        name: pdf
        description: 处理 PDF 文件。用于读取、创建或合并 PDF 时。
        ---

        # PDF 处理技能

        ## 读取 PDF

        使用 pdftotext 进行快速提取：
        ```bash
        pdftotext input.pdf -
        ```
        ...

    YAML frontmatter 提供元数据（name, description）。
    Markdown 主体提供详细指令。
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self.load_skills()

    def parse_skill_md(self, path: Path) -> dict:
        """
        将 SKILL.md 文件解析为元数据和主体。

        返回包含：name, description, body, path, dir 的字典
        如果文件不匹配格式则返回 None。
        """
        content = path.read_text()

        # 在 --- 标记之间匹配 YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None

        frontmatter, body = match.groups()

        # 解析类 YAML frontmatter（简单的 key: value）
        metadata = {}
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")

        # 需要 name 和 description
        if "name" not in metadata or "description" not in metadata:
            return None

        return {
            "name": metadata["name"],
            "description": metadata["description"],
            "body": body.strip(),
            "path": path,
            "dir": path.parent,
        }

    def load_skills(self):
        """
        扫描技能目录并加载所有有效的 SKILL.md 文件。

        启动时只加载元数据 - 主体按需加载。
        这保持初始上下文精简。
        """
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            skill = self.parse_skill_md(skill_md)
            if skill:
                self.skills[skill["name"]] = skill

    def get_descriptions(self) -> str:
        """
        为系统提示词生成技能描述。

        这是第 1 层 - 只有 name 和 description，每个技能约 100 tokens。
        完整内容（第 2 层）仅在调用 Skill 工具时加载。
        """
        if not self.skills:
            return "(没有可用技能)"

        return "\n".join(
            f"- {name}: {skill['description']}"
            for name, skill in self.skills.items()
        )

    def get_skill_content(self, name: str) -> str:
        """
        获取用于注入的完整技能内容。

        这是第 2 层 - 完整的 SKILL.md 主体，加上任何可用的
        资源（第 3 层提示）。

        如果技能未找到则返回 None。
        """
        if name not in self.skills:
            return None

        skill = self.skills[name]
        content = f"# Skill: {skill['name']}\n\n{skill['body']}"

        # 列出可用资源（第 3 层提示）
        resources = []
        for folder, label in [
            ("scripts", "脚本"),
            ("references", "参考"),
            ("assets", "资源")
        ]:
            folder_path = skill["dir"] / folder
            if folder_path.exists():
                files = list(folder_path.glob("*"))
                if files:
                    resources.append(f"{label}: {', '.join(f.name for f in files)}")

        if resources:
            content += f"\n\n**{skill['dir']} 中的可用资源：**\n"
            content += "\n".join(f"- {r}" for r in resources)

        return content

    def list_skills(self) -> list:
        """返回可用技能名称列表。"""
        return list(self.skills.keys())


# 全局技能加载器实例
SKILLS = SkillLoader(SKILLS_DIR)


# =============================================================================
# 代理类型注册表（来自 v3）
# =============================================================================

AGENT_TYPES = {
    "explore": {
        "description": "只读代理，用于探索代码、查找文件、搜索",
        "tools": ["bash", "read_file"],
        "prompt": "你是一个探索代理。搜索和分析，但永远不要修改文件。返回简洁的摘要。",
    },
    "code": {
        "description": "完整代理，用于实现功能和修复 bug",
        "tools": "*",
        "prompt": "你是一个编码代理。高效地实现请求的更改。",
    },
    "plan": {
        "description": "规划代理，用于设计实现策略",
        "tools": ["bash", "read_file"],
        "prompt": "你是一个规划代理。分析代码库并输出编号的实现计划。不要做更改。",
    },
}


def get_agent_descriptions() -> str:
    """为系统提示词生成代理类型描述。"""
    return "\n".join(
        f"- {name}: {cfg['description']}"
        for name, cfg in AGENT_TYPES.items()
    )


# =============================================================================
# TodoManager（来自 v2）
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
# 系统提示词 - v4 更新版
# =============================================================================

SYSTEM = f"""你是位于 {WORKDIR} 的编码代理。

循环：规划 -> 使用工具行动 -> 报告。

**可用技能**（任务匹配时使用 Skill 工具）：
{SKILLS.get_descriptions()}

**可用子代理**（对需要专注探索或实现的子任务使用 Task 工具）：
{get_agent_descriptions()}

规则：
- 当任务匹配技能描述时，立即使用 Skill 工具
- 对需要专注探索或实现的子任务使用 Task 工具
- 使用 TodoWrite 跟踪多步工作
- 优先使用工具而非文字。行动，而不只是解释。
- 完成后，总结更改内容。"""


# =============================================================================
# 工具定义
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

# Task 工具（来自 v3）
TASK_TOOL = {
    "type": "function",
    "function": {
        "name": "Task",
        "description": f"生成一个子代理来处理专注的子任务。\n\n代理类型：\n{get_agent_descriptions()}",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "简短任务描述（3-5 个词）"
                },
                "prompt": {
                    "type": "string",
                    "description": "子代理的详细指令"
                },
                "agent_type": {
                    "type": "string",
                    "enum": list(AGENT_TYPES.keys())
                },
            },
            "required": ["description", "prompt", "agent_type"],
        },
    },
}

# v4 新增：Skill 工具
SKILL_TOOL = {
    "type": "function",
    "function": {
        "name": "Skill",
        "description": f"""加载技能以获得任务的专业知识。

可用技能：
{SKILLS.get_descriptions()}

何时使用：
- 当用户任务匹配技能描述时立即使用
- 在尝试领域特定工作之前（PDF、MCP 等）

技能内容将被注入到对话中，为您提供详细指令和资源访问。""",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "要加载的技能名称"
                }
            },
            "required": ["skill"],
        },
    },
}

ALL_TOOLS = BASE_TOOLS + [TASK_TOOL, SKILL_TOOL]


def get_tools_for_agent(agent_type: str) -> list:
    """根据代理类型过滤工具。"""
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")
    if allowed == "*":
        return BASE_TOOLS
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
    """执行 shell 命令。"""
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


def run_skill(skill_name: str) -> str:
    """
    加载技能并将其注入到对话中。

    这是关键机制：
    1. 获取技能内容（SKILL.md 主体 + 资源提示）
    2. 将其包装在 <skill-loaded> 标签中返回
    3. 模型将此作为 tool_result（用户消息）接收
    4. 模型现在"知道"如何执行任务

    为什么是 tool_result 而不是 system prompt？
    - System prompt 更改会使缓存失效（成本增加 20-50 倍）
    - Tool 结果追加到末尾（前缀不变，缓存命中）

    这就是生产系统保持成本高效的方式。
    """
    content = SKILLS.get_skill_content(skill_name)

    if content is None:
        available = ", ".join(SKILLS.list_skills()) or "无"
        return f"错误: 未知技能 '{skill_name}'。可用: {available}"

    # 包装在标签中，以便模型知道它是技能内容
    return f"""<skill-loaded name="{skill_name}">
{content}
</skill-loaded>

按照上述技能中的说明完成用户的任务。"""


def run_task(description: str, prompt: str, agent_type: str) -> str:
    """执行子代理任务（来自 v3）。详见 v3。"""
    if agent_type not in AGENT_TYPES:
        return f"错误: 未知的代理类型 '{agent_type}'"

    config = AGENT_TYPES[agent_type]
    sub_system = f"""你是位于 {WORKDIR} 的 {agent_type} 子代理。

{config["prompt"]}

完成任务并返回清晰、简洁的摘要。"""

    sub_tools = get_tools_for_agent(agent_type)
    sub_messages = [{"role": "user", "content": prompt}]

    print(f"  [{agent_type}] {description}")
    start = time.time()
    tool_count = 0

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
    if name == "Skill":
        return run_skill(args["skill"])
    return f"未知工具: {name}"


# =============================================================================
# 主代理循环
# =============================================================================

def agent_loop(messages: list) -> list:
    """
    支持技能的主代理循环。

    与 v3 相同的模式，但现在带有 Skill 工具。
    当模型加载技能时，它接收领域知识。
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

            # 不同工具类型的特殊显示
            if func_name == "Task":
                print(f"\n> Task: {func_args.get('description', '子任务')}")
            elif func_name == "Skill":
                print(f"\n> 正在加载技能: {func_args.get('skill', '?')}")
            else:
                print(f"\n> {func_name}: {func_args}")

            output = execute_tool(func_name, func_args)

            # Skill 工具显示摘要，不是完整内容
            if func_name == "Skill":
                print(f"  技能已加载 ({len(output)} 字符)")
            elif func_name != "Task":
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
    print(f"Mini Claude Code v4 (带技能) - {WORKDIR}")
    print(f"技能: {', '.join(SKILLS.list_skills()) or '无'}")
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
