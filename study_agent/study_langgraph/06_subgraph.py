"""
LangGraph Subgraph 极简示例

演示如何将一个 graph 作为 node 嵌入到另一个 graph 中
"""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END


# ==================== 方式1：共享状态 - 直接添加子图 ====================
print("=" * 60)
print("方式 1: 共享状态模式（子图作为节点）")
print("=" * 60)

# 定义共享状态（父图和子图使用相同的键）
class SharedState(TypedDict):
    """共享状态：父图和子图有相同的键"""
    text: str


# --- 子图 ---
def sub_step1(state: SharedState):
    """子图步骤1：添加前缀"""
    return {"text": f"[前缀] {state['text']}"}


def sub_step2(state: SharedState):
    """子图步骤2：添加后缀"""
    return {"text": f"{state['text']} [后缀]"}


# 构建子图
subgraph = (
    StateGraph(SharedState)
    .add_node("sub1", sub_step1)
    .add_node("sub2", sub_step2)
    .add_edge(START, "sub1")
    .add_edge("sub1", "sub2")
    .add_edge("sub2", END)
).compile()


# --- 父图 ---
def parent_node1(state: SharedState):
    """父图节点1：准备输入"""
    return {"text": f"处理: {state['text']}"}


def parent_node2(state: SharedState):
    """父图节点2：完成处理"""
    return {"text": f"完成: {state['text']}"}


# 父图直接把子图作为一个节点（共享状态）
shared_graph = (
    StateGraph(SharedState)
    .add_node("node1", parent_node1)
    .add_node("subgraph", subgraph)  # 直接添加编译后的子图
    .add_node("node2", parent_node2)
    .add_edge(START, "node1")
    .add_edge("node1", "subgraph")
    .add_edge("subgraph", "node2")
    .add_edge("node2", END)
).compile()

# 运行共享状态模式
print("\n【运行】共享状态模式:")
print("  输入: Hello")
print("  流程: node1 → 子图(sub1→sub2) → node2")
result = shared_graph.invoke({"text": "Hello"})
print(f"  输出: {result['text']}")


# ==================== 方式2：不同状态 - 在节点中调用子图 ====================
print("\n\n" + "=" * 60)
print("方式 2: 不同状态模式（在节点中调用）")
print("=" * 60)


# --- 子图（不同的状态） ---
class SubgraphState(TypedDict):
    """子图状态 - 与父图状态完全不同"""
    input_text: str
    processed: str


def sub_transform1(state: SubgraphState):
    """子图转换1"""
    return {"processed": f"转换: {state['input_text']}"}


def sub_transform2(state: SubgraphState):
    """子图转换2"""
    return {"processed": f"{state['processed']} ✓"}


# 构建子图
transform_subgraph = (
    StateGraph(SubgraphState)
    .add_node("trans1", sub_transform1)
    .add_node("trans2", sub_transform2)
    .add_edge(START, "trans1")
    .add_edge("trans1", "trans2")
    .add_edge("trans2", END)
).compile()


# --- 父图（不同的状态） ---
class ParentState(TypedDict):
    """父图状态 - 与子图状态完全不同"""
    foo: str


def call_subgraph(state: ParentState):
    """在节点内调用子图，需要转换状态"""
    # 转换父图状态 -> 子图状态
    subgraph_input = {"input_text": state['foo'], "processed": ""}

    # 调用子图
    subgraph_output = transform_subgraph.invoke(subgraph_input)

    # 转换子图输出 -> 父图状态
    return {"foo": subgraph_output['processed']}


wrapper_graph = (
    StateGraph(ParentState)
    .add_node("wrapper", call_subgraph)
    .add_edge(START, "wrapper")
    .add_edge("wrapper", END)
).compile()

# 运行包装模式
print("\n【运行】不同状态模式:")
print("  输入: foo=World")
print("  流程: wrapper(内部调用子图 trans1→trans2)")
result = wrapper_graph.invoke({"foo": "World"})
print(f"  输出: {result['foo']}")


# ==================== 流式输出（查看子图内部）====================
print("\n\n" + "=" * 60)
print("流式输出：查看子图内部执行")
print("=" * 60)

print("\n【流式运行】共享状态模式:")
print("  使用 stream_mode='updates' + subgraphs=True 查看子图内部")
print("-" * 40)

# 使用 v2 格式
for chunk in shared_graph.stream(
    {"text": "Stream"},
    stream_mode="updates",
    subgraphs=True,     # 包含子图的事件
    version="v2",
):
    if chunk["type"] == "updates":
        # ns 是命名空间：() 表示父图，('subgraph:xxx',) 表示子图
        ns = chunk["ns"]
        data = chunk["data"]

        if ns == ():
            # 父图节点
            for node, updates in data.items():
                print(f"[父图] {node}: {updates}")
        else:
            # 子图节点 - ns 是元组，如 ('subgraph:task_id',)
            for node, updates in data.items():
                print(f"  [子图] {node}: {updates}")

print("\n" + "=" * 60)
print("💡 核心概念:")
print("  - 子图是一个完整的 graph，可以作为节点嵌入到父图中")
print("  - 两种使用方式:")
print("    1. 共享状态: 父图和子图有相同的状态键，直接 add_node(subgraph)")
print("    2. 不同状态: 在节点函数中调用子图，需要转换状态")
print("  - subgraphs=True 可以查看子图内部的执行细节")
print("=" * 60)
