import type { Product } from './types'

export type AgentName = 'consumer' | 'kitchen' | 'manager'

export interface AgentHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentSuggestion {
  kind: 'product' | 'route'
  id: string
  label?: string
  to?: string
}

export interface AgentChatRequest {
  message: string
  history?: AgentHistoryMessage[]
  /** 仅供 Mock 生成贴合当前页面数据的回复；真实 Agent Hub 暂不接收此字段。 */
  context?: Record<string, unknown>
}

export interface AgentChatResponse {
  agent: AgentName
  reply: string
  suggestions?: AgentSuggestion[]
}

export interface AgentClient {
  chat(agent: AgentName, request: AgentChatRequest): Promise<AgentChatResponse>
}

function matchBudget(text: string): number | null {
  const match = text.match(/(\d+)\s*元/)
  return match ? Number(match[1]) : null
}

function recommendProducts(text: string, products: Product[]): Product[] {
  const budgetYuan = matchBudget(text)
  const lowCal = /低卡|低热量|热量低/.test(text)
  const candidates = products.filter((product) => {
    if (product.status !== 'ON_SALE') return false
    if (lowCal && product.calories_kcal > 250) return false
    if (/无乳|不含乳/.test(text) && product.allergens.includes('MILK')) return false
    if (/无蛋/.test(text) && product.allergens.includes('EGG')) return false
    if (/无麸/.test(text) && product.allergens.includes('GLUTEN')) return false
    if (budgetYuan !== null && product.price_cent > budgetYuan * 100) return false
    if (/饮品|茶|果茶|饮料/.test(text) && product.category !== 'DRINK') return false
    if (/甜品|杯|奶油杯/.test(text) && product.category !== 'CUP_DESSERT') return false
    if (/蛋糕|芝士|烘焙/.test(text) && product.category !== 'CAKE') return false
    if (/热食|小吃|炸|薯条|鸡/.test(text) && product.category !== 'HOT_FOOD') return false
    if (/招牌/.test(text) && !product.tags.includes('招牌')) return false
    return true
  })
  const sortValue = lowCal ? (product: Product) => product.calories_kcal : (product: Product) => product.price_cent
  return [...candidates].sort((a, b) => sortValue(a) - sortValue(b)).slice(0, 4)
}

function numberFrom(context: Record<string, unknown> | undefined, key: string): number {
  const value = context?.[key]
  return typeof value === 'number' ? value : 0
}

class MockAgentClient implements AgentClient {
  async chat(agent: AgentName, request: AgentChatRequest): Promise<AgentChatResponse> {
    await new Promise((resolve) => setTimeout(resolve, 620))

    if (agent === 'consumer') {
      const products = Array.isArray(request.context?.products) ? (request.context.products as Product[]) : []
      const picks = recommendProducts(request.message, products)
      if (picks.length === 0) {
        return { agent, reply: '暂时没有完全符合的在售商品，试试放宽条件，比如去掉过敏原或预算限制？' }
      }
      const details: string[] = [`为你找到 ${picks.length} 款在售商品：`]
      if (/低卡|低热量/.test(request.message)) details.push('已按热量从低到高排序，都是 250 kcal 以内的轻负担选择。')
      const budget = matchBudget(request.message)
      if (budget !== null) details.push(`已按预算 ¥${budget} 以内筛选。`)
      details.push('点击卡片右下角即可加入购物车。')
      return {
        agent,
        reply: details.join('\n'),
        suggestions: picks.map((product) => ({ kind: 'product', id: product.product_id })),
      }
    }

    if (agent === 'kitchen') {
      const pending = numberFrom(request.context, 'pendingTasks')
      const producing = numberFrom(request.context, 'producingTasks')
      const risks = numberFrom(request.context, 'riskCount')
      const reply = /设备|异常/.test(request.message)
        ? `生产建议：当前有 ${risks} 项现场风险，建议先复核离线设备与高优质检项，再安排可并行任务。`
        : `生产建议：先处理 ${pending} 个待制作任务，同时关注 ${producing} 个制作中任务的超时风险；本建议不会自动改变任务状态。`
      return { agent, reply }
    }

    const orders = numberFrom(request.context, 'orders')
    const openAlarms = numberFrom(request.context, 'openAlarms')
    const avgWaitMinutes = numberFrom(request.context, 'avgWaitMinutes')
    const reply = /告警|风险/.test(request.message)
      ? `经营建议：当前有 ${openAlarms} 条未闭环告警，建议优先核对关键设备和库存类告警，再评估对客流的影响。`
      : `经营建议：今日已记录 ${orders} 笔订单，平均等待约 ${avgWaitMinutes} 分钟；可结合高峰时段提前调配产能。本建议仅供决策参考。`
    return { agent, reply }
  }
}

class HttpAgentClient implements AgentClient {
  private readonly baseUrl = (import.meta.env.VITE_AGENT_BASE_URL || '/agent-api').replace(/\/$/, '')

  async chat(agent: AgentName, request: AgentChatRequest): Promise<AgentChatResponse> {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10_000)
    try {
      // 必须接入服务端强制只读的建议端点；现有 /agents/*/chat 含写工具，禁止从本页面调用。
      const response = await fetch(`${this.baseUrl}/api/v1/advisors/${agent}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: request.message, history: request.history ?? [] }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error(`Agent Hub 请求失败（${response.status}）`)
      const data = (await response.json()) as Partial<AgentChatResponse>
      if (typeof data.reply !== 'string') throw new Error('Agent Hub 返回格式不正确')
      return {
        agent,
        reply: data.reply,
        suggestions: Array.isArray(data.suggestions) ? data.suggestions : undefined,
      }
    } finally {
      window.clearTimeout(timeout)
    }
  }
}

const useAgentMock = import.meta.env.VITE_AGENT_USE_MOCK !== 'false'

export const agentConnectionLabel = useAgentMock ? 'Mock 联调' : 'Agent Hub · 只读'

/** 三端共用建议接口；默认 Mock，服务端只读端点完成后才可切换。 */
export const agentApi: AgentClient = useAgentMock ? new MockAgentClient() : new HttpAgentClient()
