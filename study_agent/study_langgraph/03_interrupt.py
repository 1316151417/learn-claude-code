"""
LangGraph Interrupt 极简示例

演示人工介入(Human-in-the-Loop)模式
"""
from typing import Literal
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt


# ==================== 定义状态 ====================
@dataclass
class ApprovalState:
    action: str = ""        # 要执行的动作
    status: str = "pending"  # pending | approved | rejected
    reason: str = ""        # 拒绝原因


# ==================== 定义节点 ====================
def approval_node(state: ApprovalState) -> Command[Literal["execute", "cancel"]]:
    """审批节点：等待人工批准或拒绝"""
    decision = interrupt({
        "question": f"是否批准执行: {state.action}?",
        "action": state.action,
        "instructions": "回复 True 批准，False 拒绝"
    })

    # 根据人工决策路由到不同节点
    if decision:
        return Command(goto="execute")
    else:
        return Command(goto="cancel")


def execute_node(state: ApprovalState):
    """执行动作"""
    print(f"✅ 动作已执行: {state.action}")
    return {"status": "approved"}


def cancel_node(state: ApprovalState):
    """取消动作"""
    print(f"❌ 动作已取消: {state.action}")
    return {"status": "rejected"}


# ==================== 构建 Graph ====================
checkpointer = MemorySaver()

graph = (
    StateGraph(ApprovalState)
    .add_node("approval", approval_node)
    .add_node("execute", execute_node)
    .add_node("cancel", cancel_node)
    .add_edge(START, "approval")
    .add_edge("execute", END)
    .add_edge("cancel", END)
    .compile(checkpointer=checkpointer)
)


# ==================== 演示 ====================
def main():
    thread_id = "demo-thread-1"
    config = {"configurable": {"thread_id": thread_id}}

    # 步骤 1: 首次运行 - 触发 interrupt
    print("\n【步骤 1】提交动作，等待审批...")
    result = graph.invoke(
        {"action": "发送 500 元给用户", "status": "pending"},
        config=config,
        version="v2"
    )

    # 检查是否被中断
    if result.interrupts:
        print(f"\n⏸️  Graph 已暂停")
        print(f"等待审批: {result.interrupts[0].value}")

    # 步骤 2: 恢复 - 批准 (True)
    print("\n【步骤 2】用户批准 (True)")
    result = graph.invoke(
        Command(resume=True),
        config=config,
        version="v2"
    )
    print(f"最终状态: status={result.value.status}")

    print("\n" + "=" * 60)

    # ============== 第二次演示：拒绝 ==============
    thread_id_2 = "demo-thread-2"
    config_2 = {"configurable": {"thread_id": thread_id_2}}

    print("\n【步骤 1】提交动作，等待审批...")
    result = graph.invoke(
        {"action": "删除数据库表", "status": "pending"},
        config=config_2,
        version="v2"
    )

    if result.interrupts:
        print(f"\n⏸️  Graph 已暂停")
        print(f"等待审批: {result.interrupts[0].value}")

    print("\n【步骤 2】用户拒绝 (False)")
    result = graph.invoke(
        Command(resume=False),
        config=config_2,
        version="v2"
    )
    print(f"最终状态: status={result.value.status}")

if __name__ == "__main__":
    main()
