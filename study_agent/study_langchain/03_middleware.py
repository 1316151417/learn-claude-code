import json
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from trace_handler import LLMTraceHandler
from llm_config import get_default_llm, get_deepseek_llm, get_zhipu_llm
from langchain.agents.middleware import HumanInTheLoopMiddleware

trace_handler = LLMTraceHandler()

llm = get_zhipu_llm()

checkpointer = InMemorySaver()

@dataclass
class Context:
    """自定义上下文结构"""
    user_name: str

@dataclass
class ResponseFormat:
    """智能体的返回结构"""
    punny_response: str
    weather_conditions: str | None = None

@tool
def get_user_city(runtime: ToolRuntime[Context]):
    """获取用户所在城市"""
    user_name = runtime.context.user_name
    city = "北京市" if user_name == "周杰" else "四川市"
    return {"city": city}

@tool
def get_weather_for_city(city: str) -> str:
    """获取城市的天气"""
    return f"{city} 总是阳光明媚!"

SYSTEM_PROMPT = """
角色：你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。

工具使用流程：
1. 先调用 get_user_city() 获取用户城市，返回 {"city": "城市名"}
2. 从用户城市结果中提取 city 值，调用 get_weather_for_city(city=提取的城市)

示例对话：
用户：天气怎么样？
1. get_user_city → {"city": "四川市"}
2. get_weather_for_city(city="四川市") → "四川市 总是阳光明媚!"

始终严格按顺序调用工具，并正确传递参数。
"""

config = {
    "configurable": {"thread_id": "1"},
    "callbacks": [trace_handler]
}

agent = create_agent(
    llm,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_city, get_weather_for_city],
    context_schema=Context,
    checkpointer=checkpointer,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "get_weather_for_city": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
                "get_user_city": False
            }
        )
    ]
)

response = agent.invoke(
    {"messages": [HumanMessage(content="天气怎么样？")]},
    config=config,
    context=Context(user_name="杨苗"),
    version="v2"
)

## TODO 待完善代码
if response.interrupts:
    # 获取中断信息
    interrupt_value = response.interrupts[0].value
    action_request = interrupt_value['action_requests'][0]
    tool_name = action_request['name']
    tool_args = action_request['args']

    # 显示中断信息
    print(f"\n智能体请求执行工具: {tool_name}")
    print(f"工具参数: {json.dumps(tool_args, ensure_ascii=False)}")

    # 获取用户输入
    user_input = input("\n请选择操作 (approve/edit/reject): ").strip().lower()

    if user_input == "approve":
        # 批准：继续执行工具调用
        print("\n✓ 已批准，继续执行...")
        response = agent.invoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config=config,
            version="v2"
        )

    elif user_input == "edit":
        # 编辑：修改工具参数后执行
        print("\n请输入新的工具参数 (JSON格式):")
        try:
            input_str = input("新参数: ").strip()
            # 尝试标准解析
            try:
                new_args = json.loads(input_str)
            except json.JSONDecodeError:
                # 如果失败，尝试修复常见问题（如中文引号）
                input_str = input_str.replace("'", '"').replace('"', '"').replace('"', '"')
                new_args = json.loads(input_str)

            print(f"\n✓ 已更新参数为: {json.dumps(new_args, ensure_ascii=False)}，继续执行...")
            # 注意：edit 类型需要传入 edited_action，包含 name 和 args
            response = agent.invoke(
                Command(resume={
                    "decisions": [{
                        "type": "edit",
                        "edited_action": {
                            "name": tool_name,
                            "args": new_args
                        }
                    }]
                }),
                config=config,
                version="v2"
            )
        except json.JSONDecodeError as e:
            print(f"✗ JSON格式错误: {e}")
            print(f"  请确保格式正确，例如: {{\"city\": \"北京市\"}}")
        except Exception as e:
            print(f"✗ 处理编辑时出错: {e}")

    elif user_input == "reject":
        # 拒绝：取消工具调用
        print("\n✗ 已拒绝工具调用")
        response = agent.invoke(
            Command(resume={"decisions": [{"type": "reject"}]}),
            config=config,
            version="v2"
        )

    else:
        print(f"\n✗ 未知操作: {user_input}")

# 输出最终结果
print("\n=== 最终回复 ===")
print(f"[DEBUG] response类型: {type(response)}")
print(f"[DEBUG] response内容: {response}")
print(f"[DEBUG] dir: {[x for x in dir(response) if not x.startswith('_')]}")