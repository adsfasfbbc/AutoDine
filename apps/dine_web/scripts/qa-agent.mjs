/**
 * 三端 Agent 前端契约 QA：验证每个角色拥有独立页面、上下文侧栏，
 * 并能通过同一交互模式获得角色化 Mock 回复。
 */
import { chromium } from 'playwright-core'
import { existsSync, readFileSync } from 'node:fs'

const agentSource = readFileSync(new URL('../src/api/agent.ts', import.meta.url), 'utf8')
const viteSource = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8')
if (!agentSource.includes('/api/v1/advisors/${agent}/chat') || agentSource.includes('/api/v1/agents/${agent}/chat')) {
  throw new Error('Agent HTTP 客户端必须只调用只读 advisors 契约，禁止调用含写工具的 agents/chat')
}
if (!viteSource.includes("'/agent-api'") || !viteSource.includes("target: 'http://localhost:8100'")) {
  throw new Error('缺少 Agent Hub 开发环境同源代理配置')
}
console.log('[PASS] Agent HTTP 边界：只读契约 + 同源代理')

const BASE = process.env.QA_BASE_URL ?? 'http://localhost:5173'
const EDGE_PATHS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
]

const cases = [
  {
    route: '/consumer/agent',
    heading: '智能点餐助手',
    context: '点餐上下文',
    prompt: '推荐低卡饮品',
    reply: /为你找到 [1-9]/,
  },
  {
    route: '/production/agent',
    heading: '生产协同助手',
    context: '生产上下文',
    prompt: '哪些任务需要优先处理？',
    reply: /生产建议/,
  },
  {
    route: '/admin/agent',
    heading: '经营决策助手',
    context: '管理上下文',
    prompt: '总结今天的经营情况',
    reply: /经营建议/,
  },
]

const browser = await chromium.launch({
  headless: true,
  executablePath: EDGE_PATHS.find((path) => existsSync(path)),
  args: ['--no-sandbox', '--disable-gpu'],
})

let failed = 0
for (const testCase of cases) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.setDefaultTimeout(8_000)
  try {
    await page.goto(`${BASE}${testCase.route}`, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: testCase.heading }).waitFor()
    await page.getByRole('complementary', { name: testCase.context }).waitFor()
    await page.getByRole('textbox', { name: '向助手提问' }).fill(testCase.prompt)
    await page.getByRole('button', { name: '发送' }).click()
    await page.getByText(testCase.reply).waitFor({ timeout: 10_000 })
    console.log(`[PASS] ${testCase.heading}：独立页面、上下文与回复`)
  } catch (error) {
    failed += 1
    console.log(`[FAIL] ${testCase.heading}：${String(error).slice(0, 220)}`)
  } finally {
    await page.close()
  }
}

await browser.close()
console.log('---')
console.log(`passed=${cases.length - failed} failed=${failed}`)
process.exit(failed > 0 ? 1 : 0)
