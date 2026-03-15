"""
LLM Trace Handler - 用于追踪 LLM 和 Tool 调用的回调处理器
"""
from langchain_core.callbacks import BaseCallbackHandler


class LLMTraceHandler(BaseCallbackHandler):
    """追踪 LLM 和 Tool 调用过程的回调处理器"""

    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 开始调用时触发"""
        print("==========llm start==========")
        for p in prompts:
            for line in p.split("\n"):
                print(line)

    def on_llm_end(self, response, **kwargs):
        """LLM 调用结束时触发"""
        print("==========llm end==========")
        gen = response.generations[0][0]
        msg = gen.message
        # LLM文本响应
        if msg.content:
            print(f"LLM  → {msg.content}")
        # Tool调用信息
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for t in tool_calls:
                name = t.get("name")
                args = t.get("args")
                print(f"    LLM  → {name}({args})")

    def on_tool_start(self, serialized, input_str, **kwargs):
        """Tool 开始执行时触发"""
        print("==========tool exc==========")
        name = serialized.get("name", "tool")
        print(f"Tool → {name}({input_str})")

    def on_tool_end(self, output, **kwargs):
        """Tool 执行结束时触发"""
        print(f"    Tool → {output}")
