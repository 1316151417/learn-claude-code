# v4_skills_agent.py 代码精读

**技能机制完整解析**

---

## 目录

1. [核心哲学：知识外部化](#1-核心哲学知识外部化)
2. [SkillLoader 类](#2-skillloader-类)
3. [SKILL.md 格式](#3-skillmd-格式)
4. [Skill 工具](#4-skill-工具)
5. [渐进式披露](#5-渐进式披露)
6. [缓存友好注入](#6-缓存友好注入)
7. [完整流程图](#7-完整流程图)

---

## 1. 核心哲学：知识外部化

### v3 的局限：模型知识有限

```
┌─────────────────────────────────────────────────────────────┐
│                模型内置知识的问题                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "处理这个 PDF 文件"                                    │
│                                                             │
│  模型 (内心): "嗯... 我知道 PDF 是什么，但怎么处理？           │
│             我应该用哪个库？pdftotext？PyMuPDF？"              │
│                                                             │
│  问题：                                                     │
│  - 模型的训练数据有截止日期                                    │
│  - 模型不熟悉最新的库和工具                                    │
│  - 领域特定的最佳实践可能未知                                  │
│  - 要"教"模型需要重新训练（昂贵！）                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### v4 的解决方案：技能系统

```
┌─────────────────────────────────────────────────────────────┐
│              知识外部化：技能文件                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "处理这个 PDF 文件"                                    │
│                                                             │
│  模型: "这个任务需要 pdf 技能"                                 │
│  > Skill(pdf)                                               │
│    └─ 加载 skills/pdf/SKILL.md                              │
│    └─ 内容注入到对话中                                       │
│    └─ 模型现在知道：                                         │
│       - 使用 pdftotext 进行快速提取                           │
│       - 使用 PyMuPDF 进行复杂处理                             │
│       - 如何处理加密 PDF                                      │
│       - 最佳实践和陷阱                                        │
│                                                             │
│  优势：                                                     │
│  - 知识存储在文件中，而非模型参数中                             │
│  - 可以随时更新，无需重新训练                                  │
│  - 任何人都可以创建技能                                       │
│  - 免费、快速、灵活                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 范式转移

```
┌─────────────────────────────────────────────────────────────┐
│        知识获取的范式转移                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  传统 AI：                                                   │
│  知识锁定在模型参数中                                         │
│  ↓ 要教授新技能                                               │
│  收集数据 → 训练 → 部署                                       │
│  成本：$10K-$1M+，时间：数周                                  │
│  需要：ML 专业知识，GPU 集群                                   │
│                                                             │
│  Skills:                                                    │
│  知识存储在可编辑文件中                                       │
│  ↓ 要教授新技能                                               │
│  编写 SKILL.md 文件                                          │
│  成本：免费，时间：分钟                                        │
│  需要：任何人都可以                                           │
│                                                             │
│  这就像是附加一个可热插拔的 LoRA 适配器，而无需任何训练！        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Tools vs Skills

| 概念 | 它是什么 | 示例 |
|------|---------|------|
| **Tool** | 模型**能**做什么 | bash, read_file, write |
| **Skill** | 模型**知道如何**做 | PDF 处理，MCP 开发 |

```
工具是能力。技能是知识。

Tool = Capability  (I CAN do this)
Skill = Expertise  (I KNOW HOW to do this well)
```

---

## 2. SkillLoader 类

### 完整类定义

```python
class SkillLoader:
    """
    从 SKILL.md 文件加载和管理技能。

    一个技能是一个包含以下内容的文件夹：
    - SKILL.md (必需)：YAML frontmatter + markdown 指令
    - scripts/ (可选)：模型可以运行的辅助脚本
    - references/ (可选)：额外文档
    - assets/ (可选)：输出用的模板、文件

    SKILL.md 格式：
    ----------------
        ---
        name: pdf
        description: Process PDF files. Use when reading, creating, or merging PDFs.
        ---

        # PDF Processing Skill

        ## Reading PDFs

        Use pdftotext for quick extraction:
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
            return "(no skills available)"

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
            ("scripts", "Scripts"),
            ("references", "References"),
            ("assets", "Assets")
        ]:
            folder_path = skill["dir"] / folder
            if folder_path.exists():
                files = list(folder_path.glob("*"))
                if files:
                    resources.append(f"{label}: {', '.join(f.name for f in files)}")

        if resources:
            content += f"\n\n**Available resources in {skill['dir']}:**\n"
            content += "\n".join(f"- {r}" for r in resources)

        return content

    def list_skills(self) -> list:
        """返回可用技能名称列表。"""
        return list(self.skills.keys())
```

### 技能目录结构

```
skills/
├── pdf/
│   ├── SKILL.md          # 必需：YAML frontmatter + Markdown 主体
│   ├── scripts/          # 可选：辅助脚本
│   │   └── extract.sh
│   ├── references/       # 可选：文档、规范
│   │   └── pdf_spec.pdf
│   └── assets/           # 可选：模板、输出文件
│       └── template.txt
├── mcp-builder/
│   ├── SKILL.md
│   └── references/
│       └── mcp_spec.md
└── code-review/
    ├── SKILL.md
    └── scripts/
        └── linter.py
```

### 解析示例

```python
# SKILL.md 内容
"""
---
name: pdf
description: Process PDF files. Use when reading, creating, or merging PDFs.
---

# PDF Processing Skill

## Reading PDFs

Use pdftotext for quick extraction.
"""

# parse_skill_md() 返回
{
    "name": "pdf",
    "description": "Process PDF files. Use when reading, creating, or merging PDFs.",
    "body": "# PDF Processing Skill\n\n## Reading PDFs\n\nUse pdftotext for quick extraction.",
    "path": Path("/path/to/skills/pdf/SKILL.md"),
    "dir": Path("/path/to/skills/pdf")
}
```

---

## 3. SKILL.md 格式

### 完整示例

```markdown
---
name: pdf
description: Process PDF files. Use when reading, creating, or merging PDFs.
---

# PDF Processing Skill

This skill provides expertise in handling PDF files efficiently.

## Reading PDFs

### Quick Text Extraction

For simple text extraction, use `pdftotext`:

```bash
pdftotext input.pdf -
#                      ↑
#                  Output to stdout
```

### Complex Processing

For images, tables, or complex layouts, use `PyMuPDF`:

```python
import fitz  # PyMuPDF

doc = fitz.open("input.pdf")
page = doc[0]
text = page.get_text()
```

## Creating PDFs

Use `reportlab` for programmatic PDF creation:

```python
from reportlab.pdfgen import canvas

c = canvas.Canvas("output.pdf")
c.drawString(100, 750, "Hello PDF")
c.save()
```

## Common Issues

- **Encrypted PDFs**: Use `qpdf` to decrypt first
- **Corrupted files**: Try `pdftk` to recover
- **Large files**: Process page by page, not all at once
```

### Frontmatter 字段

| 字段 | 必需 | 说明 | 示例 |
|------|------|------|------|
| `name` | ✅ | 技能的唯一标识符 | `pdf`, `mcp-builder` |
| `description` | ✅ | 何时使用此技能 | "Process PDF files..." |

### Body 内容

- 使用 Markdown 格式
- 可以包含代码示例
- 可以列出最佳实践
- 可以说明常见陷阱

---

## 4. Skill 工具

### 工具定义

```python
SKILL_TOOL = {
    "name": "Skill",
    "description": f"""Load a skill to gain specialized knowledge for a task.

Available skills:
{SKILLS.get_descriptions()}

When to use:
- IMMEDIATELY when user task matches a skill description
- Before attempting domain-specific work (PDF, MCP, etc.)

The skill content will be injected into the conversation, giving you
detailed instructions and access to resources.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "Name of the skill to load"
            }
        },
        "required": ["skill"],
    },
}
```

### run_skill 实现

```python
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

    这就是生产系统保持成本效率的方式。
    """
    content = SKILLS.get_skill_content(skill_name)

    if content is None:
        available = ", ".join(SKILLS.list_skills()) or "none"
        return f"Error: Unknown skill '{skill_name}'. Available: {available}"

    # 包装在标签中，以便模型知道它是技能内容
    return f"""<skill-loaded name="{skill_name}">
{content}
</skill-loaded>

Follow the instructions in the skill above to complete the user's task."""
```

### 标签包装

```python
# 输出格式
<skill-loaded name="pdf">
# Skill: pdf

# PDF Processing Skill
...
</skill-loaded>

Follow the instructions in the skill above to complete the user's task.
```

**为什么使用标签？**
- 模型知道这是特殊内容
- 清晰的边界标记
- 可以引用特定技能

---

## 5. 渐进式披露

### 三层知识披露

```
┌─────────────────────────────────────────────────────────────┐
│               渐进式披露的三个层次                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: 元数据（始终加载）                                 │
│  ────────────────────────                                   │
│  在系统提示词中：                                             │
│  - pdf: Process PDF files...                                │
│  - mcp-builder: Build MCP servers...                        │
│                                                             │
│  成本：~100 tokens/skill                                    │
│  目的：让模型知道有哪些可用技能                                │
│                                                             │
│  ↓ 模型决定需要更多细节                                       ↓
│                                                             │
│  Layer 2: SKILL.md 主体（按需加载）                           │
│  ────────────────────────────────                            │
│  通过 Skill 工具注入：                                        │
│  <skill-loaded name="pdf">                                  │
│  # PDF Processing Skill                                     │
│  ## Reading PDFs                                            │
│  ...详细指令...                                             │
│  </skill-loaded>                                            │
│                                                             │
│  成本：~2000 tokens/skill                                   │
│  目的：提供完整的领域知识                                     │
│                                                             │
│  ↓ 模型决定需要更多资源                                        ↓
│                                                             │
│  Layer 3: 资源（按需）                                        │
│  ─────────────────                                         │
│  在技能内容中列出：                                           │
│  **Available resources:**                                   │
│  - Scripts: extract.sh, merge.py                           │
│  - References: pdf_spec.pdf                                 │
│                                                             │
│  成本：无限制（模型可以读取资源）                              │
│  目的：提供额外的工具和参考                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 为什么渐进式？

```python
# 假设：20 个技能

# 一次性加载所有内容（坏）
System = "...每个技能的完整内容..."  # 40,000+ tokens
# 问题：
# - 每次请求都发送
# - 大多数技能从未使用
# - 成本高昂

# 渐进式披露（好）
System = "...只有描述..."  # 2,000 tokens
# 只有当模型需要时才加载完整技能
# 成本：只在使用时支付
```

### 披露流程

```
┌─────────────────────────────────────────────────────────────┐
│               技能加载的决策流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户: "处理这个 PDF"                                         │
│            ↓                                                │
│  模型查看系统提示词中的 Layer 1（描述）                         │
│  "pdf: Process PDF files..."                               │
│            ↓                                                │
│  模型匹配："这个任务需要 pdf 技能！"                           │
│            ↓                                                │
│  调用 Skill(skill="pdf")                                    │
│            ↓                                                │
│  注入 Layer 2（完整内容）                                     │
│  <skill-loaded name="pdf">...详细指令...</skill-loaded>      │
│            ↓                                                │
│  模型现在知道如何处理 PDF                                     │
│            ↓                                                │
│  如果需要，模型可以读取 Layer 3 资源                            │
│  read_file(skills/pdf/scripts/extract.sh)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 缓存友好注入

### Prompt Cache 的重要性

```
┌─────────────────────────────────────────────────────────────┐
│              Prompt Cache 的成本影响                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Anthropic API 的缓存机制：                                    │
│  - 缓存前缀（system prompt + 早期消息）                       │
│  - 缓存命中：成本降低 90%                                     │
│  - 缓存失效：前缀改变时发生                                    │
│                                                             │
│  错误方式（使缓存失效）：                                      │
│  每次加载技能时修改 system prompt                             │
│  System = f"""...{SKILL_CONTENT}..."""                      │
│  → 前缀每次都变 → 缓存失效 → 成本 20-50x                      │
│                                                             │
│  正确方式（保持缓存）：                                        │
│  技能内容作为 tool_result 注入                                 │
│  messages.append({                                          │
│      "role": "user",                                        │
│      "content": [{"type": "tool_result", ...}]              │
│  })                                                          │
│  → 前缀不变 → 缓存命中 → 成本优化                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 注入位置对比

```python
# 错误：修改 system prompt（缓存失效）
def load_skill_wrong(skill_name):
    content = SKILLS.get_skill_content(skill_name)
    # 修改全局 system prompt
    global SYSTEM
    SYSTEM = f"{SYSTEM}\n\n{content}"

# 结果：
# Request 1: System = "original" → Cache miss
# Request 2: System = "original + skill" → Cache miss!
# Request 3: System = "original + skill" → Cache miss!
# 成本：每次都是完整价格

# 正确：作为 tool result 注入（保持缓存）
def load_skill_right(skill_name):
    content = SKILLS.get_skill_content(skill_name)
    # 返回作为 tool result
    return f"<skill-loaded>...content...</skill-loaded>"

# 结果：
# Request 1: System = "original" → Cache miss
# Request 2: System = "original" → Cache HIT! (+ skill result)
# Request 3: System = "original" → Cache HIT!
# 成本：后续请求便宜 90%
```

### 消息结构

```python
# 使用技能后的消息结构
messages = [
    {"role": "system", "content": SYSTEM},  # 不变！
    {"role": "user", "content": "处理这个 PDF"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "xxx",
                "content": "<skill-loaded name=\"pdf\">...技能内容...</skill-loaded>"
                #                    ↑
                #              技能在这里！
            }
        ]
    },
    {"role": "assistant", "content": "根据技能指南，我来处理 PDF..."}
]
```

---

## 7. 完整流程图

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    v4_skills_agent.py                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    启动阶段                          │   │
│  │  1. 初始化 SkillLoader                              │   │
│  │  2. 扫描 skills/ 目录                                │   │
│  │  3. 加载所有 SKILL.md 元数据                          │   │
│  │  4. 构建 SKILL_TOOL (带可用技能列表)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              System Prompt (Layer 1)                 │   │
│  │                                                     │   │
│  │  **Skills available** (invoke with Skill tool):     │   │
│  │  - pdf: Process PDF files...                        │   │
│  │  - mcp-builder: Build MCP servers...                │   │
│  │  - code-review: Review code systematically...        │   │
│  │                                                     │   │
│  │  ~100 tokens/skill                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              agent_loop() 主代理循环                 │   │
│  │                                                     │   │
│  │   while True:                                       │   │
│  │       ├─► 调用 LLM API                              │   │
│  │       │    (messages + ALL_TOOLS including Skill)  │   │
│  │       │                                             │   │
│  │       ├─► 如果是 Skill 工具                         │   │
│  │       │    └─► run_skill()                         │   │
│  │       │         ├─ 读取 SKILL.md 主体               │   │
│  │       │         ├─ 包装在 <skill-loaded> 标签中     │   │
│  │       │         └─ 作为 tool_result 返回           │   │
│  │       │                                             │   │
│  │       └─► 继续循环或返回                            │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 技能加载完整示例

```
用户: "从这个 PDF 中提取文本：document.pdf"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  主代理分析任务                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  模型查看系统提示词中的可用技能：                                │
│  - pdf: Process PDF files...                                │
│                                                             │
│  匹配："这个任务需要 pdf 技能！"                               │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  调用 Skill 工具                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  > Loading skill: pdf                                       │
│    Skill loaded (2847 chars)                                │
│                                                             │
│  Tool Result:                                               │
│  <skill-loaded name="pdf">                                  │
│  # Skill: pdf                                              │
│                                                             │
│  # PDF Processing Skill                                     │
│  ... (详细指令) ...                                          │
│  </skill-loaded>                                            │
│                                                             │
│  Follow the instructions in the skill above...              │
└─────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│  模型现在拥有 PDF 专业知识                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  根据技能指令，模型知道：                                      │
│  - 使用 pdftotext 进行快速文本提取                            │
│  - 命令格式：pdftotext input.pdf -                          │
│                                                             │
│  > bash: pdftotext document.pdf -                          │
│                                                             │
│  Tool Result:                                               │
│  "这是 PDF 的内容..."                                        │
└─────────────────────────────────────────────────────────────┘
              ↓
        模型返回处理后的文本
```

### 多技能协作示例

```
用户: "审查这个代码并建议改进：code.py"
              ↓
┌─────────────────────────────────────────────────────────────┐
│  主代理可能需要多个技能                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 加载 code-review 技能                                    │
│     > Loading skill: code-review                            │
│     <skill-loaded name="code-review">                       │
│     # Code Review Skill                                     │
│     ## Checklist                                            │
│     - Security issues                                       │
│     - Performance issues                                    │
│     - Code style                                            │
│     ...                                                     │
│     </skill-loaded>                                         │
│                                                             │
│  2. 模型应用审查清单                                          │
│     > read_file: code.py                                    │
│     > 分析代码                                               │
│     > 发现潜在的安全问题                                      │
│                                                             │
│  3. 如果需要格式化，可能加载其他技能                            │
│     > Loading skill: python-formatting                      │
│     ...                                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心要点总结

### 1. 知识外部化

```python
# 传统：知识在模型中
# 要教新知识 → 重新训练 → 昂贵！

# Skills: 知识在文件中
# 要教新知识 → 编写 SKILL.md → 免费！
```

### 2. Tools vs Skills

```
Tool = Capability (I CAN do this)
Skill = Expertise (I KNOW HOW to do this well)

bash: CAN run commands
pdf skill: KNOWS which PDF tools to use and how
```

### 3. 渐进式披露

```
Layer 1: 描述 (始终加载, ~100 tokens)
Layer 2: 完整内容 (按需加载, ~2000 tokens)
Layer 3: 资源 (按需访问, 无限制)
```

### 4. 缓存友好

```python
# 技能注入到 tool_result（用户消息）
# 而不是 system prompt
# → 保持前缀不变 → 缓存命中 → 成本优化
```

---

[← 返回 README](../README_zh.md)
