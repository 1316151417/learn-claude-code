# v2_todo_agent.py 代码精读

**带任务规划的代理完整解析**

---

## 目录

1. [核心哲学：让计划可见](#1-核心哲学让计划可见)
2. [TodoManager 类](#2-todomanager-类)
3. [系统提示词演进](#3-系统提示词演进)
4. [System Reminders](#4-system-reminders)
5. [TodoWrite 工具](#5-todowrite-工具)
6. [NAG_REMINDER 机制](#6-nag_reminder-机制)
7. [代理循环变化](#7-代理循环变化)
8. [完整流程图](#8-完整流程图)

---

## 1. 核心哲学：让计划可见

### v1 的问题：上下文淡化

```
┌─────────────────────────────────────────────────────────────┐
│                    v1 的隐式规划问题                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "重构认证模块，添加测试，更新文档"                       │
│                                                             │
│  v1 模型 (内心独白):                                         │
│    "我先做 A，然后 B，然后 C"                                │
│                             ↑                               │
│                        不可见！                               │
│                                                             │
│  10 轮工具调用后：                                           │
│    "等等，我做到哪了？"                                      │
│    "我是不是漏了什么？"                                      │
│                                                             │
│  问题：                                                     │
│  - 计划只存在于模型的"脑海"中                                │
│  - 模型可能忘记已完成的步骤                                  │
│  - 用户看不到进度                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### v2 的解决方案：显式规划

```
┌─────────────────────────────────────────────────────────────┐
│                    v2 的显式规划                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "重构认证模块，添加测试，更新文档"                       │
│                                                             │
│  v2 模型:                                                   │
│    TodoWrite:                                               │
│      [ ] 重构认证模块                                        │
│      [ ] 添加单元测试                                        │
│      [ ] 更新文档                                            │
│                                                             │
│  5 轮后：                                                   │
│    [x] 重构认证模块  ← 完成！                                │
│      [>] 添加单元测试 <- 正在做这个                          │
│    [ ] 更新文档                                              │
│                                                             │
│  优势：                                                     │
│  - 计划对模型和用户都可见                                    │
│  - 进度一目了然                                              │
│  - 模型可以专注于当前任务                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心洞察：约束使能

```
┌─────────────────────────────────────────────────────────────┐
│              "Structure constrains AND enables"             │
│                  结构约束并使能                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Todo 约束：                                                 │
│  - Max 20 items → 防止无限列表                              │
│  - One in_progress → 强制聚焦                               │
│  - Required fields → 确保结构化输出                          │
│                                                             │
│  这些约束不是限制，而是脚手架：                               │
│  ┌─────────────────────────────────────┐                   │
│  │   约束 → 使能                          │                   │
│  │   ─────→ ────                        │                   │
│  │   max_items → 可见的计划              │                   │
│  │   one_active → 跟踪的进度             │                   │
│  │   required_fields → 复杂任务完成       │                   │
│  └─────────────────────────────────────┘                   │
│                                                             │
│  类比：                                                     │
│  - max_tokens 约束 → 使能可管理的响应                         │
│  - Tool schemas 约束 → 使能结构化调用                         │
│  - Todos 约束 → 使能复杂任务完成                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. TodoManager 类

### 完整类定义

```python
class TodoManager:
    """
    管理带有强制约束的结构化任务列表。

    关键设计决策：
    --------------------
    1. Max 20 items: 防止模型创建无限列表
    2. One in_progress: 强制聚焦 - 一次只能做一件事
    3. Required fields: 每项需要 content, status, 和 activeForm

    activeForm 字段需要解释：
    - 它是正在发生的事情的现在时态形式
    - 当 status 为 "in_progress" 时显示
    - 例如: content="Add tests", activeForm="Adding unit tests..."

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
                raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if not active_form:
                raise ValueError(f"Item {i}: activeForm required")

            if status == "in_progress":
                in_progress_count += 1

            validated.append({
                "content": content,
                "status": status,
                "activeForm": active_form
            })

        # 强制约束
        if len(validated) > 20:
            raise ValueError("Max 20 todos allowed")
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")

        self.items = validated
        return self.render()

    def render(self) -> str:
        """
        将 todo 列表渲染为人类可读的文本。

        格式:
            [x] Completed task
            [>] In progress task <- Doing something...
            [ ] Pending task

            (2/3 completed)

        这个渲染后的文本是模型看到的工具结果。
        然后它可以根据其当前状态更新列表。
        """
        if not self.items:
            return "No todos."

        lines = []
        for item in self.items:
            if item["status"] == "completed":
                lines.append(f"[x] {item['content']}")
            elif item["status"] == "in_progress":
                lines.append(f"[>] {item['content']} <- {item['activeForm']}")
            else:
                lines.append(f"[ ] {item['content']}")

        completed = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({completed}/{len(self.items)} completed)")

        return "\n".join(lines)
```

### TodoItem 数据结构

```python
todo_item = {
    "content": "添加单元测试",           # 任务描述（必填）
    "status": "in_progress",            # pending|in_progress|completed
    "activeForm": "正在添加单元测试"     # 现在时态动作（必填）
}
```

### 渲染效果对比

```python
# 输入数据
todos = [
    {"content": "重构认证模块", "status": "completed", "activeForm": "已重构认证模块"},
    {"content": "添加单元测试", "status": "in_progress", "activeForm": "正在添加单元测试"},
    {"content": "更新文档", "status": "pending", "activeForm": "准备更新文档"}
]

# render() 输出
[x] 重构认证模块
[>] 添加单元测试 <- 正在添加单元测试
[ ] 更新文档

(1/3 completed)
```

### 验证流程

```
┌─────────────────────────────────────────────────────────────┐
│              TodoManager.update() 验证流程                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  输入: 模型发送的新 todo 列表                                 │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 1: 遍历每个 item                            │        │
│  │                                                  │        │
│  │ for i, item in enumerate(items):                │        │
│  │     content = item["content"].strip()           │        │
│  │     status = item["status"].lower()             │        │
│  │     active = item["activeForm"].strip()         │        │
│  └─────────────────────────────────────────────────┘        │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 2: 验证每个字段                             │        │
│  │                                                  │        │
│  │ if not content: → raise "content required"      │        │
│  │ if status not in ENUM: → raise "invalid status" │        │
│  │ if not active: → raise "activeForm required"    │        │
│  │ if status == "in_progress": count += 1          │        │
│  └─────────────────────────────────────────────────┘        │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 3: 强制全局约束                             │        │
│  │                                                  │        │
│  │ if len(items) > 20: → raise "Max 20 allowed"    │        │
│  │ if in_progress > 1: → raise "Only one active"   │        │
│  └─────────────────────────────────────────────────┘        │
│           ↓                                                  │
│  输出: 渲染后的 todo 列表（字符串）                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### activeForm 的作用

```python
# 没有 activeForm (不清晰)
[ ] Add tests
[ ] Update docs

# 有 activeForm (实时可见)
[ ] Add tests
[ ] Update docs

# 当一个进行中时
[ ] Add tests
[>] Update docs <- Writing API documentation...
#                     ↑
#              用户知道模型正在做什么
```

---

## 3. 系统提示词演进

### v1 vs v2 System Prompt

```python
# v1 System Prompt
SYSTEM_v1 = f"""你是位于 {WORKDIR} 的编码代理。

循环：简短思考 -> 使用工具 -> 报告结果。

规则：
- 优先使用工具而非文字。行动，而不只是解释。
- 不要虚构文件路径。如果不确定，先使用 bash ls/find。
- 做最小化修改。不要过度设计。
- 完成后，总结更改内容。"""

# v2 System Prompt
SYSTEM_v2 = f"""You are a coding agent at {WORKDIR}.

Loop: plan -> act with tools -> update todos -> report.

Rules:
- Use TodoWrite to track multi-step tasks
- Mark tasks in_progress before starting, completed when done
- Prefer tools over prose. Act, don't just explain.
- After finishing, summarize what changed."""
```

### 关键变化

| 方面 | v1 | v2 |
|------|----|----|
| 循环描述 | 简短思考 → 使用工具 → 报告 | plan → act → update todos → report |
| 核心规则 | 优先使用工具 | **使用 TodoWrite 跟踪多步任务** |
| 状态管理 | 无明确状态 | **标记任务 in_progress/completed** |

### 循环语义变化

```
┌─────────────────────────────────────────────────────────────┐
│                   循环语义的演进                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  v1 循环：                                                  │
│    简短思考 → 使用工具 → 报告结果                             │
│                            ↑                                │
│                       没有中间状态                            │
│                                                             │
│  v2 循环：                                                  │
│    plan → act → update todos → report                       │
│      ↑       ↑          ↑                                   │
│    规划    执行      更新状态                                 │
│                             │                                │
│                             └─ todos 变成                   │
│                                可见的中间状态                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. System Reminders

### Reminders 的两种类型

```python
# =============================================================================
# System Reminders - 软提示鼓励 todo 使用
# =============================================================================

# 在对话开始时显示
INITIAL_REMINDER = "<reminder>Use TodoWrite for multi-step tasks.</reminder>"

# 如果模型有一段时间没有更新 todos，则显示
NAG_REMINDER = "<reminder>10+ turns without todo update. Please update todos.</reminder>"
```

### INITIAL_REMINDER 的使用

```python
def main():
    history = []
    first_message = True

    while True:
        user_input = input("You: ").strip()

        # 构建用户消息内容
        content = []

        if first_message:
            # 在对话开始时温柔提醒
            content.append({"type": "text", "text": INITIAL_REMINDER})
            first_message = False

        content.append({"type": "text", "text": user_input})
        history.append({"role": "user", "content": content})
```

### NAG_REMINDER 的注入时机

```python
# Track how many rounds since last todo update
rounds_without_todo = 0

def agent_loop(messages: list) -> list:
    global rounds_without_todo

    while True:
        response = client.messages.create(...)

        results = []
        used_todo = False

        for tc in tool_calls:
            output = execute_tool(tc.name, tc.input)
            results.append({"type": "tool_result", ...})

            # Track todo usage
            if tc.name == "TodoWrite":
                used_todo = True

        # 更新计数器：如果使用了 todo 则重置，否则递增
        if used_todo:
            rounds_without_todo = 0
        else:
            rounds_without_todo += 1

        # 如果模型超过 10 轮没有使用 todos，注入 NAG_REMINDER
        # 这发生在 agent_loop 内部，所以模型在任务执行期间看到它
        if rounds_without_todo > 10:
            results.insert(0, {"type": "text", "text": NAG_REMINDER})

        messages.append({"role": "user", "content": results})
```

### Reminder 注入流程

```
┌─────────────────────────────────────────────────────────────┐
│              Reminder 注入的两种时机                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. INITIAL_REMINDER (第一轮开始)                            │
│     ───────────────────────────────                         │
│     User: "重构认证模块"                                      │
│     ↓ 添加到消息                                              │
│     Messages: [                                             │
│       {"type": "text", "text": "<reminder>Use TodoWrite...</>"}, │
│       {"type": "text", "text": "重构认证模块"}                │
│     ]                                                        │
│                                                             │
│  2. NAG_REMINDER (10+ 轮没有 todo 更新)                       │
│     ────────────────────────────────────                     │
│     rounds_without_todo > 10                                 │
│     ↓                                                        │
│     Tool results: [                                         │
│       {"type": "text", "text": "<reminder>10+ turns..."},    │
│       {"type": "tool_result", "tool_call_id": "xxx", ...}    │
│     ]                                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. TodoWrite 工具

### 工具定义

```python
{
    "name": "TodoWrite",
    "description": "Update the task list. Use to plan and track progress.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Complete list of tasks (replaces existing)",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task description"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Task status"
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "Present tense action, e.g. 'Reading files'"
                        },
                    },
                    "required": ["content", "status", "activeForm"],
                }
            }
        },
        "required": ["items"],
    },
}
```

### "Replaces existing" 语义

```python
# 重要：TodoWrite 总是替换整个列表，而不是增量更新

# 初始状态
todos = [
    {"content": "Task A", "status": "pending", "activeForm": "..."},
    {"content": "Task B", "status": "pending", "activeForm": "..."}
]

# 模型想要更新 Task A 为 completed
# 它必须发送完整的新列表
TodoWrite(items=[
    {"content": "Task A", "status": "completed", "activeForm": "已完成 Task A"},
    {"content": "Task B", "status": "in_progress", "activeForm": "正在执行 Task B"}
])
#                     ↑
#          这是完整列表，不是差异
```

### 为什么是完整列表而不是差异？

```python
# 差异方式的问题
TodoWrite_update(id=1, status="completed")
# 1. 需要维护 ID
# 2. 模型需要记住 ID
# 3. 容易出现 ID 不匹配

# 完整列表方式的优势
TodoWrite(items=[...])
# 1. 无需 ID，状态自包含
# 2. 模型可以看到完整状态
# 3. 不容易出现不一致
```

### run_todo 实现

```python
def run_todo(items: list) -> str:
    """
    更新 todo 列表。

    模型发送一个完整的新列表（不是差异）。
    我们验证它并返回渲染后的视图。
    """
    try:
        return TODO.update(items)
    except Exception as e:
        return f"Error: {e}"
```

---

## 6. NAG_REMINDER 机制

### 软约束 vs 硬约束

```python
# 软约束（v2 使用）
if rounds_without_todo > 10:
    results.insert(0, {"type": "text", "text": NAG_REMINDER})
# 模型可以选择忽略

# 硬约束（不使用）
if rounds_without_todo > 10:
    raise Exception("必须使用 TodoWrite")
# 强制模型使用
```

### 软约束的优势

```
┌─────────────────────────────────────────────────────────────┐
│                    软约束的优势                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 允许例外：                                               │
│     - 简单任务不需要 todos                                    │
│     - 模型可以自行决定                                        │
│                                                             │
│  2. 不打断流程：                                             │
│     - 提醒只是消息的一部分                                     │
│     - 模型可以在同一个响应中处理提醒和任务                       │
│                                                             │
│  3. 更好的用户体验：                                          │
│     - 不会因为约束而失败                                      │
│     - 提供引导而非强制                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### rounds_without_todo 计数器

```python
global rounds_without_todo

# 在 agent_loop 中
if used_todo:
    rounds_without_todo = 0  # 重置
else:
    rounds_without_todo += 1  # 递增

# 状态演变
Round 1: used_todo=False → rounds_without_todo=1
Round 2: used_todo=False → rounds_without_todo=2
...
Round 10: used_todo=False → rounds_without_todo=10
Round 11: used_todo=False → rounds_without_todo=11
                                 ↓
                          注入 NAG_REMINDER
Round 12: used_todo=True → rounds_without_todo=0  # 重置！
```

---

## 7. 代理循环变化

### v1 vs v2 代理循环

```python
# v1 代理循环
def agent_loop(messages: list) -> list:
    while True:
        response = client.chat.completions.create(...)
        # ... 处理响应
        if not msg.tool_calls:
            return messages
        # ... 执行工具
        # ... 添加结果
        # 继续循环

# v2 代理循环
def agent_loop(messages: list) -> list:
    global rounds_without_todo

    while True:
        response = client.messages.create(...)
        # ... 处理响应
        if not msg.tool_calls:
            return messages

        results = []
        used_todo = False  # 新增：追踪 todo 使用

        for tc in msg.tool_calls:
            output = execute_tool(tc.name, tc.input)
            results.append({...})

            if tc.name == "TodoWrite":  # 新增：检测 todo 使用
                used_todo = True

        # 新增：更新计数器
        if used_todo:
            rounds_without_todo = 0
        else:
            rounds_without_todo += 1

        # 新增：注入提醒
        if rounds_without_todo > 10:
            results.insert(0, {"type": "text", "text": NAG_REMINDER})

        messages.append({"role": "user", "content": results})
```

### 关键差异

| 特性 | v1 | v2 |
|------|----|----|
| Todo 追踪 | 无 | `used_todo` 标志 |
| 计数器 | 无 | `rounds_without_todo` |
| 提醒注入 | 无 | `NAG_REMINDER` 条件注入 |
| 结果构建 | 直接添加 | 可能插入提醒 |

---

## 8. 完整流程图

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    v2_todo_agent.py                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    启动阶段                          │   │
│  │  1. 初始化 TodoManager                              │   │
│  │  2. 定义 INITIAL_REMINDER, NAG_REMINDER             │   │
│  │  3. 定义 5 个工具 (v1的4个 + TodoWrite)              │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  主程序入口                          │   │
│  │                                                     │   │
│  │  first_message = True                               │   │
│  │  rounds_without_todo = 0                            │   │
│  │                                                     │   │
│  │  while True:                                        │   │
│  │    1. 读取用户输入                                   │   │
│  │    2. 如果 first_message → 注入 INITIAL_REMINDER    │   │
│  │    3. 运行 agent_loop(history)                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              agent_loop() 核心循环                   │   │
│  │                                                     │   │
│  │   while True:                                       │   │
│  │       ├─► 调用 LLM API                              │   │
│  │       │    (messages + 5 tools)                     │   │
│  │       │                                             │   │
│  │       ├─► 追踪 TodoWrite 使用                       │   │
│  │       │    used_todo = (tc.name == "TodoWrite")     │   │
│  │       │                                             │   │
│  │       ├─► 更新计数器                                │   │
│  │       │    if used_todo: rounds = 0                │   │
│  │       │    else: rounds += 1                       │   │
│  │       │                                             │   │
│  │       ├─► 检查 NAG_REMINDER                         │   │
│  │       │    if rounds > 10: 注入提醒                 │   │
│  │       │                                             │   │
│  │       └─► 继续循环或返回                            │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 带规划的任务执行示例

```
用户: "重构认证模块，添加测试，更新文档"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 模型创建计划                                        │
│                                                             │
│  > TodoWrite:                                               │
│    [ ] 重构认证模块                                          │
│    [ ] 添加单元测试                                          │
│    [ ] 更新文档                                              │
│                                                             │
│  rounds_without_todo = 0 (重置)                              │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 模型标记第一个任务为进行中                            │
│                                                             │
│  > TodoWrite:                                               │
│    [>] 重构认证模块 <- 正在重构认证模块                       │
│    [ ] 添加单元测试                                          │
│    [ ] 更新文档                                              │
│                                                             │
│  > read_file: src/auth/login.py                             │
│  > read_file: src/auth/utils.py                             │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 完成第一个任务                                      │
│                                                             │
│  > edit_file: src/auth/login.py (重构代码)                   │
│  > TodoWrite:                                               │
│    [x] 重构认证模块                                          │
│    [>] 添加单元测试 <- 正在添加单元测试                       │
│    [ ] 更新文档                                              │
│                                                             │
│  rounds_without_todo = 0 (每次使用 TodoWrite 都重置)         │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 完成所有任务                                        │
│                                                             │
│  > write_file: tests/test_auth.py                           │
│  > TodoWrite:                                               │
│    [x] 重构认证模块                                          │
│    [x] 添加单元测试                                          │
│    [>] 更新文档 <- 正在更新文档                               │
│                                                             │
│  > edit_file: README.md (更新文档)                           │
│  > TodoWrite:                                               │
│    [x] 重构认证模块                                          │
│    [x] 添加单元测试                                          │
│    [x] 更新文档                                              │
│                                                             │
│    (3/3 completed)                                          │
└─────────────────────────────────────────────────────────────┘
              ↓
        模型返回最终总结
```

### NAG_REMINDER 触发场景

```
用户: "帮我分析代码"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  模型直接开始分析，没有使用 TodoWrite                          │
│                                                             │
│  Round 1: > bash: find . -name "*.py"                        │
│  Round 2: > read_file: main.py                               │
│  ...                                                         │
│  Round 10: > read_file: utils.py                             │
│  Round 11: > bash: grep "TODO" .                             │
│                                                             │
│  rounds_without_todo = 11 > 10                               │
│                             ↓                                │
│  在下一条工具结果中注入：                                      │
│  "<reminder>10+ turns without todo update. Please update todos.</reminder>" │
│                                                             │
│  模型看到提醒，可以选择：                                      │
│  - 忽略（继续分析）                                           │
│  - 创建 TodoWrite 来跟踪分析任务                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心要点总结

### 1. 显式规划的价值

```python
# v1: 计划在模型脑海中（不可见）
"我先做 A，然后 B，然后 C"

# v2: 计划显式化（可见）
TodoWrite: [ ] A, [ ] B, [ ] C
```

### 2. 约束使能复杂任务

```
约束:
- Max 20 items
- One in_progress
- Required fields

使能:
- 可见的计划
- 跟踪的进度
- 完成的复杂任务
```

### 3. 软约束引导行为

```python
# 不强制，只是提醒
if rounds_without_todo > 10:
    results.insert(0, NAG_REMINDER)

# 模型可以选择：
# - 忽略提醒（简单任务）
# - 创建 todos（复杂任务）
```

### 4. 状态可视化

```python
# 渲染后的 todos
[x] 已完成的任务
[>] 正在做 <- 当前动作
[ ] 待办任务

(1/3 completed)  # 进度一目了然
```

---

[← 返回 README](../README_zh.md)
