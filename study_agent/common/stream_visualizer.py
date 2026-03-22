"""
Agent Stream Visualizer - 简洁版

参考 trace_handler.py 风格，直观显示 Agent 流式输出
"""
from typing import Any


class StreamVisualizer:
    """Agent 流式输出可视化器"""

    def __init__(self):
        self._prev_block_type = None
        self._label_printed = False
        self._first_text = True
        self._last_was_tool_result = False

    def visualize_chunk(self, chunk: dict[str, Any]):
        """可视化单个流式数据块"""
        chunk_type = chunk.get("type", "")

        if chunk_type == "updates":
            self._show_updates(chunk)
        elif chunk_type == "messages":
            self._show_messages(chunk)
        elif chunk_type == "custom":
            self._show_custom(chunk)

    def _show_updates(self, chunk: dict[str, Any]):
        """显示 Agent 步骤更新"""
        data = chunk.get("data", {})

        for step_data in data.values():
            messages = step_data.get("messages", [])
            if not messages:
                continue

            for msg in messages:
                content_blocks = getattr(msg, "content_blocks", None)

                # 检查消息类型
                msg_type = getattr(msg, "type", "")

                if msg_type == "tool":
                    content = getattr(msg, "content", "")
                    name = getattr(msg, "name", "")
                    print(f"ToolResult: [{name}] {self._truncate(str(content), 80)}")
                    continue

                if content_blocks:
                    for block in content_blocks:
                        block_type = block.get("type", "")

                        if block_type == "text":
                            text = block.get("text", "")
                            print(f"LLM: {self._truncate(text, 100)}")

                        elif block_type == "tool-use":
                            name = block.get("name", "")
                            args = block.get("input", {})
                            print(f"Tool: {name}{self._format_args(args)}")

                        elif block_type == "tool-result":
                            content = block.get("content", "")
                            print(f"ToolResult: {self._truncate(str(content), 80)}")

    def _show_messages(self, chunk: dict[str, Any]):
        """显示 LLM Token 输出"""
        data = chunk.get("data")
        if not data or not isinstance(data, (tuple, list)) or len(data) < 2:
            return
        token, _metadata = data
        if token is None:
            return

        # 先检查 token 类型（优先于 content_blocks）
        token_type = getattr(token, "type", "")
        content = getattr(token, "content", "")

        # 工具结果直接处理
        if token_type == "tool":
            if not self._first_text:
                print()
            print(f"ToolResult: {content}", flush=True)
            self._label_printed = False  # 重置，让后续文本能打印标签
            self._first_text = False
            self._last_was_tool_result = True  # 标记刚输出过 ToolResult
            return

        content_blocks = getattr(token, "content_blocks", None)
        if content_blocks:
            for block in content_blocks:
                block_type = block.get("type", "")

                # 块类型变化时处理
                if self._prev_block_type and self._prev_block_type != block_type:
                    self._label_printed = False

                if block_type == "text":
                    text = block.get("text", "")
                    if text:  # 有内容才处理
                        if not self._label_printed:
                            # 如果刚输出过 ToolResult，不再换行
                            if not self._first_text and not self._last_was_tool_result:
                                print()
                            print("LLM: ", end="", flush=True)
                            self._label_printed = True
                            self._first_text = False
                            self._last_was_tool_result = False  # 重置标记
                        print(text, end="", flush=True)

                elif block_type == "tool-use":
                    name = block.get("name", "")
                    args = block.get("input", {})
                    if not self._label_printed:
                        print()
                        self._first_text = False
                    print(f"Tool: {name}{self._format_args(args)}", flush=True)
                    self._label_printed = True

                elif block_type == "tool-result":
                    result_content = block.get("content", "")
                    if not self._label_printed:
                        print()
                        self._first_text = False
                    print(f"ToolResult: {self._truncate(str(result_content), 60)}", flush=True)
                    self._label_printed = True

                self._prev_block_type = block_type

    def _show_custom(self, chunk: dict[str, Any]):
        """显示自定义消息"""
        data = chunk.get("data")
        print(f"Custom: {data}")

    def _format_args(self, args: dict) -> str:
        """格式化参数显示"""
        if not args:
            return "()"
        items = []
        for k, v in list(args.items())[:3]:
            if isinstance(v, str):
                v = repr(v[:25] + "..." if len(v) > 25 else v)
            items.append(f"{k}={v}")
        if len(args) > 3:
            items.append("...")
        return "(" + ", ".join(items) + ")"

    def _truncate(self, text: str, max_length: int = 100) -> str:
        """截断文本"""
        text = str(text).strip().replace("\n", " ")
        if len(text) > max_length:
            return text[:max_length - 3] + "..."
        return text


def visualize_stream(agent, input_data: dict, **stream_kwargs):
    """
    流式执行 Agent 并可视化输出

    Args:
        agent: LangGraph Agent 实例
        input_data: 输入数据
        **stream_kwargs: 传递给 agent.stream() 的额外参数
    """
    viz = StreamVisualizer()
    stream_kwargs.setdefault("stream_mode", ["updates", "messages", "custom"])
    stream_kwargs.setdefault("version", "v2")

    for chunk in agent.stream(input_data, **stream_kwargs):
        viz.visualize_chunk(chunk)
