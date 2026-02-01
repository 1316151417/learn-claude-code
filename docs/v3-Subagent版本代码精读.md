# v3_subagent.py 代码精读

**子代理机制完整解析**

---

## 目录

1. [核心哲学：分而治之](#1-核心哲学分而治之)
2. [Agent Type Registry](#2-agent-type-registry)
3. [Task 工具](#3-task-工具)
4. [子代理执行](#4-子代理执行)
5. [工具过滤](#5-工具过滤)
6. [进程隔离](#6-进程隔离)
7. [完整流程图](#7-完整流程图)

---

## 1. 核心哲学：分而治之

### v2 的问题：上下文污染

```
┌─────────────────────────────────────────────────────────────┐
│                  单代理的上下文污染问题                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "探索代码库然后重构认证"                                │
│                                                             │
│  单代理的 history:                                           │
│    [探索阶段]                                                │
│    cat file1.py → 500 行                                    │
│    cat file2.py → 300 行                                    │
│    ... 15 个文件 ...                                        │
│    [现在进入重构阶段]                                         │
│    "等等，file1 里面有什么来着？"                             │
│                                                             │
│  问题：                                                     │
│  - 探索细节填满上下文                                        │
│  - 真正工作时空间所剩无几                                    │
│  - 模型需要"记住"太多内容                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### v3 的解决方案：上下文隔离

```
┌─────────────────────────────────────────────────────────────┐
│                 子代理的上下文隔离                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "探索代码库然后重构认证"                                │
│                                                             │
│  主代理的 history:                                          │
│    [Task: 探索代码库]                                        │
│      → 子代理探索 20 个文件（在自己的上下文中）                │
│      → 仅返回: "认证在 src/auth/, 数据库在 src/models/"      │
│    [现在开始重构，上下文干净]                                 │
│                                                             │
│  优势：                                                     │
│  - 每个子代理有独立的消息历史                                 │
│  - 过滤的工具（explore 不能写）                               │
│  - 专门的系统提示词                                           │
│  - 只返回最终摘要给父代理                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 关键洞察

```
┌─────────────────────────────────────────────────────────────┐
│            进程隔离 = 上下文隔离                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  通过生成子任务，我们获得：                                    │
│  - 主代理的干净上下文                                         │
│  - 可能的并行探索                                             │
│  - 自然的任务分解                                             │
│  - 相同的代理循环，不同的上下文                                │
│                                                             │
│  这类似于：                                                  │
│  - 函数调用（独立的局部变量）                                  │
│  - 进程 fork（独立的内存空间）                                │
│  - Docker 容器（隔离的环境）                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Type Registry

### 完整注册表

```python
AGENT_TYPES = {
    # Explore: 只读代理用于搜索和分析
    # 不能修改文件 - 可安全进行广泛探索
    "explore": {
        "description": "Read-only agent for exploring code, finding files, searching",
        "tools": ["bash", "read_file"],  # 没有写权限
        "prompt": "You are an exploration agent. Search and analyze, but never modify files. Return a concise summary.",
    },

    # Code: 完全代理用于实现
    # 有所有工具 - 用于实际编码工作
    "code": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",  # 所有工具
        "prompt": "You are a coding agent. Implement the requested changes efficiently.",
    },

    # Plan: 分析代理用于设计工作
    # 只读，专注于生成计划和策略
    "plan": {
        "description": "Planning agent for designing implementation strategies",
        "tools": ["bash", "read_file"],  # 只读
        "prompt": "You are a planning agent. Analyze the codebase and output a numbered implementation plan. Do NOT make changes.",
    },
}
```

### 三种代理类型对比

| 特性 | explore | code | plan |
|------|---------|------|------|
| **用途** | 探索代码 | 实现功能 | 设计策略 |
| **工具** | bash, read | 全部 | bash, read |
| **可写？** | ❌ | ✅ | ❌ |
| **返回** | 简洁摘要 | 完成确认 | 编号计划 |
| **典型场景** | 查找文件、理解架构 | 写代码、修bug | 设计迁移方案 |

### 典型工作流

```
┌─────────────────────────────────────────────────────────────┐
│              三种代理类型的典型工作流                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "重构认证以使用 JWT"                                   │
│                                                             │
│  主代理协调：                                                 │
│                                                             │
│  1. Task(explore): "查找所有与认证相关的文件"                │
│     └─ 子代理读取 10 个文件                                   │
│     └─ 返回: "认证在 src/auth/login.py..."                  │
│                                                             │
│  2. Task(plan): "设计 JWT 迁移策略"                         │
│     └─ 子代理分析结构                                         │
│     └─ 返回: "1. 添加 jwt 库 2. 创建 utils..."              │
│                                                             │
│  3. Task(code): "实现 JWT 令牌"                             │
│     └─ 子代理编写代码                                         │
│     └─ 返回: "已创建 jwt_utils.py，更新了 login.py"         │
│                                                             │
│  4. 主代理总结更改给用户                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Description 生成

```python
def get_agent_descriptions() -> str:
    """为系统提示词生成代理类型描述。"""
    return "\n".join(
        f"- {name}: {cfg['description']}"
        for name, cfg in AGENT_TYPES.items()
    )

# 输出
"""
- explore: Read-only agent for exploring code, finding files, searching
- code: Full agent for implementing features and fixing bugs
- plan: Planning agent for designing implementation strategies
"""
```

---

## 3. Task 工具

### 工具定义

```python
TASK_TOOL = {
    "name": "Task",
    "description": f"""Spawn a subagent for a focused subtask.

Subagents run in ISOLATED context - they don't see parent's history.
Use this to keep the main conversation clean.

Agent types:
{get_agent_descriptions()}

Example uses:
- Task(explore): "Find all files using the auth module"
- Task(plan): "Design a migration strategy for the database"
- Task(code): "Implement the user registration form"
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Short task name (3-5 words) for progress display"
            },
            "prompt": {
                "type": "string",
                "description": "Detailed instructions for the subagent"
            },
            "agent_type": {
                "type": "string",
                "enum": list(AGENT_TYPES.keys()),
                "description": "Type of agent to spawn"
            },
        },
        "required": ["description", "prompt", "agent_type"],
    },
}
```

### 参数详解

| 参数 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| `description` | string | ✅ | 短任务名（3-5词）用于进度显示 | "find auth files" |
| `prompt` | string | ✅ | 子代理的详细指令 | "Find all files that import or use the authentication module" |
| `agent_type` | string | ✅ | 要生成的代理类型 | "explore" |

### Description vs Prompt

```python
# description: 短小精悍，用于显示
"find auth files"

# prompt: 详细明确，用于执行
"Find all files in the codebase that import or use the authentication module. \
Search in src/ for files containing 'auth' imports. \
List all files with their purposes."
```

### 调用示例

```python
# 模型调用
Task(
    description="find auth files",
    prompt="探索 src/ 目录，找出所有与认证相关的文件",
    agent_type="explore"
)
```

---

## 4. 子代理执行

### run_task 函数

```python
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
      [explore] find auth files ... 5 tools, 3.2s

    这提供了可见性，而不会污染主对话。
    """
    if agent_type not in AGENT_TYPES:
        return f"Error: Unknown agent type '{agent_type}'"

    config = AGENT_TYPES[agent_type]

    # 代理特定的系统提示词
    sub_system = f"""You are a {agent_type} subagent at {WORKDIR}.

{config["prompt"]}

Complete the task and return a clear, concise summary."""

    # 为此代理类型过滤的工具
    sub_tools = get_tools_for_agent(agent_type)

    # 隔离的消息历史 - 这是关键！
    # 子代理重新开始，看不到父对话
    sub_messages = [{"role": "user", "content": prompt}]

    # 进度追踪
    print(f"  [{agent_type}] {description}")
    start = time.time()
    tool_count = 0

    # 运行相同的代理循环（静默 - 不打印到主聊天）
    while True:
        response = client.messages.create(
            model=MODEL,
            system=sub_system,
            messages=sub_messages,
            tools=sub_tools,
            max_tokens=8000,
        )

        if response.stop_reason != "tool_use":
            break

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        results = []

        for tc in tool_calls:
            tool_count += 1
            output = execute_tool(tc.name, tc.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": output
            })

            # 更新进度行（就地）
            elapsed = time.time() - start
            sys.stdout.write(
                f"\r  [{agent_type}] {description} ... {tool_count} tools, {elapsed:.1f}s"
            )
            sys.stdout.flush()

        sub_messages.append({"role": "assistant", "content": response.content})
        sub_messages.append({"role": "user", "content": results})

    # 最终进度更新
    elapsed = time.time() - start
    sys.stdout.write(
        f"\r  [{agent_type}] {description} - done ({tool_count} tools, {elapsed:.1f}s)\n"
    )

    # 提取并只返回最终文本
    # 这是父代理看到的 - 干净的摘要
    for block in response.content:
        if hasattr(block, "text"):
            return block.text

    return "(subagent returned no text)"
```

### 隔离的消息历史

```python
# 父代理的 messages (主对话)
messages = [
    {"role": "user", "content": "重构认证模块"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "xxx", "content": "..."}
]
# 可能很长！

# 子代理的 sub_messages (全新开始)
sub_messages = [
    {"role": "user", "content": "探索代码库找出认证文件"}
]
# 干净！
```

### 进度显示机制

```python
# 初始显示
print(f"  [{agent_type}] {description}")
# [explore] find auth files

# 实时更新（同一行）
sys.stdout.write(f"\r  [{agent_type}] {description} ... {tool_count} tools, {elapsed:.1f}s")
# \r = 回到行首，覆盖之前的输出

# 最终显示
sys.stdout.write(f"\r  [{agent_type}] {description} - done ({tool_count} tools, {elapsed:.1f}s)\n")
# [explore] find auth files - done (5 tools, 3.2s)
```

### 完整执行流程

```
┌─────────────────────────────────────────────────────────────┐
│           run_task("find auth files", "explore")            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 验证 agent_type                                         │
│     → "explore" 在 AGENT_TYPES 中 ✅                        │
│                                                             │
│  2. 构建子代理系统提示词                                      │
│     → "You are a explore subagent at /path/..."            │
│     → "Search and analyze, but never modify files..."      │
│                                                             │
│  3. 过滤工具                                                 │
│     → ["bash", "read_file"] (只有这两个！)                   │
│                                                             │
│  4. 创建隔离的 messages                                      │
│     → [{"role": "user", "content": "探索代码库..."}]        │
│                                                             │
│  5. 运行子循环（静默）                                        │
│     → 不打印到主聊天                                         │
│     → 只更新进度行                                           │
│                                                             │
│  6. 返回最终摘要                                              │
│     → "认证在 src/auth/，包含 login.py 和 utils.py"         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 工具过滤

### get_tools_for_agent 函数

```python
def get_tools_for_agent(agent_type: str) -> list:
    """
    根据代理类型过滤工具。

    每个代理类型都有一个允许的工具白名单。
    '*' 表示所有工具（但子代理不获取 Task 工具以防止无限递归）。
    """
    allowed = AGENT_TYPES.get(agent_type, {}).get("tools", "*")

    if allowed == "*":
        return BASE_TOOLS  # 所有基础工具，但不包括 Task（演示中没有递归）

    return [t for t in BASE_TOOLS if t["name"] in allowed]
```

### 工具过滤示例

```python
# explore 代理
get_tools_for_agent("explore")
# → [bash, read_file]
#    没有 write_file, edit_file, TodoWrite

# code 代理
get_tools_for_agent("code")
# → [bash, read_file, write_file, edit_file, TodoWrite]
#    所有基础工具

# plan 代理
get_tools_for_agent("plan")
# → [bash, read_file]
#    只读，像 explore
```

### 为什么子代理没有 Task 工具？

```python
# 如果子代理也有 Task 工具
Main Agent
  └─ Task(explore): "find files"
       └─ Subagent
            └─ Task(explore): "find more files"  # 递归！
                 └─ Sub-subagent
                      └─ Task(explore): "find even more"
                           └─ 无限递归...

# 在生产系统中，可以：
# 1. 限制递归深度
# 2. 只允许特定代理类型使用 Task
# 3. 使用预算/配额系统
```

---

## 6. 进程隔离

### 上下文隔离对比

```
┌─────────────────────────────────────────────────────────────┐
│                主代理 vs 子代理的上下文                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  主代理 messages (共享上下文):                               │
│  ┌────────────────────────────────────────────┐             │
│  │ User: "重构认证"                            │             │
│  │ Assistant: "我先探索代码库..."              │             │
│  │ Tool: Task(explore, "find auth files")     │             │
│  │ Tool Result: "认证在 src/auth/..."         │ ← 子代理摘要  │
│  │ Assistant: "现在我来设计迁移方案..."        │             │
│  │ Tool: Task(plan, "design migration")       │             │
│  │ Tool Result: "1. 添加 jwt 2. 创建 utils..."│ ← 子代理摘要  │
│  │ Assistant: "开始实现..."                   │             │
│  └────────────────────────────────────────────┘             │
│            ↑                                                │
│       干净的上下文                                          │
│       只包含摘要，没有中间步骤                                │
│                                                             │
│  子代理 messages (隔离上下文):                               │
│  ┌────────────────────────────────────────────┐             │
│  │ User: "探索代码库找出认证文件"               │             │
│  │ Assistant: "我来搜索..."                   │             │
│  │ Tool: bash find . -name "*.py"             │             │
│  │ Tool Result: "file1.py, file2.py..."       │             │
│  │ Assistant: "读取 file1.py"                  │             │
│  │ Tool: read_file file1.py                   │             │
│  │ Tool Result: "500 行内容..."               │             │
│  │ ... 15 轮 ...                              │             │
│  │ Assistant: "认证在 src/auth/，包含..."      │             │
│  └────────────────────────────────────────────┘             │
│            ↑                                                │
│       不会被父代理看到                                       │
│       只有最终摘要返回                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 隔离的好处

```
┌─────────────────────────────────────────────────────────────┐
│                    进程隔离的好处                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 干净的上下文                                             │
│     主代理只看到摘要，不看细节                                 │
│     → 更少的 token 使用                                      │
│     → 更好的决策质量                                         │
│                                                             │
│  2. 故障隔离                                                │
│     子代理错误不影响主代理                                    │
│     → 可以单独重试子任务                                     │
│                                                             │
│  3. 并行潜力                                                │
│     子代理可以并行运行                                       │
│     → 更快的完成时间                                         │
│                                                             │
│  4. 自然的任务分解                                           │
│     复杂任务分解为子任务                                     │
│     → 更容易理解和调试                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 完整流程图

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    v3_subagent.py                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    启动阶段                          │   │
│  │  1. 定义 AGENT_TYPES (explore, code, plan)          │   │
│  │  2. 创建 TASK_TOOL                                   │   │
│  │  3. 继承 TodoManager (来自 v2)                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  主程序入口                          │   │
│  │  while True:                                        │   │
│    1. 读取用户输入                                       │   │
│    2. 运行 agent_loop(history)                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              agent_loop() 主代理循环                 │   │
│  │                                                     │   │
│  │   while True:                                       │   │
│  │       ├─► 调用 LLM API                              │   │
│  │       │    (messages + ALL_TOOLS including Task)   │   │
│  │       │                                             │   │
│  │       ├─► 如果是 Task 工具                          │   │
│  │       │    └─► run_task()                          │   │
│  │       │         ├─ 创建隔离的 sub_messages          │   │
│  │       │         ├─ 过滤工具                         │   │
│  │       │         ├─ 运行子循环 (静默)                │   │
│  │       │         └─ 返回摘要                        │   │
│  │       │                                             │   │
│  │       └─► 继续循环或返回                            │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 子代理调用完整示例

```
用户: "重构认证以使用 JWT"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  主代理决策：需要探索代码库                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  > Task(explore): "查找所有与认证相关的文件"                  │
│    prompt: "在 src/ 中搜索所有导入或使用认证模块的文件"       │
│                                                             │
│  [explore] find auth files ... 3 tools, 1.5s                │
│  [explore] find auth files - done (5 tools, 2.3s)           │
│                                                             │
│  Tool Result: "认证相关文件:                                  │
│    - src/auth/login.py (登录逻辑)                            │
│    - src/auth/utils.py (工具函数)                            │
│    - src/middleware.py (认证中间件)"                          │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  主代理决策：需要设计迁移方案                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  > Task(plan): "设计 JWT 迁移策略"                           │
│    prompt: "分析当前认证实现，设计 JWT 迁移的详细计划"         │
│                                                             │
│  [plan] design migration ... 4 tools, 1.8s                  │
│  [plan] design migration - done (6 tools, 3.1s)             │
│                                                             │
│  Tool Result: "JWT 迁移计划:                                  │
│    1. 安装 PyJWT 库                                          │
│    2. 创建 src/auth/jwt_utils.py (token 生成/验证)          │
│    3. 修改 src/auth/login.py 使用 JWT                       │
│    4. 更新 src/middleware.py 验证 JWT                       │
│    5. 添加测试"                                              │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  主代理决策：开始实现                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  > TodoWrite: [ ] 安装 PyJWT, [ ] 创建 jwt_utils, ...     │
│  > TodoWrite: [>] 安装 PyJWT <- 正在安装                     │
│  > bash: pip install pyjwt                                  │
│  > TodoWrite: [x] 安装 PyJWT, [>] 创建 jwt_utils...         │
│  > Task(code): "实现 JWT 工具函数"                           │
│    prompt: "创建 jwt_utils.py 包含 generate_token 和        │
│             verify_token 函数"                              │
│                                                             │
│  [code] implement jwt utils ... 3 tools, 2.1s               │
│  [code] implement jwt utils - done (3 tools, 2.1s)          │
│                                                             │
│  Tool Result: "已创建 jwt_utils.py:                          │
│    - generate_token(user_id) 返回 JWT 字符串                 │
│    - verify_token(token) 验证并返回 user_id"                 │
└─────────────────────────────────────────────────────────────┘
              ↓
        主代理继续实现其他步骤...
```

### 子代理内部循环

```
┌─────────────────────────────────────────────────────────────┐
│            子代理内部循环 (与主代理相同的模式)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  while True:                                                │
│      │                                                     │
│      ├─► 调用 LLM API                                       │
│      │    (sub_messages + sub_tools)                       │
│      │    # 注意：使用隔离的 messages 和过滤的工具           │
│      │                                                     │
│      ├─► 如果没有工具调用                                    │
│      │    └─► break (返回最终文本)                          │
│      │                                                     │
│      ├─► 执行工具                                           │
│      │    output = execute_tool(tc.name, tc.input)         │
│      │    # 注意：使用主代理的 execute_tool (共享实现)       │
│      │                                                     │
│      ├─► 更新进度显示                                        │
│      │    sys.stdout.write(f"\r ... {tool_count} tools")   │
│      │    # 注意：只更新进度行，不打印完整输出               │
│      │                                                     │
│      └─► 继续循环                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心要点总结

### 1. 上下文隔离的价值

```python
# 主代理的 messages (干净)
[User, Assistant, Task Result (摘要), Assistant, ...]
#                              ↑
#                          只有摘要

# 子代理的 messages (详细但隔离)
[User, Assistant, Tool, Tool Result, Assistant, ...]
#                           ↑
#                       所有细节
```

### 2. 代理类型的分工

```
explore: 只读，用于搜索和分析
plan: 只读，用于设计和规划
code: 读写，用于实现和修改
```

### 3. 相同的循环，不同的上下文

```python
# 主代理和子代理使用相同的循环模式
while True:
    response = model(messages, tools)
    if no tools: return
    execute(results)

# 区别在于：
# - messages 内容不同
# - tools 过滤不同
# - system prompt 不同
```

### 4. 进度显示 vs 详细输出

```python
# 主代理：详细输出
> read_file: src/auth/login.py
  #!/usr/bin/env python
  """Login module"""
  ...

# 子代理：进度显示
[explore] find auth files ... 3 tools, 1.5s
#                         ↑
#                    只显示摘要
```

---

[← 返回 README](../README_zh.md)
