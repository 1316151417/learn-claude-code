"""
LangGraph Memory 极简示例

演示 Short-term（会话记忆）和 Long-term（长期记忆）
"""
from dataclasses import dataclass
import uuid

from langchain.messages import HumanMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.runtime import Runtime
from common.llm_config import get_default_llm


# ==================== 定义状态 ====================
class ChatState(MessagesState):
    """聊天状态，继承 MessagesState 自动支持消息累加"""
    user_id: str


@dataclass
class Context:
    """上下文：传入用户 ID"""
    user_id: str


# ==================== 定义节点 ====================
def chat_node(state: ChatState, runtime: Runtime[Context]):
    """聊天节点：使用短期和长期记忆"""
    # runtime.context 可能是 None，需要处理
    user_id = (runtime.context or {}).user_id if runtime.context else state.get("user_id", "unknown")
    store = runtime.store

    # 从长期记忆中获取用户信息
    namespace = ("user", user_id)
    memories = store.search(namespace)
    user_info = "\n".join([m.value.get("info", "") for m in memories]) if memories else "无"

    print(f"[长期记忆] 用户信息: {user_info}")

    # 调用 LLM
    model = get_default_llm()
    system_prompt = f"你是一个友好的助手。用户信息：{user_info}"
    messages = [HumanMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    # 检测是否需要记住信息
    last_msg = state["messages"][-1].content
    if "记住" in last_msg:
        # 保存到长期记忆
        memory_id = str(uuid.uuid4())
        store.put(namespace, memory_id, {"info": f"用户说：{last_msg}"})
        print(f"[长期记忆] 已保存: {last_msg}")

    return {"messages": [response]}


# ==================== 构建 Graph（带 Memory）====================
checkpointer = MemorySaver()  # Short-term memory
store = InMemoryStore()        # Long-term memory

graph = (
    StateGraph(ChatState, context_schema=Context)
    .add_node("chat", chat_node)
    .add_edge(START, "chat")
    .add_edge("chat", END)
    .compile(checkpointer=checkpointer, store=store)
)


def main():
    print("=" * 60)
    print("LangGraph Memory 示例")
    print("=" * 60)

    # ========== 场景 1: Short-term Memory（会话记忆）==========
    print("\n【场景 1】Short-term Memory - 同一会话内记住上下文")
    print("-" * 40)

    config = {"configurable": {"thread_id": "session-1"}}

    # 第一轮
    print("\n[用户] 你好，我是小明")
    result = graph.invoke(
        {"messages": [HumanMessage(content="你好，我是小明")], "user_id": "user-1"},
        config,
        context=Context(user_id="user-1")
    )
    print(f"[AI] {result['messages'][-1].content}")

    # 第二轮（同一会话）
    print("\n[用户] 我叫什么名字？")
    result = graph.invoke(
        {"messages": [HumanMessage(content="我叫什么名字？")], "user_id": "user-1"},
        config,
        context=Context(user_id="user-1")
    )
    print(f"[AI] {result['messages'][-1].content}")

    # ========== 场景 2: 不同会话 ==========
    print("\n\n【场景 2】不同 thread_id = 不同会话")
    print("-" * 40)

    config2 = {"configurable": {"thread_id": "session-2"}}

    print("\n[用户] 我叫什么名字？")
    result = graph.invoke(
        {"messages": [HumanMessage(content="我叫什么名字？")], "user_id": "user-1"},
        config2,
        context=Context(user_id="user-1")
    )
    print(f"[AI] {result['messages'][-1].content}")
    print("💡 不同的 thread_id，无法获取之前会话的记忆")

    # ========== 场景 3: Long-term Memory（跨会话记忆）==========
    print("\n\n【场景 3】Long-term Memory - 跨会话保存信息")
    print("-" * 40)

    config3 = {"configurable": {"thread_id": "session-3"}}

    # 第一轮：让 AI 记住
    print("\n[用户] 请记住我喜欢编程")
    result = graph.invoke(
        {"messages": [HumanMessage(content="请记住我喜欢编程")], "user_id": "user-2"},
        config3,
        context=Context(user_id="user-2")
    )
    print(f"[AI] {result['messages'][-1].content}")

    # 第二轮：新会话，但同一 user
    config4 = {"configurable": {"thread_id": "session-4"}}
    print("\n[用户] 我有什么爱好？")
    result = graph.invoke(
        {"messages": [HumanMessage(content="我有什么爱好？")], "user_id": "user-2"},
        config4,
        context=Context(user_id="user-2")
    )
    print(f"[AI] {result['messages'][-1].content}")
    print("💡 通过 store，即使新会话也能记住用户信息")

    print("\n" + "=" * 60)
    print("💡 核心概念:")
    print("  - Short-term Memory (checkpointer)")
    print("    · thread_id 标识会话")
    print("    · 同一会话内记住对话历史")
    print("    · 不同 thread_id = 不同记忆")
    print("")
    print("  - Long-term Memory (store)")
    print("    · 跨会话持久化用户数据")
    print("    · 通过 namespace 组织（如 user_id）")
    print("    · 支持语义搜索")
    print("=" * 60)


if __name__ == "__main__":
    main()
