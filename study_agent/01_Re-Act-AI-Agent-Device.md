# Re-Act AI Agent Device

## 什么是 Re-Act?

Re-Act (Reason + Act) 是一种范式，它提供了一种在语言模型的工作中结合推理和行动的方法（ReAct: Synergizing Reasoning and Acting in Language Models）。

与其他构建 agent 的方法不同，在那些方法中，模型要么只进行推理，要么只执行操作，要么立即给出答案，而 Re-Act 强制模型交替进行**逻辑推理**与**用户函数调用（或工具——Tools）**来与外部世界交互。模型生成一个思想和行动的序列，逐步向解决问题迈进。这种组合使 AI 能够同时考虑解决方案，并在必要时参考工具或外部数据。

> 一个小小的免责声明：Re-Act 并不是构建 AI agent 的灵丹妙药，也不是某种唯一正确的方法，它只是众多方法中的一种。在文章末尾，我会提供其他方法的示例链接。

## Re-Act Agent 的组件：

- **语言模型（LLM）**——是 agent 的"大脑"，生成决策步骤。它释放出思想（推理轨迹）并指示要执行的操作
- **工具（Tools）**——是 agent 可以调用的外部函数或 API，用于接收信息或执行操作。例如，互联网搜索、计算、数据库操作等。工具以名称和自然语言描述的形式注册，以便模型知道如何使用它们
- **Agent 执行器（Agent Executor）**——执行模型关于行动的决定，调用相应的工具并将结果返回给模型。在 Re-Act 的上下文中，这个组件实现了"思考 → 行动和观察"的循环
- **Agent 状态（State）**——累积的对话和行动历史。这包括用户请求、模型消息（思想/行动）和观察（工具结果）。状态随着步骤的完成而不断更新

## Re-Act Agent 工作循环

1. **接收请求（Query）**——agent 接收用户的输入消息，这成为初始状态
2. **生成推理和行动（Think）**——语言模型基于当前状态生成一个结论，包括：
   - **Thought**：内部推理，agent 分析任务并形成计划
   - **Action**：执行特定操作的指令（例如，使用特定参数调用工具）
3. **执行操作**——如果生成的输出包含命令（例如，`Action: Search["query"]`），执行器会调用相应的工具并获取结果
4. **状态更新（Observation）**——工具的结果被保存为观察并添加到交互历史中，之后循环重复：更新后的状态被传递给模型进行下一次迭代
5. **完成（END）**——如果模型生成了最终响应（例如，`Answer: ...`），循环中断并将响应返回给用户

