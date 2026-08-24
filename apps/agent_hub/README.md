# AutoDine Agent Hub

Agent Hub 是 AutoDine 的智能体协调应用。它通过 **Tool Calling** 调用中台
（AutoDineCore）的 REST API，实现三个 LLM Agent：

| Agent | 职责 | 核心能力 |
|---|---|---|
| `consumer` | 消费者点餐助手 | 菜单推荐、智能点餐、查单、退单 |
| `kitchen` | 后厨助手 | 生产咨询：领料清单、生产状态推进 |
| `manager` | 店长助手 | 库存/质量查询、告警处理、排队查看、运营总结 |

**约束**：Agent 只能通过 `CoreClient` 走中台 REST 接口，**严禁直接访问数据库**，
也不 import 任何 `autodine_core` 内部代码。

## 目录结构

```
apps/agent_hub/
├── pyproject.toml           # 独立子包：依赖、打包、test extra（对齐 front_vision）
├── README.md
├── src/agent_hub/
│   ├── __init__.py
│   ├── __main__.py          # python -m agent_hub 入口
│   ├── config.py            # Settings（AGENT_HUB_* 环境变量）
│   ├── errors.py            # 异常类型（CoreAPIError / UnknownAgentError）
│   ├── core_client.py       # 唯一访问中台 REST 的客户端（httpx）
│   ├── tools/               # 工具层：每个工具封装一个中台接口（JSON Schema + handler）
│   │   ├── base.py          #   ToolDefinition
│   │   ├── menu.py / order.py / production.py
│   │   ├── inventory.py / alarm.py / queue.py / analytics.py / device.py
│   │   └── __init__.py      #   TOOL_REGISTRY + execute_tool
│   ├── llm/                 # 可插拔 LLM 适配器
│   │   ├── base.py          #   LLMAdapter / ChatMessage / LLMResponse
│   │   ├── openai_adapter.py   # 任意 OpenAI 兼容端点（Qwen / DeepSeek / GLM）
│   │   └── scripted_adapter.py # 确定性兜底（离线 / 测试）
│   ├── agents/              # 三个 Agent
│   │   ├── base.py          #   Agent 执行循环（生成 → 执行工具 → 回填）
│   │   ├── consumer.py / kitchen.py / manager.py
│   │   └── __init__.py      #   build_agent
│   ├── hub.py               # AgentHub：组装 client + adapter + agents
│   ├── cli.py               # 命令行
│   ├── service.py           # FastAPI 应用（create_app） + Web 界面托管
│   └── web/                 # 每个 Agent 一个交互界面
│       ├── index.html / consumer.html / kitchen.html / manager.html
│       └── static/          #   style.css / app.js
└── tests/                   # 离线测试（MockTransport + 假 LLM）
    ├── conftest.py / helpers.py
    ├── test_core_client.py / test_tools.py / test_agents.py
    ├── test_openai_adapter.py / test_scripted_adapter.py
    └── test_service.py
```

## 安装

```bash
cd apps/agent_hub
pip install -e ".[test]"
```

## 使用

### 1. 命令行（默认走 scripted 兜底，无需 API Key）

```bash
# 单轮
python -m agent_hub consumer "推荐一杯含奶饮品"
python -m agent_hub manager "今天的运营总结"

# 列出 agent
python -m agent_hub --list

# 交互式
python -m agent_hub kitchen --chat
```

> 默认 `AGENT_HUB_LLM_DRIVER=scripted`：用一个确定性的意图路由驱动工具调用，
> 无需任何外部 LLM 即可跑通完整链路（也用于测试）。

### 2. 接入国产模型（OpenAI 兼容）

任选一家提供 OpenAI 兼容接口的厂商，设置环境变量后即可切到真实 Tool Calling：

```bash
# Qwen（阿里云百炼 DashScope）
export AGENT_HUB_LLM_DRIVER=openai
export AGENT_HUB_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export AGENT_HUB_LLM_API_KEY=<你的 DASHSCOPE_API_KEY>
export AGENT_HUB_LLM_MODEL=qwen-plus

# DeepSeek
# export AGENT_HUB_LLM_BASE_URL=https://api.deepseek.com
# export AGENT_HUB_LLM_MODEL=deepseek-chat

# GLM（智谱）
# export AGENT_HUB_LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# export AGENT_HUB_LLM_MODEL=glm-4-flash

python -m agent_hub consumer "帮我点一杯美式"
```

### 3. HTTP 服务 + Web 交互界面

**一键启动**：双击仓库根目录的 `start.bat`，会自动「建种子库 → 启动 Core(8000) → 启动 Agent Hub(8100) → 打开浏览器」。手动启动方式如下：

每个 Agent 都有一个独立的网页聊天界面：

```bash
python -m uvicorn agent_hub.service:create_app --factory --port 8100
```

浏览器打开：

| 页面 | Agent |
|---|---|
| `http://localhost:8100/` | 入口页（选择 Agent） |
| `http://localhost:8100/consumer` | 🛒 Consumer（点餐 / 推荐） |
| `http://localhost:8100/kitchen` | 👨‍🍳 Kitchen（生产咨询） |
| `http://localhost:8100/manager` | 📊 Manager（库存 / 运营） |

REST 接口：

```bash
curl http://localhost:8100/health
curl http://localhost:8100/api/v1/agents
curl -X POST http://localhost:8100/api/v1/agents/manager/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "库存怎么样"}'
```

## 配置项（`AGENT_HUB_*`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_HUB_CORE_BASE_URL` | `http://localhost:8000` | 中台 REST 地址 |
| `AGENT_HUB_DEFAULT_STORE_ID` | `store-main` | 默认门店 |
| `AGENT_HUB_DEFAULT_LOCATION_ID` | `bar` | 默认仓/位置（与种子数据一致） |
| `AGENT_HUB_LLM_DRIVER` | `scripted` | `scripted` 或 `openai` |
| `AGENT_HUB_LLM_BASE_URL` | — | OpenAI 兼容端点 |
| `AGENT_HUB_LLM_API_KEY` | — | API Key |
| `AGENT_HUB_LLM_MODEL` | `qwen-plus` | 模型名 |
| `AGENT_HUB_MAX_TOOL_ITERATIONS` | `8` | 单轮最大工具调用轮次 |

## 测试

```bash
cd apps/agent_hub
pytest -q
```

全部离线：用 `httpx.MockTransport` 伪造中台、用 `ScriptedAdapter` 或注入的假
client 驱动，不依赖真实数据库或 LLM。

## 已知限制（来自中台当前 API 边界）

1. 中台没有「生产任务列表」端点（只有按 `task_id` 的 start/ready/complete），
   因此 Kitchen Agent 以 `order_id` 为入口：先 `get_order` 拿到 `task_id` 与
   `pick_list`，再推进生产。
2. `complete_production_task` 的 `actual_consumption` 需要 `location_id`，而
   `get_order` 返回的 `pick_list` 只有 `{ingredient_id, quantity, unit}`（中台
   未暴露 reservation 明细）。单店单仓场景下用 `default_location_id`（`bar`）
   补全；多仓场景需中台补充接口，见 `docs/superpowers/specs/2026-08-21-autodine-v1-design.md`。
3. `get_analytics_summary` 的 `start/end` 为必填，工具层默认近 24 小时兜底，
   使「运营总结」一句话即可用。
