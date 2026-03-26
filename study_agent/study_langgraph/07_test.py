"""
LangGraph Testing 极简 Demo
基于: https://docs.langchain.com/oss/python/langgraph/test

覆盖三种测试模式:
1. 基本执行测试 - 完整流程
2. 单节点测试 - 测试单个节点
3. 部分执行测试 - 只执行中间某段节点

运行方式
uv run pytest study_agent/study_langgraph/07_test.py -v
"""

import pytest
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


# ============ 图定义（共享） ============

def create_graph() -> StateGraph:
    class MyState(TypedDict):
        my_key: str

    graph = StateGraph(MyState)
    graph.add_node("node1", lambda state: {"my_key": "hello from node1"})
    graph.add_node("node2", lambda state: {"my_key": "hello from node2"})
    graph.add_node("node3", lambda state: {"my_key": "hello from node3"})
    graph.add_node("node4", lambda state: {"my_key": "hello from node4"})

    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", "node3")
    graph.add_edge("node3", "node4")
    graph.add_edge("node4", END)

    return graph


# ============ 测试 1: 基本执行 ============

def test_basic_execution() -> None:
    """测试完整图执行，验证最终状态"""
    checkpointer = MemorySaver()
    compiled = create_graph().compile(checkpointer=checkpointer)

    result = compiled.invoke(
        {"my_key": "initial"},
        config={"configurable": {"thread_id": "test-1"}},
    )

    assert result["my_key"] == "hello from node4"


# ============ 测试 2: 单节点执行 ============

def test_single_node() -> None:
    """只执行 node2，跳过其他节点"""
    checkpointer = MemorySaver()
    compiled = create_graph().compile(checkpointer=checkpointer)

    # 通过 graph.nodes["node_name"] 直接调用单个节点
    result = compiled.nodes["node2"].invoke({"my_key": "initial"})

    assert result["my_key"] == "hello from node2"


# ============ 测试 3: 部分执行（只跑 node2 → node3） ============

def test_partial_execution() -> None:
    """只执行 node2 -> node3，跳过 node1 和 node4"""
    checkpointer = MemorySaver()
    compiled = create_graph().compile(checkpointer=checkpointer)

    # 1) 模拟 node1 已执行完毕的状态
    compiled.update_state(
        config={"configurable": {"thread_id": "test-3"}},
        values={"my_key": "initial"},
        as_node="node1",  # 假装从 node1 出来，下一跳从 node2 开始
    )

    # 2) 从 node2 恢复执行，在 node3 后中断
    result = compiled.invoke(
        None,
        config={"configurable": {"thread_id": "test-3"}},
        interrupt_after="node3",
    )

    assert result["my_key"] == "hello from node3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
