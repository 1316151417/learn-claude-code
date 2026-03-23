"""
LangGraph Streaming 综合示例

演示所有核心流式模式（除 debug）：
1. values - 完整状态
2. updates - 状态更新
3. messages - LLM tokens
4. custom - 自定义数据
5. checkpoints - 检查点
6. tasks - 任务事件
"""
from typing import TypedDict
from dataclasses import dataclass
import operator
from typing_extensions import Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain.messages import AnyMessage

from common.llm_config import get_default_llm


# ==================== 定义状态 ====================
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


class TopicState(TypedDict):
    topic: str
    joke: str


@dataclass
class DataState:
    topic: str
    result: str = ""
    progress: int = 0


# ==================== 示例 1: values 模式 ====================
def demo_values_mode():
    """
    values 模式：流式输出每步后的完整状态
    """
    print("\n" + "="*60)
    print("示例 1: VALUES 模式 - 完整状态流")
    print("="*60)

    def refine_topic(state: TopicState):
        return {"topic": state["topic"] + " and cats"}

    def generate_joke(state: TopicState):
        return {"joke": f"This is a joke about {state['topic']}"}

    graph = (
        StateGraph(TopicState)
        .add_node(refine_topic)
        .add_node(generate_joke)
        .add_edge(START, "refine_topic")
        .add_edge("refine_topic", "generate_joke")
        .add_edge("generate_joke", END)
        .compile()
    )

    print("\n--- 每步的完整状态 ---")
    for chunk in graph.stream(
        {"topic": "ice cream"},
        stream_mode="values",
        version="v2",
    ):
        if chunk["type"] == "values":
            state = chunk["data"]
            print(f"topic: '{state.get('topic', '')}', joke: '{state.get('joke', '')}'")


# ==================== 示例 2: updates 模式 ====================
def demo_updates_mode():
    """
    updates 模式：只流式输出状态的变化部分
    """
    print("\n" + "="*60)
    print("示例 2: UPDATES 模式 - 状态变化流")
    print("="*60)

    def refine_topic(state: TopicState):
        return {"topic": state["topic"] + " and cats"}

    def generate_joke(state: TopicState):
        return {"joke": f"This is a joke about {state['topic']}"}

    graph = (
        StateGraph(TopicState)
        .add_node(refine_topic)
        .add_node(generate_joke)
        .add_edge(START, "refine_topic")
        .add_edge("refine_topic", "generate_joke")
        .add_edge("generate_joke", END)
        .compile()
    )

    print("\n--- 每个节点的状态更新 ---")
    for chunk in graph.stream(
        {"topic": "ice cream"},
        stream_mode="updates",
        version="v2",
    ):
        if chunk["type"] == "updates":
            for node_name, state_update in chunk["data"].items():
                print(f"Node `{node_name}` updated: {state_update}")


# ==================== 示例 3: messages 模式 ====================
def demo_messages_mode():
    """
    messages 模式：流式输出 LLM tokens
    """
    print("\n" + "="*60)
    print("示例 3: MESSAGES 模式 - LLM Token 流")
    print("="*60)

    from langchain.messages import HumanMessage
    from langgraph.config import get_stream_writer

    model = get_default_llm()

    def call_model(state: MessagesState):
        """调用 LLM 生成回复"""
        writer = get_stream_writer()
        writer({"status": "LLM 正在思考..."})

        response = model.invoke(state["messages"])
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1
        }

    graph = (
        StateGraph(MessagesState)
        .add_node(call_model)
        .add_edge(START, "call_model")
        .compile()
    )

    print("\n--- LLM Token 流式输出 ---")
    for chunk in graph.stream(
        {"messages": [HumanMessage(content="用一句话介绍 Python")], "llm_calls": 0},
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] == "messages":
            msg, metadata = chunk["data"]
            if hasattr(msg, 'content') and msg.content:
                print(msg.content, end="", flush=True)


# ==================== 示例 4: custom 模式 ====================
def demo_custom_mode():
    """
    custom 模式：流式输出自定义数据（进度、状态等）
    """
    print("\n" + "="*60)
    print("示例 4: CUSTOM 模式 - 自定义数据流")
    print("="*60)

    from langgraph.config import get_stream_writer

    def process_with_progress(state: DataState):
        """带进度报告的处理节点"""
        writer = get_stream_writer()

        # 模拟多步骤处理
        steps = [
            (1, "正在分析主题..."),
            (2, "正在生成内容..."),
            (3, "正在优化结果..."),
            (4, "完成!")
        ]

        result = ""
        for progress, status in steps:
            writer({"progress": progress, "status": status})
            result += f"[{progress}] {status}\n"

        return {"result": result, "progress": 100}

    graph = (
        StateGraph(DataState)
        .add_node(process_with_progress)
        .add_edge(START, "process_with_progress")
        .compile()
    )

    print("\n--- 自定义进度数据流 ---")
    for chunk in graph.stream(
        {"topic": "AI Agents"},
        stream_mode="custom",
        version="v2",
    ):
        if chunk["type"] == "custom":
            data = chunk["data"]
            print(f"进度: {data['progress']}% - {data['status']}")


