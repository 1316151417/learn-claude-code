# v1_basic_agent_glm.py 代码精读

**GLM-4 版本的四工具代理完整解析**

---

## 目录

1. [文件头与导入](#1-文件头与导入)
2. [核心配置](#2-核心配置)
3. [系统提示词](#3-系统提示词)
4. [工具定义](#4-工具定义)
5. [工具实现](#5-工具实现)
6. [代理循环](#6-代理循环)
7. [主程序入口](#7-主程序入口)
8. [完整流程图](#8-完整流程图)

---

## 1. 文件头与导入

```python
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
...
"""
```

### 核心哲学解析

```
┌─────────────────────────────────────────────────────────────┐
│                  "模型即代理" 的含义                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  传统聊天机器人：                                             │
│    User → Model → Text Response                             │
│    (一次问答，没有行动能力)                                    │
│                                                             │
│  代理系统：                                                  │
│    User → Model → [Tool -> Result]* -> Response             │
│                          ^________|                          │
│                    (可以重复多次)                            │
│                                                             │
│  关键区别：                                                   │
│    - 模型可以**决定**调用哪些工具                              │
│    - 模型可以**决定**调用顺序                                 │
│    - 模型可以**决定**何时停止                                 │
│                                                             │
│  代码的角色：                                                 │
│    - 提供工具定义                                             │
│    - 运行循环                                                │
│    - 执行工具调用                                             │
│    - 把结果返回给模型                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 导入模块

```python
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
```

### 导入顺序规范

```
标准库导入 → 第三方库导入 → 本地模块导入
    ↓              ↓              ↓
  os, sys       OpenAI        (本例无)
  json         dotenv
  subprocess
  pathlib
```

---

## 2. 核心配置

```python
# =============================================================================
# 配置
# =============================================================================

WORKDIR = Path.cwd()
client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", "your_api_key_here"),
    base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
)
MODEL = os.getenv("MODEL_ID", "glm-4.7")
```

### Path.cwd() vs os.getcwd()

```python
# pathlib 方式 (推荐)
WORKDIR = Path.cwd()
# 返回 Path 对象，支持 / 运算符，跨平台

# os 方式 (传统)
WORKDIR = os.getcwd()
# 返回字符串，路径拼接需要 os.path.join
```

### API 密钥的回退机制

```python
os.getenv("ZHIPU_API_KEY", "your_api_key_here")
#                         ↑
#                    默认值（环境变量不存在时使用）
```

等价于：
```python
key = os.getenv("ZHIPU_API_KEY")
if key is None:
    key = "your_api_key_here"
```

---

## 3. 系统提示词

```python
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
```

### System Prompt 的三层作用

```
┌─────────────────────────────────────────────────────────────┐
│              System Prompt 的三个层面                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 身份定位                                                 │
│     "你是位于 {WORKDIR} 的编码代理"                           │
│     → 告诉模型它在哪里，它的角色是什么                          │
│                                                             │
│  2. 工作流程                                                 │
│     "循环：简短思考 -> 使用工具 -> 报告结果"                  │
│     → 教模型如何行动：思考→工具→报告                            │
│                                                             │
│  3. 行为约束                                                 │
│     "- 优先使用工具而非文字"                                   │
│     "- 不要虚构文件路径"                                      │
│     "- 做最小化修改"                                          │
│     → 防止模型犯错或过度设计                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 动态上下文注入

```python
SYSTEM = f"""你是位于 {WORKDIR} 的编码代理..."""
                               ↑
                        运行时计算，例如：
                        /Users/jiezhou/IdeaProjects/learn-claude-code
```

**为什么重要？**
- 模型知道当前工作目录
- 可以使用相对路径
- 理解项目结构上下文

---

## 4. 工具定义

```python
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
    # ... 其他工具
]
```

### 四大核心工具

| Tool | Purpose | Example | 覆盖场景 |
|------|---------|---------|----------|
| **bash** | 运行任何命令 | `ls`, `git status`, `npm install` | 探索、执行、测试 |
| **read_file** | 读取文件内容 | 查看 `src/index.ts` | 理解代码 |
| **write_file** | 创建/覆盖文件 | 创建 `README.md` | 新建文件 |
| **edit_file** | 精确修改 | 替换函数名 | 小改动 |

### OpenAI Function Calling 格式

```python
TOOL = {
    "type": "function",           # 固定值
    "function": {
        "name": "bash",           # 工具名称
        "description": "...",      # 教 AI 如何使用
        "parameters": {           # JSON Schema 格式
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令"
                }
            },
            "required": ["command"]  # 必填参数
        }
    }
}
```

### 工具完整定义

#### 1. Bash 工具

```python
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
}
```

**Bash 能做什么：**
```bash
# 文件探索
ls -la
find . -name "*.py"
grep -r "TODO" src/

# 代码执行
python main.py
npm test
make build

# 文件操作
cat file.py
echo "content" > new_file.txt
```

#### 2. Read File 工具

```python
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
}
```

**使用场景：**
```python
# 读取完整文件
read_file(path="src/main.py")

# 读取前 50 行（大文件）
read_file(path="src/large_file.py", limit=50)
```

#### 3. Write File 工具

```python
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
}
```

**使用场景：**
```python
# 创建新文件
write_file(
    path="README.md",
    content="# My Project\n..."
)

# 完全重写文件
write_file(
    path="config.json",
    content="{...}"
)
```

#### 4. Edit File 工具

```python
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
}
```

**使用场景：**
```python
# 修改函数名
edit_file(
    path="utils.py",
    old_text="def old_function():",
    new_text="def new_function():"
)

# 修改配置值
edit_file(
    path="config.py",
    old_text='DEBUG = True',
    new_text='DEBUG = False'
)
```

### Description 作为 Prompt

```python
"description": "运行 shell 命令。用于：ls, find, grep, git, npm, python 等"
```

**关键洞察**：`description` 既是文档，也是 prompt！

- AI 阅读后学会：何时调用、如何调用
- 列出常用示例，减少 AI 的尝试次数
- 描述简洁但信息丰富

---

## 5. 工具实现

### 5.1 安全路径处理

```python
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
```

### 路径安全机制

```python
# 示例：防止路径逃逸攻击
WORKDIR = "/home/user/project"

# 正常路径
safe_path("src/main.py")
# → /home/user/project/src/main.py ✅

# 试图逃逸
safe_path("../../../etc/passwd")
# → ValueError: Path escapes workspace ❌

# 解析后检查
safe_path("normal/../etc/passwd")
# → /home/user/project/etc/passwd ✅ (仍在工作区内)
```

### Path 操作详解

```python
# Path 运算符
WORKDIR / "src" / "main.py"
# 等价于 os.path.join(WORKDIR, "src", "main.py")

# .resolve() 解析
(Path("a/b/../c") / "./d").resolve()
# → /absolute/path/a/c/d

# .is_relative_to() 检查
path = Path("/home/user/project/src/main.py")
path.is_relative_to(Path("/home/user/project"))
# → True
```

### 5.2 Bash 实现

```python
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
```

### subprocess.run 参数详解

```python
subprocess.run(
    command,              # 命令字符串
    shell=True,           # 通过 shell 执行（支持管道、重定向）
    cwd=WORKDIR,          # 工作目录
    capture_output=True,  # 捕获 stdout 和 stderr
    text=True,            # 返回字符串而非字节
    timeout=60            # 60秒超时
)
```

### 安全检查机制

```python
# 危险命令检测
dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]

if any(d in command for d in dangerous):
    # any() 短路求值：一个匹配就返回 True
    return "Error: Dangerous command blocked"

# 示例
"rm -rf /home/user"  # 包含 "rm -rf /" → 被阻止 ❌
"sudo apt install"   # 包含 "sudo" → 被阻止 ❌
"ls -la"             # 安全 ✅
```

### 5.3 Read File 实现

```python
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
```

### 行限制处理

```python
# 大文件处理
text = "line1\nline2\n...line1000\n"
lines = text.splitlines()  # ['line1', 'line2', ..., 'line1000']

# 限制为前 50 行
limit = 50
if limit < len(lines):  # 50 < 1000
    lines = lines[:50]  # 前 50 行
    lines.append(f"... (950 more lines)")  # 添加提示

# 结果：50 行 + 提示，共 51 行
```

### 5.4 Write File 实现

```python
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
```

### 自动创建目录

```python
# path = "src/utils/helpers.py"
fp = safe_path(path)
# → Path(/home/user/project/src/utils/helpers.py)

fp.parent.mkdir(parents=True, exist_ok=True)
#        ↑
#   src/utils (如果不存在会创建)
#
# parents=True: 递归创建所有父目录
# exist_ok=True: 目录已存在不报错
```

### 5.5 Edit File 实现

```python
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
```

### str.replace() 第三个参数

```python
text = "apple apple apple"

# 默认：替换所有
text.replace("apple", "orange")
# → "orange orange orange"

# 只替换第一个
text.replace("apple", "orange", 1)
# → "orange apple apple"
#         ↑
#      只改了第一个

# 只替换前两个
text.replace("apple", "orange", 2)
# → "orange orange apple"
```

### 5.6 工具分发器

```python
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
```

### 工具分发流程

```
模型调用：read_file(path="config.json", limit=100)
              ↓
execute_tool("read_file", {"path": "config.json", "limit": 100})
              ↓
run_read("config.json", 100)
              ↓
返回文件内容（字符串）
              ↓
模型收到工具结果
```

---

## 6. 代理循环

```python
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
```

### 代理循环流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      代理循环核心流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    while True:                                              │
│       │                                                     │
│       ├─► 调用 LLM API                                       │
│       │    (messages + tools)                               │
│       │                                                     │
│       ├─► 解析响应                                           │
│       │    ├─ 有 tool_calls? ──Yes──► 执行工具             │
│       │    │                      ↓                         │
│       │    │                   添加结果到 messages           │
│       │    │                      ↓                         │
│       │    │                   继续循环 (while True)         │
│       │    │                                                │
│       │    └─ No ──► 返回文本结果                          │
│       │                                                     │
└─────────────────────────────────────────────────────────────┘
```

### Messages 结构演变

```python
# 初始状态
messages = [
    {"role": "user", "content": "列出当前目录的文件"}
]

# 第一次循环后
messages = [
    {"role": "user", "content": "列出当前目录的文件"},
    {"role": "assistant", "content": "我来列出文件", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "xxx", "content": "file1.py\nfile2.py"}
]

# 第二次循环后（模型返回最终答案）
messages = [
    {"role": "user", "content": "列出当前目录的文件"},
    {"role": "assistant", "content": "我来列出文件", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "xxx", "content": "file1.py\nfile2.py"},
    {"role": "assistant", "content": "当前目录有 2 个文件：..."}
]
#                         ↑
#              没有 tool_calls，循环结束
```

### Temperature 参数

```
Temperature 控制输出的随机性

┌─────────────────────────────────────────────────────────────┐
│  0.0 ──●─────────────────────────────────────  2.0         │
│        ↑                                              ↑     │
│     完全确定                                        完全随机  │
│     每次相同结果                                    更有创造力 │
│                                                              │
│  本代码使用 0.7：                                           │
│  - 有一定随机性（更好的对话体验）                            │
│  - 但不会太发散（保持工具调用的准确性）                       │
└─────────────────────────────────────────────────────────────┘
```

### 响应消息结构

```python
msg = {
    "content": "我来帮你列出文件...",    # 文本回复
    "tool_calls": [                      # 工具调用
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "bash",
                "arguments": '{"command": "ls -la"}'  # JSON 字符串
            }
        }
    ]
}
```

### 工具调用解析

```python
# 从 JSON 字符串解析参数
func_args = json.loads(tool_call.function.arguments)
# '{"command": "ls -la"}' → {"command": "ls -la"}

# 访问参数
command = func_args["command"]  # "ls -la"
```

---

## 7. 主程序入口

```python
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
```

### REPL 模式

```
REPL = Read - Eval - Print Loop

┌─────────────────────────────────────────────────────────────┐
│                    REPL 循环流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  while True:                                                │
│       │                                                     │
│    1. Read: user_input = input("You: ")                     │
│       │                                                     │
│    2. Eval: agent_loop(history)                             │
│       │    → 调用模型 → 执行工具 → 更新 history              │
│       │                                                     │
│    3. Print: (在 agent_loop 中打印)                         │
│       │                                                     │
│    4. Loop: 继续下一轮                                      │
│       │                                                     │
└─────────────────────────────────────────────────────────────┘
```

### History 生命周期

```python
# 跨轮次共享的上下文
history = []

# 第一轮
history.append({"role": "user", "content": "创建文件 hello.txt"})
agent_loop(history)
# history 现在包含：
# [user, assistant, tool, assistant]

# 第二轮
history.append({"role": "user", "content": "修改内容为 Hello World"})
agent_loop(history)
# history 现在包含两轮对话
# 模型可以看到之前的所有交互！
```

### 退出条件

```python
try:
    user_input = input("You: ").strip()
except (EOFError, KeyboardInterrupt):
    break  # Ctrl+D 或 Ctrl+C

if not user_input or user_input.lower() in ("exit", "quit", "q"):
    break  # 输入 exit、quit、q 或空回车
```

---

## 8. 完整流程图

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                   v1_basic_agent_glm.py                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    启动阶段                          │   │
│  │  1. 修复 locale (macOS/Linux)                       │   │
│  │  2. 加载环境变量 (.env)                              │   │
│  │  3. 初始化 OpenAI 客户端                             │   │
│  │  4. 定义 4 个工具                                    │   │
│  │  5. 构建 System Prompt                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  主程序入口                          │   │
│  │                                                     │   │
│  │  while True:                                        │   │
│  │    1. 读取用户输入                                   │   │
│  │    2. 添加到 history                                │   │
│  │    3. 运行 agent_loop(history)                      │   │
│  │    4. 用户输入 exit/quit/q → 退出                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  agent_loop() 核心循环               │   │
│  │                                                     │   │
│  │   while True:                                       │   │
│  │       │                                             │   │
│  │       ├─► 调用 LLM API                              │   │
│  │       │    (messages + 4 tools)                     │   │
│  │       │                                             │   │
│  │       ├─► 解析响应                                  │   │
│  │       │    ├─ 有 tool_calls? ──Yes──► 执行工具     │   │
│  │       │    │                      ↓                │   │
│  │       │    │                   添加结果到 history   │   │
│  │       │    │                      ↓                │   │
│  │       │    │                   继续循环             │   │
│  │       │    │                                        │   │
│  │       │    └─ No ──► 返回文本结果                  │   │
│  │       │                                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 单次对话示例

```
用户输入: "创建一个名为 hello.txt 的文件，内容是 'Hello World'"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 添加用户消息到 history                              │
│  history = [                                                 │
│    {"role": "user", "content": "创建一个名为..."}            │
│  ]                                                            │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 第一次 LLM API 调用                                 │
│  POST /chat/completions                                      │
│  {                                                           │
│    "model": "glm-4.7",                                       │
│    "messages": [system, user],                               │
│    "tools": [bash, read, write, edit]                        │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: LLM 返回工具调用                                    │
│  {                                                           │
│    "content": "我来创建这个文件",                             │
│    "tool_calls": [{                                         │
│      "id": "call_123",                                      │
│      "function": {                                          │
│        "name": "write_file",                                │
│        "arguments": '{"path": "hello.txt", "content": "Hello World"}' │
│      }                                                       │
│    }]                                                        │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 执行 write_file 工具                                │
│  run_write("hello.txt", "Hello World")                      │
│  → 创建文件 hello.txt                                        │
│  → 返回: "Wrote 11 bytes to hello.txt"                      │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 添加工具结果到 history                              │
│  history.append({                                            │
│    "role": "tool",                                          │
│    "tool_call_id": "call_123",                              │
│    "content": "Wrote 11 bytes to hello.txt"                 │
│  })                                                          │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 第二次 LLM API 调用（带着工具结果）                 │
│  {                                                           │
│    "messages": [system, user, assistant, tool]              │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 7: LLM 返回最终回复                                    │
│  {                                                           │
│    "content": "已成功创建 hello.txt 文件，内容为 Hello World" │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
              ↓
        返回给用户
```

### 工具调用决策流程

```
用户: "查看 src/utils.py 的内容，然后在第 10 行添加一个注释"
              ↓
┌─────────────────────────────────────────────────────────────┐
│                    模型的决策过程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  模型分析任务：                                              │
│  1. "查看 src/utils.py 的内容" → 需要读取文件                │
│     → 调用 read_file(path="src/utils.py")                   │
│                                                             │
│  2. 获取文件内容后                                           │
│     → 找到第 10 行                                           │
│     → 在第 10 行后添加注释                                    │
│     → 调用 edit_file(                                       │
│         path="src/utils.py",                                │
│         old_text="原始的第10行内容",                         │
│         new_text="原始的第10行内容  # 新注释"               │
│       )                                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
              ↓
        自动执行两个工具调用
```

---

## 核心要点总结

### 1. 模型是决策者

```python
# 代码不决定做什么，模型决定
# 代码只提供能力和执行
while True:
    response = model(messages, tools)
    if no tools: return
    execute(results)
```

### 2. 四工具覆盖90%场景

```
bash      → 执行任何命令、探索文件系统
read_file → 理解现有代码
write_file → 创建新文件
edit_file  → 精确修改
```

### 3. 对话历史即内存

```python
# messages 累积所有交互
# 模型可以"记住"之前的对话
messages = [
    user_msg_1,
    assistant_msg_1,
    tool_result_1,
    assistant_msg_1_final,
    user_msg_2,  # 新一轮，但可以看到之前所有内容
    ...
]
```

### 4. 约束使能复杂任务

```python
# 系统提示词中的规则不是限制，而是引导
"""
规则：
- 优先使用工具而非文字
- 不要虚构文件路径
- 做最小化修改
"""
```

---

[← 返回 README](../README_zh.md)
