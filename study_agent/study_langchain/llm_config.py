"""
LLM 配置模块 - 统一管理 LLM 初始化
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

# 加载环境变量
load_dotenv()

# 获取 API 配置
zhipu_api_base = os.getenv("ZHIPU_BASE_URL")
zhipu_api_key = os.getenv("ZHIPU_API_KEY")
zhipu_model = os.getenv("ZHIPU_MODEL_ID")

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

def get_zhipu_llm(**kwargs) -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_base=zhipu_api_base,
        openai_api_key=zhipu_api_key,
        model=zhipu_model,
        **kwargs
    )

def get_deepseek_llm(**kwargs) -> ChatDeepSeek:
    return ChatDeepSeek(
        model="deepseek-chat"
    )

def get_default_llm():
    return get_deepseek_llm()