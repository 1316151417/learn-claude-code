"""
LangGraph Time Travel 极简示例

演示 checkpointer 如何保存每步状态，以及如何回退
"""
from typing import Annotated
from typing_extensions import TypedDict
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


# ==================== 定义状态 ====================
class GameState(TypedDict):
    step: int
    history: Annotated[list[str], operator.add]


# ==================== 定义节点 ====================
def step1(state: GameState) -> dict:
    print("→ 执行 step1")
    return {"step": 1, "history": ["step1"]}


def step2(state: GameState) -> dict:
    print("→ 执行 step2")
    return {"step": 2, "history": ["step2"]}


def step3(state: GameState) -> dict:
    print("→ 执行 step3")
    return {"step": 3, "history": ["step3"]}


# ==================== 构建 Graph ====================
checkpointer = MemorySaver()

graph = (
    StateGraph(GameState)
    .add_node("step1", step1)
    .add_node("step2", step2)
    .add_node("step3", step3)
    .add_edge(START, "step1")
    .add_edge("step1", "step2")
    .add_edge("step2", "step3")
    .add_edge("step3", END)
    .compile(checkpointer=checkpointer)
)


def main():
    print("=" * 60)
    print("LangGraph Time Travel 示例")
    print("=" * 60)

    thread = "demo-thread"
    config = {"configurable": {"thread_id": thread}}

    # ========== 场景 1: 正常执行 ==========
    print("\n【场景 1】正常执行完整流程")
    print("-" * 40)

    result = graph.invoke({"step": 0, "history": []}, config)
    print(f"\n✓ 完成: history={result['history']}")

    # ========== 场景 2: 查看检查点列表 ==========
    print("\n\n【场景 2】查看所有检查点（时间线）")
    print("-" * 40)

    checkpoints = list(checkpointer.list(config))
    print(f"共有 {len(checkpoints)} 个检查点:")
    for i, cp in enumerate(checkpoints):
        state = cp.checkpoint.get("channel_values", {})
        step = state.get("step", "?") if state else "?"
        history = state.get("history", []) if state else []
        history_str = ",".join(history) if history else ""
        print(f"  [{i}] step={step} | history=[{history_str}]")

    # ========== 场景 3: 回到中间某个检查点 ==========
    print("\n\n【场景 3】回到 step2 之后的检查点")
    print("-" * 40)

    # 找到 step=2 的检查点
    target_cp = None
    for cp in checkpoints:
        state = cp.checkpoint.get("channel_values", {})
        if state.get("step") == 2:
            target_cp = cp
            break

    if target_cp:
        cp_id = target_cp.config.get("configurable", {}).get("checkpoint_id")
        state_at_cp = target_cp.checkpoint.get("channel_values", {})

        print(f"找到检查点: step={state_at_cp.get('step')}, history={state_at_cp.get('history')}")
        print(f"checkpoint_id: {cp_id}")

        # 从该检查点重新执行（模拟"读档"）
        rewind_config = {
            "configurable": {
                "thread_id": thread,
                "checkpoint_id": cp_id
            }
        }

        print("\n从该检查点继续执行...")
        result2 = graph.invoke(None, config=rewind_config)
        print(f"✓ 新结果: history={result2['history']}")
        print(f"\n💡 注意：历史记录累加了！")

    # ========== 场景 4: 查看新的时间线 ==========
    print("\n\n【场景 4】查看扩展后的时间线")
    print("-" * 40)

    new_checkpoints = list(checkpointer.list(config))
    print(f"现在有 {len(new_checkpoints)} 个检查点:")
    for i, cp in enumerate(new_checkpoints):
        state = cp.checkpoint.get("channel_values", {})
        step = state.get("step", "?") if state else "?"
        history = state.get("history", []) if state else []
        history_str = ",".join(history) if history else ""
        # 只显示一部分，避免太长
        if len(history_str) > 20:
            history_str = history_str[:17] + "..."
        print(f"  [{i}] step={step} | history=[{history_str}]")

    print("\n" + "=" * 60)
    print("💡 核心概念:")
    print("  - checkpointer 在每步后自动保存状态")
    print("  - 每个 checkpoint_id 是一个'存档点'")
    print("  - 可以回到任意存档点继续")
    print("  - 历史状态会累加（不是覆盖）")
    print("  - 类似游戏的'读档'功能")
    print("=" * 60)


if __name__ == "__main__":
    main()
