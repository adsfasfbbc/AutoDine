/**
 * AutoDine 布局 QA：无头浏览器遍历三端全部路由，
 * 在 1440×900 与 1920×1080 两个视口检测横向溢出与运行时错误。
 *
 * 运行：pnpm qa  （依赖系统 Edge + playwright-core）
 */
import { chromium } from 'playwright-core'
import { writeFileSync } from 'node:fs'

const BASE = process.env.QA_BASE_URL ?? 'http://localhost:5173'

const ROUTES = [
  '/',
  '/consumer/menu',
  '/consumer/kiosk',
  '/consumer/agent',
  '/consumer/queue',
  '/consumer/orders',
  '/production/overview',
  '/production/agent',
  '/production/tasks',
  '/production/inventory',
  '/production/quality',
  '/production/devices',
  '/admin/overview',
  '/admin/agent',
  '/admin/orders',
  '/admin/traffic',
  '/admin/inventory',
  '/admin/alarms',
  '/admin/analytics',
]

const VIEWPORTS = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
]

const EDGE_PATHS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
]

function findEdge() {
  return EDGE_PATHS.find((p) => p) ?? undefined
}

const report = { base: BASE, checkedAt: new Date().toISOString(), viewports: [] }

const browser = await chromium.launch({
  headless: true,
  executablePath: findEdge(),
  args: ['--no-sandbox', '--disable-gpu'],
})

let failures = 0

for (const vp of VIEWPORTS) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } })
  const vpResult = { viewport: vp.name, routes: [] }

  for (const route of ROUTES) {
    const errors = []
    const onPageError = (err) => errors.push(`pageerror: ${String(err)}`)
    const onConsole = (msg) => {
      if (msg.type() === 'error') errors.push(`console.error: ${msg.text().slice(0, 200)}`)
    }
    page.on('pageerror', onPageError)
    page.on('console', onConsole)

    const row = { route, status: 'OK', overflow: null, title: null }
    try {
      await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 20000 })
      // 等待 Mock 数据与首帧动效完成
      await page.waitForTimeout(900)
      const metrics = await page.evaluate(() => {
        const doc = document.documentElement
        const body = document.body
        return {
          scrollW: Math.max(doc.scrollWidth, body.scrollWidth),
          innerW: window.innerWidth,
          scrollH: Math.max(doc.scrollHeight, body.scrollHeight),
          innerH: window.innerHeight,
          title: document.title,
        }
      })
      row.title = metrics.title
      const overflowX = metrics.scrollW - metrics.innerW
      if (overflowX > 2) {
        row.status = 'OVERFLOW_X'
        row.overflow = overflowX
      }
      if (route === '/consumer/kiosk' && metrics.scrollH > metrics.innerH + 100) {
        await page.evaluate(() => window.scrollTo(0, Math.min(520, document.documentElement.scrollHeight - window.innerHeight)))
        await page.waitForTimeout(120)
        const cartBox = await page.locator('aside[aria-label="自助订单"]').evaluate((element) => {
          const rect = element.getBoundingClientRect()
          return { top: rect.top, bottom: rect.bottom }
        })
        if (cartBox.top < 80 || cartBox.bottom <= 160) {
          row.status = row.status === 'OK' ? 'KIOSK_CART_NOT_STICKY' : `${row.status}+KIOSK_CART_NOT_STICKY`
          row.cartBox = cartBox
        }
        await page.evaluate(() => window.scrollTo(0, 0))
      }
      if (errors.length > 0) {
        row.status = row.status === 'OK' ? 'RUNTIME_ERROR' : `${row.status}+RUNTIME_ERROR`
        row.errors = errors.slice(0, 3)
      }
      if (row.status !== 'OK') failures++
    } catch (e) {
      row.status = 'NAV_FAIL'
      row.errors = [String(e).slice(0, 200)]
      failures++
    } finally {
      page.removeListener('pageerror', onPageError)
      page.removeListener('console', onConsole)
    }
    vpResult.routes.push(row)
    console.log(`[${vp.name}] ${row.status.padEnd(14)} ${route}`)
  }
  report.viewports.push(vpResult)
  await page.close()
}

await browser.close()

writeFileSync(new URL('./qa-report.json', import.meta.url), JSON.stringify(report, null, 2))
console.log('---')
console.log(`failures=${failures} viewports=${VIEWPORTS.length} routes=${ROUTES.length * VIEWPORTS.length}`)
process.exit(failures > 0 ? 1 : 0)
