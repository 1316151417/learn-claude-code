"""
LangGraph Agent Chat UI 极简 Demo
基于: https://docs.langchain.com/oss/python/langgraph/ui

Agent Chat UI 是一个 Next.js 聊天界面，用于与 LangGraph agent 交互。
本 demo 展示如何编写一个兼容 Agent Chat UI 的 agent，并通过 langgraph dev 启动。

运行方式:
  1. uv add "langgraph-cli[inmem]"
  2. uv run langgraph dev --port 2024
  3. 打开 https://chat.langchain.com，填入:
     - Deployment URL: http://localhost:2024
     - Graph ID: chatbot
  4. 访问：https://agentchat.vercel.app/
"""

from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage
from common.llm_config import get_default_llm
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


# ============ State 定义 ============

class State(TypedDict):
    """消息列表状态，使用 add_messages 实现消息追加"""
    messages: Annotated[list, add_messages]


# ============ 节点定义 ============

model = get_default_llm()


def chatbot(state: State) -> dict:
    """调用 LLM 生成回复"""
    response = model.invoke(state["messages"])
    return {"messages": [response]}


# ============ 构建图 ============

graph = StateGraph(State)
graph.add_node("chatbot", chatbot)
graph.add_edge(START, "chatbot")
graph.add_edge("chatbot", END)

# 编译为可运行的图
app = graph.compile()


# ============ 本地调试（不依赖 UI 时使用） ============

if __name__ == "__main__":
    result = app.invoke({
        "messages": [HumanMessage(content="你好，介绍一下你自己")],
    })
    for msg in result["messages"]:
        print(f"{msg.type}: {msg.content}")
