"""
LangGraph Streaming 极简示例

用一个 Graph 演示所有核心流式模式
"""
from dataclasses import dataclass

from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer

from common.llm_config import get_default_llm


# ==================== 定义状态 ====================
@dataclass
class State:
    topic: str
    result: str = ""
    messages: list[AnyMessage] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []


# ==================== 定义节点 ====================
def process_node(state: State):
    """简单处理节点：报告进度"""
    writer = get_stream_writer()
    writer({"progress": 50, "status": "处理中..."})
    return {"result": f"关于 {state.topic} 的处理结果"}


def llm_node(state: State):
    """LLM 节点：生成回复"""
    model = get_default_llm()
    response = model.invoke(state["messages"] if state.messages else [HumanMessage(content=f"介绍{state.topic}，一句话简短回复")])
    return {"messages": [response], "result": f"LLM分析了{state.topic}"}


# ==================== 构建 Graph ====================
checkpointer = MemorySaver()

graph = (
    StateGraph(State)
    .add_node("process", process_node)
    .add_node("llm", llm_node)
    .add_edge(START, "process")
    .add_edge("process", "llm")
    .add_edge("llm", END)
    .compile(checkpointer=checkpointer)
)


# ==================== 演示所有流式模式 ====================
def main():
    initial_state = {"topic": "Python编程", "messages": [], "result": ""}
    config = {"configurable": {"thread_id": "demo-thread"}}

    print("=" * 60)
    print("LangGraph Streaming 极简示例")
    print("=" * 60)

    # 1. values 模式
    print("\n【1. VALUES 模式】完整状态流")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="values", version="v2"):
        if chunk["type"] == "values":
            s = chunk["data"]
            print(f"  topic: {s.topic}, result: {s.result}")

    # 2. updates 模式
    print("\n【2. UPDATES 模式】状态变化流")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="updates", version="v2"):
        if chunk["type"] == "updates":
            for node, update in chunk["data"].items():
                print(f"  {node}: {update}")

    # 3. messages 模式
    print("\n【3. MESSAGES 模式】LLM Token 流")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="messages", version="v2"):
        if chunk["type"] == "messages":
            msg, _ = chunk["data"]
            if hasattr(msg, 'content') and msg.content:
                print(msg.content, end="", flush=True)
    print()

    # 4. custom 模式
    print("\n【4. CUSTOM 模式】自定义数据流")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="custom", version="v2"):
        if chunk["type"] == "custom":
            data = chunk["data"]
            print(f"  进度: {data.get('progress', 0)}% - {data.get('status', '')}")

    # 5. checkpoints 模式
    print("\n【5. CHECKPOINTS 模式】检查点事件")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="checkpoints", version="v2"):
        if chunk["type"] == "checkpoints":
            cp = chunk["data"]
            step = cp.get('metadata', {}).get('source', 'unknown')
            print(f"  检查点: {step}")

    # 6. tasks 模式
    print("\n【6. TASKS 模式】任务事件")
    print("-" * 40)
    for chunk in graph.stream(initial_state, config, stream_mode="tasks", version="v2"):
        if chunk["type"] == "tasks":
            task = chunk["data"]
            name = task.get('name', 'unknown')
            # 判断是开始还是结束
            if 'result' in task:
                status = "结束"
            elif 'input' in task:
                status = "开始"
            else:
                status = "unknown"
            print(f"  任务 {name}: {status}")

    # # 7. 多模式混合
    # print("\n【7. 多模式混合】UPDATES + CUSTOM")
    # print("-" * 40)
    # for chunk in graph.stream(initial_state, config, stream_mode=["updates", "custom"], version="v2"):
    #     if chunk["type"] == "updates":
    #         for node, update in chunk["data"].items():
    #             print(f"  [更新] {node}: {update}")
    #     elif chunk["type"] == "custom":
    #         print(f"  [自定义] {chunk['data']}")

    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
