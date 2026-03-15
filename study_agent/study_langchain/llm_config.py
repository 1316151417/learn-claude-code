"""
LLM 配置模块 - 统一管理 LLM 初始化
"""
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# 加载环境变量
load_dotenv()

# 获取 API 配置
zhipu_api_base = os.getenv("ZHIPU_BASE_URL")
zhipu_api_key = os.getenv("ZHIPU_API_KEY")
zhipu_model = os.getenv("ZHIPU_MODEL")

deepseek_api_base = os.getenv("DEEPSEEK_BASE_URL")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepseek_model = os.getenv("DEEPSEEK_MODEL")

default_model = os.getenv("MODEL")

def get_default_llm(**kwargs):
    print(f"初始化默认模型(model={default_model})...")
    return init_chat_model(
        model=default_model,
        **kwargs
    )

def get_deepseek_llm(**kwargs):
    print(f"初始化DeepSeek模型(base_url:{deepseek_api_base}, model={deepseek_api_key})")
    return init_chat_model(
        base_url=deepseek_api_base,
        api_key=deepseek_api_key,
        model=deepseek_model,
        **kwargs
    )

def get_zhipu_llm(**kwargs):
    print(f"初始化智谱模型(base_url:{zhipu_api_base}, model={zhipu_model})")
    return init_chat_model(
        model_provider="openai",
        base_url=zhipu_api_base,
        api_key=zhipu_api_key,
        model=zhipu_model,
        **kwargs
    )