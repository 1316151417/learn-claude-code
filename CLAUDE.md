# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Learn Claude Code** - an educational repository from shareAI Lab that teaches how modern AI agents work by progressively building them from scratch. The project demonstrates the core patterns behind AI coding agents like Claude Code and Kode.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### Running Agents
```bash
python v0_bash_agent.py      # Minimal (50 lines): 1 tool, recursive subagents
python v1_basic_agent.py     # Core loop (200 lines): 4 tools
python v2_todo_agent.py      # + Todo planning (300 lines)
python v3_subagent.py        # + Subagents (450 lines)
python v4_skills_agent.py    # + Skills (550 lines)
```

### Testing
```bash
# Unit tests (no API calls required)
python tests/test_unit.py

# Integration tests (requires TEST_API_KEY, TEST_BASE_URL, TEST_MODEL env vars)
python tests/test_agent.py
```

### Creating New Agents
```bash
# Scaffold a new agent project using the agent-builder skill
python skills/agent-builder/scripts/init_agent.py my-agent

# Specify complexity level
python skills/agent-builder/scripts/init_agent.py my-agent --level 0  # Minimal
python skills/agent-builder/scripts/init_agent.py my-agent --level 1  # 4 tools
```

## Architecture Overview

### The Agent Loop Pattern

Every AI coding agent in this repository follows this fundamental pattern:

```python
while True:
    response = model(messages, tools)
    if response.stop_reason != "tool_use":
        return response.text
    results = execute(response.tool_calls)
    messages.append(results)
```

### Progressive Version Evolution

The project evolves through 5 versions, each building on the previous:

| Version | Lines | Tools | Core Addition | Key Insight |
|---------|-------|-------|---------------|-------------|
| v0 | ~50 | bash | Recursive subagents | One tool is enough |
| v1 | ~200 | bash, read, write, edit | Core agent loop | Model as Agent |
| v2 | ~300 | +TodoWrite | TodoManager for planning | Constraints enable complexity |
| v3 | ~450 | +Task | Subagents with context isolation | Clean context = better results |
| v4 | ~550 | +Skill | Knowledge loading via skills | Expertise without retraining |

### Key Architectural Patterns

**1. Context Isolation (v3)**
- Subagents run as isolated processes with separate message history
- Agent types: `explore` (read-only), `code` (full access), `plan` (read-only analysis)
- Each agent type has filtered tools and specialized system prompts
- Process isolation prevents context pollution in complex tasks

**2. Knowledge Externalization (v4)**
- Skills store domain knowledge in `skills/<name>/SKILL.md` files
- Format: YAML frontmatter (name, description) + Markdown body
- Skills are loaded on-demand via the Skill tool
- Cache-preserving injection via tool results

**3. Explicit Planning (v2)**
- `TodoManager` enforces constraints: max 20 items, only one `in_progress` at a time
- TodoWrite tool for task tracking
- NAG_REMINDER injection when agent doesn't use todos

**4. Tool Design Philosophy**
- Tools are capabilities (what the model CAN do)
- Skills are knowledge (what the model KNOWS how to do)
- Tools execute, Skills instruct
- Minimal interface, maximum flexibility

### Configuration

Environment variables in `.env`:
- `ANTHROPIC_API_KEY` (required) - Your Anthropic API key
- `ANTHROPIC_BASE_URL` (optional) - For API proxies
- `MODEL_ID` (optional) - Model selection (defaults to claude-sonnet-4-5-20250929)

### Project Structure

```
learn-claude-code/
├── v*_agent.py          # Progressive agent implementations
├── skills/              # Domain expertise skills
│   ├── pdf/            # PDF processing
│   ├── code-review/    # Code review methodology
│   ├── mcp-builder/    # MCP server development
│   └── agent-builder/  # Meta-agent for building agents
├── docs/               # Technical documentation (EN + ZH + JA)
├── articles/           # Blog-style explanations (ZH)
├── tests/              # Unit and integration tests
└── .env.example        # Environment configuration
```

### Core Philosophy

> **The model is 80%. Code is 20%.**

Modern agents work because the model is trained to be an agent. The code's job is to provide tools and get out of the way.

### Related Projects

- **Kode CLI** - Production-ready open source agent CLI
- **shareAI-skills** - Production skills collection
- **Agent Skills Spec** - Official specification

### Documentation Resources

- **README.md**: Main overview with learning path
- **docs/**: Technical tutorials for each version (v0-v4)
- **articles/**: In-depth explanations in Chinese
- Multi-language support: English, Chinese (README_zh.md), Japanese (README_ja.md)
