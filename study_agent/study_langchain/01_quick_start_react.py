import os
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

load_dotenv()

api_base = os.getenv("ZHIPU_BASE_URL")
api_key = os.getenv("ZHIPU_API_KEY")

llm = ChatOpenAI(
    openai_api_base=api_base,
    openai_api_key=api_key,
    model="glm-4.7",
)

@dataclass
class Context:
    user_name: str

context = Context(user_name="杨苗")

# ------------------ tools ------------------

def get_user_city():
    city = "北京市" if context.user_name == "周杰" else "四川市"
    return {"city": city}

def get_weather_for_city(city: str):
    return f"{city} 总是阳光明媚!"

llm = llm.bind_tools([
    get_user_city,
    get_weather_for_city
])

# ------------------ prompt ------------------

SYSTEM_PROMPT = """
你是一位资深天气预报专家，说话时喜欢使用双关语。

工具：
1. get_user_city()
2. get_weather_for_city(city)

流程：
先调用 get_user_city
再调用 get_weather_for_city
"""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    HumanMessage(content="天气怎么样？")
]

# ------------------ REACT LOOP ------------------

for step in range(5):

    response = llm.invoke(messages)

    print("\n===== LLM RAW OUTPUT =====")
    print(response)

    messages.append(response)

    tool_calls = getattr(response, "tool_calls", None)

    if not tool_calls:
        break

    for call in tool_calls:

        name = call["name"]
        args = call.get("args", {})

        print(f"\n>>> TOOL CALL: {name} {args}")

        if name == "get_user_city":
            result = get_user_city()

        elif name == "get_weather_for_city":
            result = get_weather_for_city(**args)

        else:
            result = "unknown tool"

        print(f">>> TOOL RESULT: {result}")

        messages.append(
            ToolMessage(
                tool_call_id=call["id"],
                name=name,
                content=str(result)
            )
        )

# ------------------ 打印最终 messages ------------------

print("\n\n===== FINAL TRACE =====")

for m in messages:
    print(type(m).__name__, getattr(m, "content", None))