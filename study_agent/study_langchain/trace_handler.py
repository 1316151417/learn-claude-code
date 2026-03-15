"""
LLM Trace Handler - 用于追踪 LLM 和 Tool 调用的回调处理器

简化输出，每个操作只占一行，方便观测。
"""
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage


class LLMTraceHandler(BaseCallbackHandler):
    """追踪 LLM 和 Tool 调用过程的回调处理器"""

    def __init__(self, multiline: bool = False, show_tools: bool = False, max_length: int = 100):
        """
        初始化追踪器

        Args:
            multiline: 是否多行显示详细输出（默认 False，简洁模式）
            show_tools: 是否显示工具 schema（默认 False）
            max_length: 文本最大显示长度（默认 100）
        """
        super().__init__()
        self.multiline = multiline
        self.show_tools = show_tools
        self.max_length = max_length
        self._tool_depth = 0

    def _format_args(self, args: dict) -> str:
        """格式化参数显示"""
        if not args:
            return ""
        if self.multiline:
            import json
            return json.dumps(args, ensure_ascii=False, indent=2)
        # 简洁模式：只显示关键信息
        items = []
        for k, v in list(args.items())[:3]:
            if isinstance(v, str):
                v = repr(v[:30] + "..." if len(v) > 30 else v)
            items.append(f"{k}={v}")
        if len(args) > 3:
            items.append("...")
        return "(" + ", ".join(items) + ")"

    def _truncate(self, text: str) -> str:
        """截断文本"""
        text = text.strip().replace("\n", " ")
        if len(text) > self.max_length:
            return text[:self.max_length - 3] + "..."
        return text

    def _extract_tool_output(self, output) -> str:
        """提取工具的实际返回值"""
        # 如果是 ToolMessage 对象，提取 content
        if isinstance(output, ToolMessage):
            return output.content
        # 如果是 dict，尝试提取 content 或直接转为字符串
        if isinstance(output, dict):
            if 'content' in output:
                return str(output['content'])
            return str(output)
        # 如果是字符串，直接返回
        if isinstance(output, str):
            return output
        # 其他情况转为字符串
        return str(output)

    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 开始调用时触发"""
        if self.multiline:
            print("┌─ LLM Start ──────────────────────────────────")
            for p in prompts:
                for line in p.split("\n"):
                    if line.strip():
                        print(f"│ {line}")
            print("└───────────────────────────────────────────────")

    def on_llm_end(self, response, **kwargs):
        """LLM 调用结束时触发"""
        gen = response.generations[0][0]
        msg = gen.message

        # LLM 文本响应
        if msg.content:
            text = self._truncate(msg.content)
            print(f"└─ {text}")

        # Tool 调用
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for t in tool_calls:
                name = t.get("name", "")
                args = t.get("args", {})
                args_str = self._format_args(args)

                # 判断是否是特殊工具
                is_special = name and name[0].isupper() and name not in ["get_user_city", "get_weather_for_city"]

                if is_special:
                    print(f"✦─ {name}{args_str}")
                else:
                    print(f"→─ {name}{args_str}")
                    self._tool_depth += 1

    def on_tool_start(self, serialized, input_str, **kwargs):
        """Tool 开始执行时触发"""
        pass  # 简洁模式不显示工具开始

    def on_tool_end(self, output, **kwargs):
        """Tool 执行结束时触发"""
        actual_output = self._extract_tool_output(output)
        output_str = self._truncate(actual_output)
        print(f"   └─ → {output_str}")
