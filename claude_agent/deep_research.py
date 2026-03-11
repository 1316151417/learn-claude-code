#!/usr/bin/env python3
"""
deep_research.py - 极简深度研究代理 (~60 行)

基于 Claude Agent SDK 的深度研究代理。

用法:
    python claude_agent/deep_research.py

示例:
    Research: 深入研究 Python asyncio 的工作原理
    Research: 分析 Rust 所有权系统的设计思想
    Research: 调查 WebAssembly 的应用场景
"""

import anyio
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions


async def deep_research(topic: str):
    """
    执行深度研究。

    SDK 会自动：
    - 使用 Claude Code CLI 的配置（模型、API key 等）
    - 提供完整的工具集（bash, read, web_search 等）
    - 处理多轮对话直到任务完成
    """
    system_prompt = """你是深度研究代理。

核心能力：
1. 深入分析：不满足表面答案，挖掘底层原理
2. 多源验证：从多个角度验证结论
3. 结构输出：提供清晰、有组织的分析结果

研究流程：
- 理解问题 → 分解子问题 → 搜索/验证 → 综合结论
- 使用 web_search 查找最新资料
- 使用 bash/read 分析本地代码/文档
- 提供可引用的来源和具体示例

输出格式：
## 核心结论
（简洁总结）

## 详细分析
（分点展开，附来源）

## 延伸阅读
（推荐资源）"""

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["WebSearch", "WebFetch", "Read", "Write", "Bash"],
    )

    full_prompt = f"研究主题: {topic}\n\n请进行深入研究，提供全面的分析。"

    async for message in query(prompt=full_prompt, options=options):
        # message 是一个字典，包含 type, content 等字段
        if isinstance(message, dict):
            msg_type = message.get("type", "")
            content = message.get("content", "")

            print(f"zj debug {msg_type} {content}")

            if msg_type == "text" or isinstance(content, str):
                print(content, end="", flush=True)
            elif msg_type == "tool_use":
                tool_name = content.get("name", "") if isinstance(content, dict) else ""
                tool_input = content.get("input", "") if isinstance(content, dict) else {}
                print(f"\n\n> 使用工具: {tool_name} {tool_input}\n")
            elif msg_type == "tool_result":
                print(f"  ✓ 工具执行完成")
        else:
            print(message)


def main():
    print("=" * 60)
    print("Deep Research Agent - 深度研究代理")
    print("=" * 60)
    print("\n基于 Claude Agent SDK")
    print("会自动使用 Claude Code 的配置和工具\n")
    print("示例研究主题:")
    print("  - 深入研究 Python asyncio 的事件循环实现")
    print("  - 分析 Rust 所有权系统的设计思想")
    print("  - 调查 WebAssembly 在浏览器外的应用")
    print("\nType 'exit' to quit\n")

    while True:
        try:
            topic = input("Research: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not topic or topic.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        print(f"\n🔍 正在研究: {topic}\n")
        print("-" * 60)

        try:
            anyio.run(deep_research, topic)
        except Exception as e:
            print(f"\n❌ Error: {e}")

        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