# ==================== 示例 5: checkpoints 模式 ====================
def demo_checkpoints_mode():
    """
    checkpoints 模式：流式输出检查点事件（需要 checkpointer）
    """
    print("\n" + "="*60)
    print("示例 5: CHECKPOINTS 模式 - 检查点事件流")
    print("="*60)

    def step1(state: TopicState):
        return {"topic": state["topic"] + " -> step1"}

    def step2(state: TopicState):
        return {"joke": f"Joke about {state['topic']}"}

    checkpointer = MemorySaver()

    graph = (
        StateGraph(TopicState)
        .add_node(step1)
        .add_node(step2)
        .add_edge(START, "step1")
        .add_edge("step1", "step2")
        .add_edge("step2", END)
        .compile(checkpointer=checkpointer)
    )

    config = {"configurable": {"thread_id": "demo-thread-1"}}

    print("\n--- 检查点事件 ---")
    for chunk in graph.stream(
        {"topic": "demo"},
        config=config,
        stream_mode="checkpoints",
        version="v2",
    ):
        if chunk["type"] == "checkpoints":
            checkpoint = chunk["data"]
            print(f"检查点 - 步骤: {checkpoint.get('metadata', {}).get('source', 'unknown')}")
            print(f"  状态: {checkpoint.get('channel_values', {})}")


# ==================== 示例 6: tasks 模式 ====================
def demo_tasks_mode():
    """
    tasks 模式：流式输出任务开始/结束事件
    """
    print("\n" + "="*60)
    print("示例 6: TASKS 模式 - 任务事件流")
    print("="*60)

    from langgraph.config import get_stream_writer

    def task_node(state: DataState):
        """一个简单的任务节点"""
        writer = get_stream_writer()
        writer({"task_status": "开始处理..."})

        result = f"处理结果: {state.topic}"
        return {"result": result}

    checkpointer = MemorySaver()

    graph = (
        StateGraph(DataState)
        .add_node(task_node)
        .add_edge(START, "task_node")
        .compile(checkpointer=checkpointer)
    )

    config = {"configurable": {"thread_id": "demo-thread-2"}}

    print("\n--- 任务事件 ---")
    for chunk in graph.stream(
        {"topic": "test task"},
        config=config,
        stream_mode="tasks",
        version="v2",
    ):
        if chunk["type"] == "tasks":
            task_event = chunk["data"]
            print(f"任务: {task_event.get('name', 'unknown')}")
            print(f"  状态: {task_event.get('event', 'unknown')}")
            if task_event.get('result'):
                print(f"  结果: {task_event['result']}")


# ==================== 示例 7: 多模式混合 ====================
def demo_multiple_modes():
    """
    同时使用多个流式模式
    """
    print("\n" + "="*60)
    print("示例 7: 多模式混合 - UPDATES + CUSTOM")
    print("="*60)

    from langgraph.config import get_stream_writer

    def smart_node(state: DataState):
        """同时输出状态更新和自定义数据"""
        writer = get_stream_writer()

        # 发送自定义进度数据
        writer({"progress": 50, "message": "处理中..."})

        return {"result": f"Processed: {state.topic}"}

    graph = (
        StateGraph(DataState)
        .add_node(smart_node)
        .add_edge(START, "smart_node")
        .compile()
    )

    print("\n--- 混合流式输出 ---")
    for chunk in graph.stream(
        {"topic": "multi-mode demo"},
        stream_mode=["updates", "custom"],
        version="v2",
    ):
        if chunk["type"] == "updates":
            for node_name, update in chunk["data"].items():
                print(f"[状态更新] {node_name}: {update}")
        elif chunk["type"] == "custom":
            print(f"[自定义数据] {chunk['data']}")


# ==================== 主函数 ====================
def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("LangGraph Streaming 综合示例")
    print("="*60)

    # 运行各个示例
    demo_values_mode()
    demo_updates_mode()
    demo_messages_mode()
    demo_custom_mode()
    demo_checkpoints_mode()
    demo_tasks_mode()
    demo_multiple_modes()

    print("\n" + "="*60)
    print("所有示例运行完成!")
    print("="*60)


if __name__ == "__main__":
    main()
