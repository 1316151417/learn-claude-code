# Claude Code 工具完全指南

本文档详细解读 Claude Code 内置的 18 个工具，按功能分类并说明使用场景。

## 目录

- [核心工具](#核心工具)
- [任务管理工具](#任务管理工具)
- [计划模式工具](#计划模式工具)
- [用户交互工具](#用户交互工具)
- [MCP 扩展工具](#mcp-扩展工具)

---

## 核心工具

### Bash

**功能**: 执行 shell 命令

**用途**: 万能工具，可以运行任何命令行操作
- 文件操作: `ls`, `find`, `cp`, `mv`
- Git 操作: `git status`, `git commit`, `git push`
- 包管理: `npm install`, `pip install`, `cargo build`
- 系统操作: `ps`, `kill`, `curl`

**限制**:
- 默认 60 秒超时
- 输出截断至 50KB
- 危险命令会被阻止

**示例**:
```bash
git log --oneline -10
npm test
find . -name "*.py" | head -20
```

---

### Glob

**功能**: 文件路径模式匹配

**用途**: 快速查找符合特定模式的文件
- 查找所有 Python 文件: `**/*.py`
- 查找测试文件: `tests/**/*.test.js`
- 查找配置文件: `**/*.json`

**优势**: 比 `find` 命令更快，专为代码库搜索优化

**示例**:
```
src/components/**/*.tsx    # 所有 React 组件
**/*.md                   # 所有 Markdown 文件
tests/test_*.py           # 测试文件
```

---

### Grep

**功能**: 代码内容搜索（基于 ripgrep）

**用途**: 在文件中搜索特定内容
- 查找函数定义: `def function_name`
- 查找变量使用: `myVariable`
- 正则表达式: `class \w+Controller`

**参数**:
- `-i`: 忽略大小写
- `-C`: 显示上下文行
- `--glob`: 限制文件类型

**示例**:
```bash
# 查找函数调用
grep -r "fetchData(" --include="*.js"

# 查找 TODO 注释
grep -r "TODO" --glob="*.py"

# 带上下文的搜索
grep -C 3 "class User" src/
```

---

### Read

**功能**: 读取文件内容

**用途**: 理解现有代码、查看配置
- 支持大文件的行数限制
- 自动处理编码
- 返回格式化内容

**参数**:
- `offset`: 起始行号
- `limit`: 最大读取行数

**示例**:
```
读取整个文件: src/main.py
读取前 50 行: src/main.py (limit: 50)
读取特定行: src/main.py (offset: 100, limit: 50)
```

---

### Write

**功能**: 写入文件内容

**用途**: 创建新文件或完全重写现有文件
- 自动创建父目录
- 覆盖现有内容
- 适用于新文件创建

**使用场景**:
- 创建新的模块文件
- 生成配置文件
- 写入测试代码

---

### Edit

**功能**: 精确编辑文件（字符串替换）

**用途**: 对现有代码进行精确修改
- 替换特定函数
- 修改配置值
- 重命名变量

**工作原理**: 精确字符串匹配，只替换第一次出现

**优势**: 比 Write 更安全，不会影响文件其他部分

---

### NotebookEdit

**功能**: 编辑 Jupyter Notebook 单元格

**用途**: 操作 `.ipynb` 文件
- 替换单元格内容
- 添加新单元格
- 删除单元格

**使用场景**:
- 数据科学项目
- 自动化 Notebook 更新
- 批量修改分析

---

### TodoWrite

**功能**: 任务列表管理

**用途**: 跟踪复杂任务进度

**约束**:
- 最多 20 个任务
- 同时只有 1 个 `in_progress`
- 必须包含: `content`, `status`, `activeForm`

**状态流程**:
```
pending → in_progress → completed
```

**使用场景**:
- 多步骤代码重构
- 复杂功能开发
- 调试任务分解

---

### WebSearch

**功能**: 网页搜索

**用途**: 获取最新信息
- 查找技术文档
- 搜索错误解决方案
- 获取最新版本信息

**注意**: 实际搜索服务由底层 API 决定
- Anthropic API: 使用 Claude 的搜索
- 智谱 API: 使用 web_search_prime

---

## 任务管理工具

### Task

**功能**: 启动子代理处理复杂任务

**用途**: 将复杂任务委托给专门的子代理

**子代理类型**:

| 类型 | 用途 | 可用工具 |
|------|------|----------|
| `explore` | 探索代码库 | Bash, Read, Glob, Grep |
| `code` | 代码修改 | 全部工具 |
| `plan` | 架构分析 | 只读工具 |
| `general-purpose` | 通用任务 | 所有工具 |

**使用场景**:
- 大型代码库探索
- 独立任务并行执行
- 上下文隔离

---

### TaskOutput

**功能**: 获取后台任务输出

**用途**: 检查后台运行任务的进度和结果

**参数**:
- `task_id`: 任务 ID
- `block`: 是否等待完成
- `timeout`: 超时时间

---

### TaskStop

**功能**: 停止后台任务

**用途**: 终止运行中的任务

**使用场景**:
- 任务卡住时
- 不再需要结果时
- 资源限制时

---

## 计划模式工具

### EnterPlanMode

**功能**: 进入计划模式

**用途**: 在实现复杂功能前先规划

**工作流程**:
1. 探索代码库
2. 设计实现方案
3. 用户审核批准
4. 执行实现

**使用场景**:
- 大型功能开发
- 架构重构
- 需要多文件修改的任务

---

### ExitPlanMode

**功能**: 退出计划模式并开始执行

**用途**: 完成规划后，请求用户批准并开始实现

**参数**:
- `allowedPrompts`: 定义允许的操作类型

---

### Skill

**功能**: 加载领域技能

**用途**: 加载存储在 `skills/<name>/SKILL.md` 的领域知识

**技能格式**:
```yaml
---
name: skill-name
description: 技能描述
---

# 技能详细说明
...
```

**优势**: 无需重新训练即可添加专业知识

---

## 用户交互工具

### AskUserQuestion

**功能**: 向用户提问

**用途**: 在执行前获取用户输入或决策

**参数**:
- `questions`: 问题列表（最多 4 个）
- `multiSelect`: 是否允许多选
- `options`: 选项列表

**使用场景**:
- 选择技术方案
- 确认操作
- 获取配置信息

---

## MCP 扩展工具

### mcp__4_5v_mcp__analyze_image

**功能**: 图像分析

**用途**: 使用 AI 视觉模型分析图片
- 理解图片内容
- 提取文字信息
- 分析 UI 设计

**参数**:
- `imageSource`: 图片 URL
- `prompt`: 分析提示词

---

### mcp__web_reader__webReader

**功能**: 网页阅读器

**用途**: 获取网页内容并转换为 Markdown
- 抓取网页内容
- 转换为可读格式
- 保留图片和链接

**参数**:
- `url`: 网页地址
- `return_format`: 返回格式

---

## 工具使用原则

### 1. 优先使用专用工具

```
✅ 好的做法:
- 用 Glob 查找文件
- 用 Grep 搜索内容
- 用 Read 读取文件

❌ 不好的做法:
- 全部用 Bash + find/grep/cat
```

### 2. 安全性考虑

- 路径限制在项目目录内
- 危险命令会被阻止
- 文件操作有权限检查

### 3. 性能优化

- Glob 比 `find` 更快
- Grep 使用 ripgrep，性能优异
- 大文件使用 Read 的 limit 参数

### 4. 工具组合

典型的代码修改流程:
```
1. Glob / Grep → 找到文件
2. Read → 理解代码
3. Edit → 修改代码
4. Bash + git → 提交更改
```

---

## 工具配置

### 限制工具使用

```bash
# 只允许特定工具
claude --allowed-tools Bash,Read,Glob

# 禁用特定工具
claude --disallowed-tools WebSearch,Edit

# 使用默认工具集
claude --tools default
```

### 工具权限模式

```bash
# 默认: 危险工具需要确认
claude --permission-mode default

# 自动接受文件编辑
claude --permission-mode acceptEdits

# 跳过所有权限检查（仅沙盒环境）
claude --permission-mode bypassPermissions
```

---

## 总结

| 类别 | 工具数量 | 核心价值 |
|------|----------|----------|
| 核心工具 | 9 | 文件和命令操作 |
| 任务管理 | 3 | 并行和异步执行 |
| 计划模式 | 3 | 复杂任务规划 |
| 用户交互 | 2 | 人机协作 |
| MCP 扩展 | 2 | 外部服务集成 |

**关键洞察**: 模型是 80%，代码是 20%。工具提供能力，模型决定如何使用。
