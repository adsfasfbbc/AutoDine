# AutoDine Web · 前端中枢

AutoDine 是云边协同的无人餐厅与甜品店系统。本仓库是前端（团队仓库中的 F 模块，对应 `apps/dine_web`），
以 **Vue 3 + Vite + TypeScript** 实现统一桌面 SPA：消费者端、生产端、管理端通过角色入口切换，
共享同一订单与设备状态语义。

## 快速开始

```bash
pnpm install     # 安装依赖
pnpm dev         # 启动开发服务器 http://localhost:5173
pnpm build       # 类型检查 + 生产构建
pnpm preview     # 预览构建产物
```

> 开发环境默认使用 **Mock 数据源**（内存状态 + 延迟模拟 + 实时事件），无需后端即可完整体验
> 点餐 → 下单 → 排队 → 制作 → 取餐闭环。Core 就绪后设置 `VITE_USE_MOCK=false` 切换真实接口。

复制 `.env.example` 为 `.env.local` 后可覆盖本机配置。所有 `VITE_*` 变量都会进入浏览器构建产物，
因此不得写入模型 API Key 或其他服务端密钥。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_USE_MOCK` | `true` | `'false'` 时切换为真实 HTTP/WS 客户端 |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Core REST 基地址 |
| `VITE_WS_BASE_URL` | `ws://localhost:8000` | Core WebSocket 基地址 |
| `VITE_AGENT_USE_MOCK` | `true` | 只读建议端点就绪后，设为 `'false'` 切换 Agent Hub |
| `VITE_AGENT_BASE_URL` | `/agent-api` | Agent Hub 同源代理前缀 |

## 三端智能助手现状

- 当前 `/consumer/agent`、`/production/agent`、`/admin/agent` 分别提供点餐、生产协同与经营决策助手；三者共用 `src/api/agent.ts` 接口，默认使用角色化 Mock。
- 消费者 Mock 按预算、热量、过敏原、品类与标签筛选当前菜单；生产和管理助手读取页面现有业务接口的关键数据并给出建议，不会自动执行任务流转、库存或告警操作。
- 当前实现不内嵌、不直连 Codex/OpenAI，也不消耗 Codex、ChatGPT 或 OpenAI API 额度；默认 Mock 部署无需模型服务。
- 前端已预留只读契约 `POST /api/v1/advisors/{consumer|kitchen|manager}/chat`；请求为 `message + history`，回复为 `agent + reply`，并可选返回 `suggestions`。该端点需由 Agent Hub 负责人实现并在服务端限制为只读工具后，才能设置 `VITE_AGENT_USE_MOCK=false`。
- 当前 Agent Hub 的 `/api/v1/agents/{agent}/chat` 含下单、任务流转、告警和设备命令等写工具，前端不会调用该端点，避免“建议助手”意外改变业务状态。
- 模型 API Key 只能存放在 Agent Hub 的服务端环境或云端密钥管理中，不能使用 `VITE_*` 暴露给浏览器。

## 部署边界

- 当前团队仓库没有为 Web 定义 Docker 服务或云发布流水线；本模块的交付要求是可独立 `pnpm dev`、`pnpm build` 与本地预览。
- `dist/` 是静态产物，可部署到支持 SPA 路由回退的静态托管平台；默认 Mock 模式不依赖后端。
- 启用真实数据时，需要可访问的 Core REST/WebSocket；启用真实智能建议时还需要部署只读 Agent Hub 端点。开发环境已将 `/agent-api` 代理到 `localhost:8100`，生产环境需配置同路径反向代理。

## 三端入口

| 端 | 路由 | 内容 |
|---|---|---|
| 首页 | `/` | 三端角色入口（传菜带式入场动效） |
| 消费者端 | `/consumer/*` | 菜单（分类/搜索/热量/过敏原筛选、持久购物车、商品详情）、智能点餐助手（Agent 推荐）、排队、订单状态 |
| 门店自助点餐 | `/consumer/kiosk` | 从消费者端显式进入的横屏自助模式；与普通页面共享菜单、购物车和订单状态 |
| 生产端 | `/production/*` | 生产总览、生产协同助手、制作任务看板（四状态流转）、库存（67 原料 + 流水）、质检、设备（温控/重启/自检） |
| 管理端 | `/admin/*` | 经营总览、经营决策助手、订单管理（筛选/详情/取消）、客流分析（分时图）、库存管理（损耗/流水）、告警中心、经营分析（分时营收/品类构成） |

## 目录结构

```
../../contracts/     团队仓库根目录契约（openapi / websocket / adp，只读）
docs/                设计系统与接口适配说明
public/img/          演示菜品配图（Unsplash 占位，可替换为实拍）
src/
  api/               契约适配层：types / http / ws / client / mock
  data/              P0 示例数据（40 SKU 中 8 个演示商品，含 BOM）
  stores/            Pinia：角色 / 菜单 / 购物车 / 订单
  layouts/           三端布局（用户端顶栏、生产/管理端侧边栏）
  views/             首页与三端页面
  styles/            设计令牌（品牌蓝橙、字体、动效、reduced-motion）
```

## 数据边界

- 页面不直接耦合 Mock：所有数据经 `src/api/` 适配层，`api` 与 `realtime` 按环境切换 Mock/真实实现。
- 真实契约见 `../../contracts/openapi/autodine-core-v1.yaml` 与 `../../contracts/websocket/topics.yaml`。
- 菜单在售/售罄语义：真实环境由 Core 依据 BOM 可售量维护；Mock 用 `stock` 字段演示库存驱动联动。

## 视觉与规范

- 品牌：深海军蓝 + 暖橙，纸张质感暖灰背景，克制版式（详见 `docs/DESIGN.md`）。
- 动效：单一主记忆动效（传菜带入场）+ 短促交互反馈；支持 `prefers-reduced-motion`。
- 目标分辨率：1440×900 与 1920×1080 桌面横屏。
- 用户端模式：普通电脑页面 B 为默认体验，自助点餐 A 由顶栏“进入自助点餐”按钮进入，不按屏幕宽度自动切换。

## 演示配图

`public/img/*.jpg` 为 Unsplash 演示占位图（仅用于视觉阶段），接入真实门店物料后替换即可。
