# 实际执行结构
Agent
   ├── Model
   ├── Tools
   ├── Middleware
   └── Runtime
          ├── State
          ├── Context
          ├── Store
          └── StreamWriter

# 解释
Model        → 推理
Tools        → 行动
Middleware   → 控制
Runtime      → 运行环境
State        → 工作记忆
Store        → 长期记忆



# 抽象设计结构
Agent = Model + Tools + Middleware + State
State 指工作状态（working state）



# 什么图？
```mermaid
flowchart TD

User[User Request]

subgraph Client
A1[agent.stream / agent.astream]
A2[Iterator Consumer]
A3[UI Render]
end

subgraph LangGraph_Runtime
B1[Load Thread State<br>Checkpointer]
B2[Graph Execution Engine]

subgraph Middleware
M1[before_model]
M2[after_model]
end

subgraph Nodes
N1[LLM Node]
N2[Tool Node]
N3[Custom Node]
end

subgraph Streaming_System
S1[Event Generator]
S2[Streaming Bus]
end

end

User --> A1
A1 --> B1
B1 --> B2

B2 --> M1
M1 --> N1
N1 --> S1

B2 --> N2
N2 --> S1

B2 --> N3
N3 --> S1

S1 --> S2
S2 --> A2
A2 --> A3

N1 --> M2
M2 --> B2
```