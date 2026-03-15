"""
调试版本 - 显示原始工具信息结构
"""
from langchain_core.callbacks import BaseCallbackHandler
import json


class DebugToolHandler(BaseCallbackHandler):
    """调试工具信息结构"""

    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 开始调用时触发"""
        if 'invocation_params' in kwargs:
            invocation_params = kwargs['invocation_params']
            tools_info = invocation_params.get('tools')
            if tools_info:
                print("=" * 60)
                print("DEBUG: 原始工具信息结构")
                print("=" * 60)
                for i, tool in enumerate(tools_info):
                    print(f"\n[Tool {i}] 类型: {type(tool)}")
                    print(f"Keys: {list(tool.keys()) if isinstance(tool, dict) else 'N/A'}")
                    print(f"完整内容:")
                    print(json.dumps(tool, ensure_ascii=False, indent=2, default=str))
                print("=" * 60)
