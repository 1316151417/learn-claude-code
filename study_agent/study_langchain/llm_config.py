"""
LLM 配置模块 - 统一管理 LLM 初始化
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()

# 获取 API 配置
api_base = os.getenv("ZHIPU_BASE_URL")
api_key = os.getenv("ZHIPU_API_KEY")


def create_llm(model: str = "glm-4.7", **kwargs) -> ChatOpenAI:
    """
    创建 LLM 实例

    Args:
        model: 模型名称，默认为 glm-4.7
        **kwargs: 其他 ChatOpenAI 参数

    Returns:
        ChatOpenAI 实例
    """
    return ChatOpenAI(
        openai_api_base=api_base,
        openai_api_key=api_key,
        model=model,
        **kwargs
    )


# 默认 LLM 实例
def get_default_llm() -> ChatOpenAI:
    """获取默认配置的 LLM 实例"""
    return create_llm(model="glm-4.7")
