"""
LangGraph Functional API 极简示例

与 Graph API 不同，Functional API 用标准 Python 控制流（if/for）定义工作流，
无需构建 State / Node / Edge。

核心概念:
  @task       — 封装离散工作单元（如 API 调用），结果可被 checkpoint 持久化
  @entrypoint — 工作流入口，管理执行流、中断恢复、短期记忆
  interrupt   — 暂停工作流等待人工输入（Human-in-the-Loop）
  Command(resume=...) — 恢复被中断的工作流
"""
import time
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt, Command


# ==================== 定义 Task ====================
@task
def generate_topic_essay(topic: str) -> str:
    """模拟一个耗时操作：生成一篇关于指定主题的短文"""
    time.sleep(0.5)
    return f"这是一篇关于「{topic}」的短文。{topic}是非常有趣的话题，值得深入探讨。"


# ==================== 定义 Entrypoint ====================
checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def essay_workflow(topic: str) -> dict:
    """
    工作流：生成短文 → 人工审批 → 返回结果

    与 Graph API 的区别：
    - 不需要定义 State / Node / Edge
    - 直接用 Python 函数 + 标准控制流
    - interrupt 暂停，Command(resume=...) 恢复
    """
    # 1. 调用 task 生成短文（结果会被 checkpoint 缓存，恢复时不重算）
    essay = generate_topic_essay(topic).result()

    # 2. 暂停等待人工审批
    is_approved = interrupt({
        "essay": essay,
        "action": "请审批：回复 True 批准，False 拒绝",
    })

    # 3. 返回最终结果
    return {
        "essay": essay,
        "is_approved": is_approved,
    }


# ==================== 演示 ====================
def main():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # ---- 步骤 1: 首次运行，生成短文并中断 ----
    print("\n【步骤 1】生成短文，等待审批...")
    for chunk in essay_workflow.stream("人工智能", config):
        print(chunk)

    print("\n⏸️  工作流已暂停，等待人工审批\n")

    # ---- 步骤 2: 人工批准，恢复工作流 ----
    print("【步骤 2】用户批准 (True)")
    for chunk in essay_workflow.stream(Command(resume=True), config):
        print(chunk)

    print("\n" + "=" * 60)

    # ---- 演示短期记忆（previous 参数） ----
    print("\n【演示】短期记忆 —— 累加求和")
    print("每次调用都能访问上一次的返回值（previous）\n")

    @entrypoint(checkpointer=InMemorySaver())
    def accumulator(number: int, *, previous: int = None) -> int:
        """每次调用累加 previous"""
        previous = previous or 0
        return number + previous

    acc_config = {"configurable": {"thread_id": "acc-demo"}}

    r1 = accumulator.invoke(1, acc_config)
    print(f"  invoke(1) → {r1}")   # 1

    r2 = accumulator.invoke(2, acc_config)
    print(f"  invoke(2) → {r2}")   # 3 (previous=1)

    r3 = accumulator.invoke(10, acc_config)
    print(f"  invoke(10) → {r3}")  # 13 (previous=3)

    print(f"\n  累加链: 1 → 3 → 13")


if __name__ == "__main__":
    main()