![Re-Act agent 工作循环](https://www.yotec.net/wp-content/uploads/2025/02/751c68755ea7d4f5f1e77838e776356f.png)

## 内部反思和 Re-Act 方法

Re-Act 架构的关键特性之一是 agent 进行内部对话的能力，我们将其称为"Thoughts"。这个过程包括以下方面：

- **分析和规划**——agent 使用内部推理来分析输入信息，将复杂任务分解为可控的步骤，并确定进一步的行动。这可以看作是一种内部"头脑风暴"，模型在其中构建解决方案计划

- **推理示例**：
  - **规划**："要解决这个问题，首先需要收集初始数据，然后识别模式，最后准备最终报告。"
  - **分析**："错误表明与数据库的连接存在问题，很可能是访问设置不正确。"
  - **决策**："对于具有这种预算的用户来说，最佳选择是选择中端价位，因为它在价格和质量之间提供了最好的平衡。"
  - **问题解决**："在优化代码之前，应该先测量其性能，以了解哪些部分运行最慢。"
  - **记忆整合**："由于用户之前说过他更喜欢 Python，最好用这种语言提供代码示例。"
  - **自我反思**："之前的方法无效。我将尝试不同的策略来实现目标。"
  - **目标设定**："在开始任务之前，必须确定成功完成的标准。"
  - **优先级排序**："在添加新功能之前，必须先消除关键的安全漏洞。"

## Re-Act Agent 工作示例

让我们考虑一个最简单的 Re-Act agent 工作示例。在我们的示例中，假设用户想按当前汇率将 100 美元转换为欧元。

在简单实现中（内部使用 tavily 进行互联网搜索，使用 python REPL 运行任意 python 代码），与模型的通信 prompt 将如下所示：

> 尽可能最好地回答以下问题。你可以访问以下工具：
>
> **python_repl**(command: str, timeout: Optional[int] = None) -> str – 一个 Python shell。使用它来执行 python 命令。输入应该是有效的 python 命令。如果你想查看值的输出，应该用 print(...) 将其打印出来。
>
> **tavily_search_results_json** – 一个针对全面、准确和可信结果进行优化的搜索引擎。当你需要回答有关当前事件的问题时很有用。输入应该是搜索查询。
>
> **使用以下格式：**
>
> Question: _你必须回答的输入问题_
>
> Thought: _你应该总是考虑要做什么_
>
> _Action: 要采取的行动，应该是 [python_repl, tavily_search_results_json] 之一_
>
> Action Input: _行动的输入_
>
> Observation: _行动的结果...（这个 Thought/Action/Action Input/Observation 可以重复 N 次）_
>
> Thought: _我现在知道最终答案了_
>
> Final Answer: _原始输入问题的最终答案_
>
> **开始！**
>
> Question: ___按当前汇率 100 美元是多少欧元？___
>
> Thought:

以下是 LLM 在 Think -> Action -> Observation 循环的第一次迭代中的响应示例：

> Thought: _要找到答案，我们需要知道美元和欧元之间的当前汇率。_
>
> Action: ___tavily_search_results_json___
>
> Action Input: __"给我当前的美元欧元汇率"__

正如我们所见，LLM 思考（Thought）首先需要获取当前汇率。并决定调用 tavily 来查找它（Action）。

agent 回答此示例问题的完整工作循环将如下所示：

![Re-Act agent 完整工作循环](https://www.yotec.net/wp-content/uploads/2025/02/5a5edfc4fa50d980b519a561548c2d7f.png)

首先，模型使用 tavily (tavily_search_results_json) 识别当前汇率，然后它建议调用 python_repl 将 100 美元转换为欧元并输出答案：

> 计算结果表明，按当前汇率，100 美元将转换为约 95.7 欧元。
>
> **Final Answer: 95.7 欧元**

基于 LangGraph 的此示例的 Python 代码将如下所示：

```python
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain_experimental.utilities import PythonREPL

python_repl = PythonREPL()

repl_tool = Tool(
    name="python_repl",
    description="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
    func=python_repl.run,
)

llm = ChatOpenAI(model_name="gpt-4o-mini")
tools = [repl_tool, TavilySearchResults(max_results=1)]

prompt = hub.pull("hwchase17/react")

# 构建ReAct agent
agent = create_react_agent(llm, tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

agent_executor.invoke({"input": "How much will 100 dollars be in euros at the current exchange rate?"})
```

## Re-Act Agents 实现细节

从理论转向实践，应该说不同框架中的实际实现与原始文章（ReAct: Synergizing Reasoning and Acting in Language Models）中提出的方法有所不同，因为该文章发布时间相对较早，在此期间 LLM 的发展已经大大推进。

例如，以下是 LangGraph 库中预构建 agent 的一些有趣实现细节：

- LangGraph 使用 tool-calling（function-calling）技术（https://platform.openai.com/docs/guides/function-calling）使 LLM 决定调用用户函数，而文章使用原始文本 prompt 和解析来处理 LLM 在响应中输出的内容。这是因为在撰写本文时，内置的 tool-calling 尚不存在。现在许多现代 LLM（甚至是开源和本地部署的）都经过专门的函数调用技术训练（例如，Qwen 中的 tool calling）。
- LangGraph 使用参数数组来调用工具，而不是将所有参数作为一个大字符串传递。同样，这是由于撰写本文时存在的 LLM 限制。
- LangGraph 允许一次调用多个工具。
- 最后，文章在决定调用哪些工具之前明确生成了 Thought 阶段。这是 Re-Act 中 Reasoning 的一部分。LangGraph 默认不这样做，主要是因为 LLM 能力已显著提高，这不再那么必要。

## Re-Act 的优缺点

**Re-Act 不是万能解决方案，有其优缺点。**

### 优点：

- **灵活的逐步解决方案**——agent 独立规划和执行一系列操作。它可以从各种工具中选择，并在使用内存保存上下文的同时执行多个步骤。这允许动态解决复杂问题，将其分解为子任务。
- **易于开发**：Re-Act agents 相对容易实现，因为它们的逻辑简化为"思考-行动-观察"循环。许多框架（例如 LangGraph）已经提供现成的 Re-Act 实现。
- **通用性**：Re-Act agents 适用于各种领域——从信息搜索到设备管理——这得益于连接必要工具的能力。

### 缺点：

- **在某些场景中效率低**：每一步都需要单独的 LLM 调用，这使得解决方案对于长链来说缓慢、冗长且昂贵。每个操作（工具调用）都伴随着模型的反思，增加了对模型的调用总数。
- **没有全局计划**：agent 在每次迭代中只向前规划一步。由于缺乏整体计划，他可能选择次优的操作、进入死胡同或重复自己。这使得需要同时战略性地审查多个步骤的问题变得困难。
- **可扩展性有限**：如果 agent 有太多可能的工具或很长的历史记录，他很难选择正确的下一个操作。上下文和选项数量可能超过单个模型有效管理它们的能力，从而降低结果质量。

## 其他构建 Agent 的方法示例

正如我所说，Re-Act 并不是构建 AI agent 的唯一和最佳方法。此外，即使是官方原始文章也比较了 Re-Act 和 CoT，结果表明"vanilla"Re-Act 并不总是获胜。

现在经常开发混合方法，使用多种构建 agent 方法的变体和组合。例如，LangGraph 允许创建任意的 agent 图和多 agent 系统。

我将提供其他构建 agent 和 promptting 方法的示例，Re-Act 与它们竞争或可以与之结合：

- Chain-Of-Thought (CoT) – [链接](https://arxiv.org/abs/2201.11903)
- Self-Ask Prompting – [链接](https://arxiv.org/abs/2204.00598)
- Self-Discover – [链接](https://arxiv.org/abs/2402.03620)
- Tree-Of-Thought (ToT) – [链接](https://arxiv.org/abs/2305.10601)
- Language Agent Tree Search – [链接](https://arxiv.org/abs/2310.04406)
- Reflexion – [链接](https://arxiv.org/abs/2303.11366)
- MRKL Systems (Modular Reasoning, Knowledge and Language) – [链接](https://arxiv.org/abs/2205.00445)
- PAL (Program-aided Language Models) – [链接](https://arxiv.org/abs/2211.10435)
- Toolformer – [链接](https://arxiv.org/abs/2302.04761)

- 带规划的 Agents：
  - 规划和执行（Plan-and-Execute）– [参考 1](https://arxiv.org/abs/2306.04581), [参考 2](https://python.langchain.com/docs/langgraph#plan-and-execute)
  - ReWOO (Reasoning WithOut Observations) – [参考 1](https://arxiv.org/abs/2305.18323), [链接 2](https://python.langchain.com/docs/langgraph#rewoo)
  - LLMCompiler – [参考 1](https://arxiv.org/abs/2312.04510), [链接 2](https://python.langchain.com/docs/langgraph#llm-compiler)

- Multi-Agent Systems：
  - Network – [链接](https://python.langchain.com/docs/langgraph#multi-agent-network)
  - Supervisor – [链接](https://python.langchain.com/docs/langgraph#multi-agent-supervisor)
  - Hierarchical – [链接](https://python.langchain.com/docs/langgraph#multi-agent-hierarchical)

---

**原文链接**：https://www.yotec.net/re-act-ai-agent-device/
**翻译时间**：2026-03-11
