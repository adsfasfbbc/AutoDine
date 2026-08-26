/**
 * AutoDine 端到端交互 QA（无头浏览器，纯 SPA 导航）：
 * 从首页进入消费者端完成加购→下单→状态推进，再经「切换角色」进入生产端
 * 验证任务看板、智能点餐推荐、管理端订单，全程不整页刷新以保持 Mock 状态。
 *
 * 运行：node scripts/qa-flow.mjs  （依赖系统 Edge + playwright-core）
 */
import { chromium } from 'playwright-core'

const BASE = process.env.QA_BASE_URL ?? 'http://localhost:5173'
const EDGE_PATHS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
]

const results = []
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail })
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`)
}

const browser = await chromium.launch({
  headless: true,
  executablePath: EDGE_PATHS.find((p) => p),
  args: ['--no-sandbox', '--disable-gpu'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(8000)

try {
  /* 0. 首页 → 消费者端（SPA） */
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: /进入消费者端/ }).click()
  await page.waitForSelector('text=金桔柠檬水', { timeout: 8000 })

  /* 1. B 主站加购 → A 自助点餐，共享购物车 */
  await page.getByRole('button', { name: '加入' }).first().click()
  const cartCount = await page.locator('header span.tabular-nums').first().textContent()
  check('菜单加购后购物车计数', cartCount?.includes('1') ?? false, `计数=${cartCount?.trim()}`)

  await page.getByRole('button', { name: '进入自助点餐' }).click()
  await page.waitForURL('**/consumer/kiosk')
  const kioskHeading = page.getByRole('heading', { name: '自助点餐' })
  await kioskHeading.waitFor()
  check('B 可进入 A 自助点餐模式', await kioskHeading.isVisible())
  const kioskOrder = page.getByRole('complementary', { name: '自助订单' })
  await kioskOrder.waitFor()
  check('B 的购物车状态进入 A 后保留', await kioskOrder.getByText('金桔柠檬水').isVisible())

  await page.getByRole('button', { name: /加入 .* 元/ }).nth(1).click()
  await page.getByRole('button', { name: '返回普通页面' }).click()
  await page.waitForURL('**/consumer/menu')
  const preservedCount = Number(await page.locator('header [data-cart-count]').textContent())
  check('A 的加购状态返回 B 后保留', preservedCount >= 2, `计数=${preservedCount}`)

  /* 2. 再次进入 A 并确认订单 → 订单页 */
  await page.getByRole('button', { name: '进入自助点餐' }).click()
  await page.waitForURL('**/consumer/kiosk')
  await page.getByRole('button', { name: '确认订单' }).click()
  await page.waitForURL('**/consumer/orders', { timeout: 10000 })
  await page.waitForSelector('text=取餐码', { timeout: 8000 })
  const orderId = (await page.locator('text=/OD[A-Z0-9]+/').first().textContent())?.match(/OD[A-Z0-9]+/)?.[0] ?? ''
  check('A 自助点餐下单成功并进入订单页', orderId.startsWith('OD'), `订单=${orderId}`)

  /* 3. 订单自动推进到制作中 */
  await page.waitForSelector('text=制作中', { timeout: 12000 })
  check('订单状态自动推进到制作中', true)

  /* 4. 切换角色 → 生产端 → 任务看板（SPA，Mock 状态保持） */
  await page.getByRole('button', { name: '切换角色' }).click()
  await page.getByRole('button', { name: /进入生产端/ }).click()
  await page.getByRole('link', { name: '制作任务' }).click()
  await page.waitForSelector(`text=${orderId}`, { timeout: 8000 })
  check('生产端任务看板含新任务', true, `任务=${orderId}`)

  /* 5. 生产端设备页渲染 */
  await page.getByRole('link', { name: '设备' }).click()
  await page.waitForSelector('text=2 号冷藏柜', { timeout: 8000 })
  check('生产端设备页渲染', true)

  /* 6. 切换角色 → 消费者端 → 智能点餐 */
  await page.getByRole('button', { name: '切换角色' }).click()
  await page.getByRole('button', { name: /进入消费者端/ }).click()
  await page.getByRole('link', { name: '智能点餐' }).click()
  await page.getByPlaceholder(/输入你的口味偏好/).fill('推荐低卡饮品')
  await page.getByRole('button', { name: '发送' }).click()
  const pickText = await page.locator('text=/为你找到 \\d+ 款/').textContent()
  check('Agent 返回低卡推荐', /为你找到 [1-9]/.test(pickText ?? ''), pickText?.trim().split('\n')[0])

  /* 7. 切换角色 → 管理端 → 订单管理（含新订单） */
  await page.getByRole('button', { name: '切换角色' }).click()
  await page.getByRole('button', { name: /进入管理端/ }).click()
  await page.locator('aside a', { hasText: '订单管理' }).first().click()
  await page.waitForSelector(`text=${orderId}`, { timeout: 8000 })
  const rows = await page.locator('tbody tr').count()
  check('管理端订单列表含新订单', rows >= 11, `行数=${rows}`)

  /* 8. 经营分析环形图 */
  await page.getByRole('link', { name: '经营分析' }).click()
  await page.waitForSelector('text=分时营收', { timeout: 8000 })
  await page.waitForSelector('svg circle[stroke-dasharray]', { timeout: 8000 })
  const bars = await page.locator('svg circle[stroke-dasharray]').count()
  check('经营分析环形图渲染', bars >= 5, `环形分段=${bars}`)
} catch (e) {
  check('流程执行', false, String(e).slice(0, 240))
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok).length
console.log('---')
console.log(`passed=${results.length - failed} failed=${failed}`)
process.exit(failed > 0 ? 1 : 0)
