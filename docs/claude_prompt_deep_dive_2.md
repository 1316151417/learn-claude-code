# Claude Code 系统提示词深度解析（10模块版）

**提示词来源**：Anthropic 官方 Claude Code CLI 完整系统提示（Sonnet 4，2025 年设计）  
**分析目标**：严格按你指定的 **10 个模块** 拆解，深度挖掘每一条指令的提示工程逻辑、实现技巧、防御机制与可复用价值。每一模块不仅覆盖你列出的要点，还补充提示词原文细节、设计意图、实战效果与学习启发。

## 1. 身份定义与安全防御（角色边界，安全防御）
提示词开篇第一句就定义：「You are an interactive CLI tool that helps users with software engineering tasks.」  
紧接着用 **3 次高强度重复** 强调：「Assist with defensive security tasks only. Refuse to create, modify, or improve code that may be used maliciously.」并列出允许范围（安全分析、检测规则、漏洞解释、防御工具、文档）。  
**设计意图**：让模型从 token 第 1 位就建立「铁壁角色边界」，防止任何越界行为。  
**实战效果**：用户一旦问「写个后门」或「帮我做 XSS payload」，模型会直接拒绝且不解释原因（避免说教）。  
**学习启发**：安全提示词最强写法 = 「角色一句话 + 重复 3 次负面禁令 + 精确允许清单」，可直接套用在任何企业级代理中。

## 2. 语气和风格（适配CLI、简化输出、省TOKEN 减少上下文）
核心指令：「You MUST answer concisely with fewer than 4 lines」「minimize output tokens」「Answer the user's question directly, without elaboration」「One word answers are best」。  
附赠 **6 个极致简洁示例**（2+2=4、ls、prime number、git status 等）。  
改完文件后「just stop, rather than providing an explanation」。  
**设计意图**：把大模型输出从「聊天机器人」彻底变成「真实 CLI 工具」，减少上下文膨胀。  
**实战效果**：用户在终端里看到的就是干净的命令行反馈，没有任何「我帮你做了什么」的废话墙。  
**学习启发**：用「具体例子轰炸 + MUST 强制 + 负面指令」三连，是控制输出长度的核武器，比单纯说「简洁」有效 10 倍。

## 3. 主动性平衡（该干什么干什么，别多干、少干）
专设「Proactiveness」章节：「You are allowed to be proactive, but only when the user asks you to do something」「first answer their question first, and not immediately jump into taking actions」「Do not surprise the user」。  
**设计意图**：解决 AI 代理最常见的「过度热情」问题，让用户始终掌握控制权。  
**实战效果**：用户问「怎么实现 X」时，模型会先给出思路，再问「要我现在动手改代码吗？」而不是直接改文件。  
**学习启发**：在提示词里明确「先回答问题，再行动」的优先级顺序，是让代理既聪明又听话的关键。

## 4. 参考现有包依赖、代码风格
指令：「NEVER assume that a given library is available」「first check that this codebase already uses the given library」「When you edit a piece of code, first look at the code's surrounding context (especially its imports)」「Mimic code style, use existing libraries and utilities, and follow existing patterns」。  
**设计意图**：杜绝幻觉依赖和风格不一致。  
**实战效果**：模型会先用搜索工具看 package.json、邻近文件、import，再决定用什么框架。  
**学习启发**：把「先观察再模仿」写成强制步骤，是让模型写出「像原生开发者」代码的最有效方法。

## 5. 代码不要写注释（省token 减少上下文）
**铁律**：「IMPORTANT: DO NOT ADD ***ANY*** COMMENTS unless asked」。用粗体+星号三连强调。  
**设计意图**：直接砍掉最浪费 token 的部分（注释通常占 20-30% 代码量）。  
**实战效果**：生成的代码极度干净，上下文窗口压力大幅降低，适合长会话多文件编辑。  
**学习启发**：把「不要加注释」作为独立模块硬编码，比让模型「尽量少写」强太多。

## 6. 复杂任务规划
**强制要求**：「Always use the TodoWrite tool to plan and track tasks」「Use these tools VERY frequently」「It is critical that you mark todos as completed as soon as you are done」。  
提供 **2 个完整拆解示例**（修复 10 个类型错误、实现新功能）。  
**设计意图**：把模型的思考过程外部化，防止长任务遗忘或混乱。  
**实战效果**：用户实时看到「正在处理第 3/12 项」「已完成 7 项」，进度透明。  
**学习启发**：用专用工具强制「规划-执行-标记」循环，是构建可靠长任务代理的核心技巧。

## 7. 任务处理流程（先判断要不要规划？再判断要不要使用工具？做完需要验证？不要提交代码！）
标准流程隐含在多处：
- 先判断是否需要 TodoWrite 规划
- 大量使用搜索工具理解代码库
- 改完**强制**运行 lint + typecheck（「VERY IMPORTANT」）
- 「NEVER commit changes unless the user explicitly asks you to」  
  **设计意图**：形成闭环验证 + 用户最终控制权。  
  **实战效果**：代码质量有保障，用户不会被意外 git commit 吓到。  
  **学习启发**：把「规划 → 搜索 → 执行 → 验证 → 不提交」写成隐性流水线，是提示词工程的「流程化」典范。

## 8. 工具使用策略（优先使用特定工具而非bash、优先使用特定Task、多个工具并行调用）
- 「When doing file search, prefer to use the Task tool」「You should proactively use the Task tool with specialized agents」
- 「You can call multiple tools in a single response」「When making multiple bash tool calls, you MUST send a single message with multiple tools calls in parallel」
- 非平凡 bash 命令必须解释用途  
  **设计意图**：优先高效工具、减少上下文、并行提速。  
  **实战效果**：一次响应可同时跑 git status + 搜索 + 读取文件，速度飞起。  
  **学习启发**：明确「工具优先级 + 并行调用规则」，是让代理高效的关键。

## 9. 环境信息（工程目录、操作系统、是否git仓库、模型、知识截止时间）
每轮对话开头注入：<env> 标签，包含：
- Working directory
- Is directory a git repo
- Platform / OS Version
- Today's date
- Current branch + git status + 最近 5 次 commit
- 模型名（claude-sonnet-4-20250514）+ 知识截止时间（January 2025）  
  **设计意图**：让模型「知道自己在哪、用什么工具、时间线」避免幻觉。  
  **实战效果**：模型能准确说出「当前在 main 分支，干净状态」，或判断是否能跑 npm。  
  **学习启发**：把动态环境快照作为系统消息注入，是多轮对话保持一致性的神器。

## 10. 代码片段引用化（XxxFile.java:109）
强制格式：「When referencing specific functions or pieces of code include the pattern `file_path:line_number`」。  
**示例**：`src/services/process.ts:712`  
**设计意图**：让用户能一键跳转到准确位置（IDE 友好）。  
**实战效果**：用户直接 Ctrl+Click 就能定位，再也不用「大概在哪个文件」。  
**学习启发**：一个小小的格式规范，却极大提升了人机协作效率，可复制到任何代码代理。

**一句话总评**：  
这 10 个模块构成了 Claude Code 最强提示词铁三角——**安全边界 + 极致简洁 + 结构化流程**，堪称 2025 年提示工程教科书级别作品。

需要我再给你一个**可直接复制的精简中文模板**（把这 10 条浓缩成 800 字可直接套用），还是针对某一模块继续深挖？随时说。