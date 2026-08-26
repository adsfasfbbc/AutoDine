import { CATEGORY_LABELS, INVENTORY_SEED, P0_PRODUCTS } from '@/data/products'

import type { ApiClient } from '../client'
import type {
  Alarm,
  AnalyticsSummary,
  CategoryShare,
  Device,
  DeviceCommand,
  HealthStatus,
  HourlyPoint,
  InventoryItem,
  InventoryMovement,
  Order,
  OrderCreateInput,
  ProductionTask,
  Product,
  ProductDetail,
  QualityEvent,
  QueueSnapshot,
  TrafficSummary,
} from '../types'
import type { WsMessage, WsTopic } from '../ws'

const STORE_ID = 'store-main'

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const jitter = (base: number) => base + Math.random() * 140
const nowIso = () => new Date().toISOString()
const addSecIso = (sec: number) => new Date(Date.now() + sec * 1000).toISOString()
const genId = (prefix: string) =>
  `${prefix}${Date.now().toString(36).toUpperCase()}${Math.floor(Math.random() * 46656).toString(36).toUpperCase()}`
const rand = (min: number, max: number) => Math.floor(min + Math.random() * (max - min + 1))

interface MockOrderState {
  order: Order
  task: ProductionTask
  timers: ReturnType<typeof setTimeout>[]
}

function seedAlarms(): Alarm[] {
  const base = Date.now()
  const at = (minAgo: number) => new Date(base - minAgo * 60_000).toISOString()
  return [
    {
      alarm_id: 'AL001',
      store_id: STORE_ID,
      severity: 'CRITICAL',
      category: 'DEVICE',
      title: '冷藏柜温度异常',
      message: '1 号冷藏柜温度 12.4°C，超过阈值 8°C，请立即检查。',
      status: 'OPEN',
      created_at: at(4),
    },
    {
      alarm_id: 'AL002',
      store_id: STORE_ID,
      severity: 'WARNING',
      category: 'INVENTORY',
      title: '草莓库存偏低',
      message: '草莓视觉计数 4.2kg，低于安全阈值 5kg，建议补货。',
      status: 'OPEN',
      created_at: at(12),
    },
    {
      alarm_id: 'AL003',
      store_id: STORE_ID,
      severity: 'INFO',
      category: 'QUALITY',
      title: '芒果表皮损伤批次',
      message: '早间质检发现芒果批次 M-0821 表皮损伤，已隔离待处理。',
      status: 'ACKNOWLEDGED',
      created_at: at(96),
      acknowledged_at: at(90),
    },
    {
      alarm_id: 'AL004',
      store_id: STORE_ID,
      severity: 'INFO',
      category: 'DEVICE',
      title: '出餐口传感器离线恢复',
      message: '出餐口传感器已于 09:24 恢复在线。',
      status: 'RESOLVED',
      created_at: at(180),
      acknowledged_at: at(175),
      resolved_at: at(160),
    },
  ]
}

function seedDevices(): Device[] {
  const at = (minAgo: number) => new Date(Date.now() - minAgo * 60_000).toISOString()
  return [
    { device_id: 'D001', name: '1 号冷藏柜', kind: 'COOLER', location: '原料区 · 东', status: 'ONLINE', temperature_c: 4.2, target_temp_c: 4, online_since: at(120), last_seen_at: at(0) },
    { device_id: 'D002', name: '2 号冷藏柜', kind: 'COOLER', location: '原料区 · 西', status: 'ERROR', temperature_c: 12.4, target_temp_c: 4, online_since: at(300), last_seen_at: at(1) },
    { device_id: 'D003', name: '智能烤箱', kind: 'OVEN', location: '热食工位', status: 'ONLINE', temperature_c: 182, target_temp_c: 180, online_since: at(90), last_seen_at: at(0), metrics: { 批次: 3 } },
    { device_id: 'D004', name: '自动炸炉', kind: 'FRYER', location: '热食工位', status: 'ONLINE', temperature_c: 176, target_temp_c: 175, online_since: at(90), last_seen_at: at(0) },
    { device_id: 'D005', name: '制冰机', kind: 'ICE_MAKER', location: '饮品区', status: 'ONLINE', online_since: at(400), last_seen_at: at(0), metrics: { 冰量kg: 12 } },
    { device_id: 'D006', name: '出餐口', kind: 'PICKUP', location: '前场', status: 'ONLINE', online_since: at(200), last_seen_at: at(0) },
    { device_id: 'D007', name: '前场视觉传感器', kind: 'SENSOR', location: '前场 · 顶', status: 'ONLINE', online_since: at(600), last_seen_at: at(0), metrics: { 帧率: 24 } },
    { device_id: 'D008', name: '仓储视觉传感器', kind: 'SENSOR', location: '仓储 · 顶', status: 'ONLINE', online_since: at(600), last_seen_at: at(0), metrics: { 帧率: 24 } },
    { device_id: 'D009', name: '制作机械臂', kind: 'ROBOT', location: '中央工位', status: 'ONLINE', online_since: at(45), last_seen_at: at(0), metrics: { 负载: 38 } },
  ]
}

function seedQualityEvents(): QualityEvent[] {
  const at = (minAgo: number) => new Date(Date.now() - minAgo * 60_000).toISOString()
  return [
    { event_id: 'QE001', ingredient_id: 'I012', ingredient_name: '芒果', type: 'VISUAL_DEFECT', severity: 'HIGH', quantity: 1.2, unit: 'kg', note: '表皮大面积损伤，已隔离待处理', status: 'OPEN', detected_at: at(96), source: '视觉质检' },
    { event_id: 'QE002', ingredient_id: 'I009', ingredient_name: '牛奶', type: 'TEMP_ABNORMAL', severity: 'MEDIUM', quantity: 2, unit: 'L', note: '冷链温度短暂超标 8 分钟，复核中', status: 'INSPECTING', detected_at: at(40), source: '温控监测' },
    { event_id: 'QE003', ingredient_id: 'I010', ingredient_name: '淡奶油', type: 'EXPIRY', severity: 'LOW', quantity: 500, unit: 'g', note: '接近保质期，已安排优先出清', status: 'HANDLED', detected_at: at(200), handled_at: at(170), source: '人工巡检' },
  ]
}

function seedMovements(): InventoryMovement[] {
  const at = (minAgo: number) => new Date(Date.now() - minAgo * 60_000).toISOString()
  return [
    { movement_id: 'MV01', ingredient_id: 'I011', name: '草莓', delta: 5000, unit: 'g', reason: 'RESTOCK', occurred_at: at(150) },
    { movement_id: 'MV02', ingredient_id: 'I012', name: '芒果', delta: -1800, unit: 'g', reason: 'WASTE', occurred_at: at(120) },
    { movement_id: 'MV03', ingredient_id: 'I011', name: '草莓', delta: -960, unit: 'g', reason: 'CONSUME', occurred_at: at(80) },
    { movement_id: 'MV04', ingredient_id: 'I041', name: '冷冻薯条', delta: 20000, unit: 'g', reason: 'RESTOCK', occurred_at: at(60) },
    { movement_id: 'MV05', ingredient_id: 'I048', name: '鸡腿肉', delta: -1620, unit: 'g', reason: 'CONSUME', occurred_at: at(35) },
    { movement_id: 'MV06', ingredient_id: 'I001', name: '香水柠檬', delta: -6, unit: 'pcs', reason: 'CONSUME', occurred_at: at(12) },
    { movement_id: 'MV07', ingredient_id: 'I003', name: '蜂蜜', delta: 4000, unit: 'g', reason: 'ADJUST', occurred_at: at(8) },
  ]
}

function buildHourly(): HourlyPoint[] {
  const base = [2, 1, 1, 1, 1, 2, 3, 6, 10, 14, 16, 18, 17, 14, 13, 15, 18, 20, 19, 16, 12, 8, 5, 3]
  return base.map((orders, hour) => {
    const jitter = Math.round(Math.sin(hour * 1.7) * 2)
    const o = Math.max(0, orders + jitter)
    return { hour, orders: o, parties: Math.round(o * 1.4), revenue_cent: o * 1820 }
  })
}

function buildCategoryBreakdown(): CategoryShare[] {
  const weights: [Product['category'], number][] = [
    ['DRINK', 38],
    ['CUP_DESSERT', 24],
    ['HOT_FOOD', 20],
    ['CAKE', 13],
    ['LIGHT_MEAL', 5],
  ]
  return weights.map(([category, pct]) => ({
    category,
    label: CATEGORY_LABELS[category],
    orders: Math.round((126 * pct) / 100),
    revenue_cent: Math.round((368400 * pct) / 100),
  }))
}

function makeHistoricalOrder(
  seq: number,
  minutesAgo: number,
  status: Order['status'],
  productIds: [string, number][],
): Order {
  const created = new Date(Date.now() - minutesAgo * 60_000)
  const items = productIds.map(([pid, qty]) => {
    const p = P0_PRODUCTS.find((x) => x.product_id === pid)!
    return {
      product_id: pid,
      quantity: qty,
      name: p.name,
      price_cent: p.price_cent,
      prep_time_sec: p.prep_time_sec,
      image: p.image,
    }
  })
  const total = items.reduce((s, it) => s + it.price_cent * it.quantity, 0)
  const readyAt = new Date(created.getTime() + 6 * 60_000)
  return {
    order_id: `ODH${String(seq).padStart(4, '0')}`,
    store_id: STORE_ID,
    customer_id: 'demo-customer',
    status,
    items,
    total_price_cent: total,
    queue_position: 0,
    estimated_ready_at: readyAt.toISOString(),
    created_at: created.toISOString(),
    updated_at: readyAt.toISOString(),
  }
}

function seedOrders(): Order[] {
  return [
    makeHistoricalOrder(1, 300, 'COMPLETED', [['P001', 1], ['P027', 1]]),
    makeHistoricalOrder(2, 260, 'COMPLETED', [['P021', 1]]),
    makeHistoricalOrder(3, 220, 'COMPLETED', [['P011', 2], ['P004', 1]]),
    makeHistoricalOrder(4, 180, 'COMPLETED', [['P029', 1], ['P001', 2]]),
    makeHistoricalOrder(5, 140, 'COMPLETED', [['P003', 1], ['P012', 1]]),
    makeHistoricalOrder(6, 100, 'COMPLETED', [['P027', 2], ['P021', 1]]),
    makeHistoricalOrder(7, 70, 'CANCELED', [['P004', 1]]),
    makeHistoricalOrder(8, 45, 'READY', [['P011', 1]]),
    makeHistoricalOrder(9, 20, 'PRODUCING', [['P001', 1], ['P029', 1]]),
    makeHistoricalOrder(10, 6, 'CONFIRMED', [['P003', 2]]),
  ]
}

/**
 * Mock 数据源：内存状态 + 延迟模拟 + 实时事件发射。
 * 用于视觉阶段与演示；真实接入时由 api/index.ts 切换到 HttpApiClient。
 * - 菜单在售/售罄由 Mock 库存驱动（演示 BOM 可售量联动语义）。
 * - 订单创建后自动按 PENDING→CONFIRMED→PRODUCING→READY→COMPLETED 推进并广播事件。
 */
export class MockApiClient implements ApiClient {
  private products = P0_PRODUCTS.map((p) => ({ ...p, bom: [...p.bom] }))
  private inventory = INVENTORY_SEED.map((i) => ({ ...i }))
  private orderStates = new Map<string, MockOrderState>()
  private alarms: Alarm[] = seedAlarms()
  private devices: Device[] = seedDevices()
  private qualityEvents: QualityEvent[] = seedQualityEvents()
  private movements: InventoryMovement[] = seedMovements()
  private historicalOrders: Order[] = seedOrders()
  private listeners = new Map<WsTopic, Set<(msg: WsMessage) => void>>()

  /* ---------- realtime 桥接 ---------- */

  onTopic(topic: WsTopic, handler: (msg: WsMessage) => void): () => void {
    let set = this.listeners.get(topic)
    if (!set) {
      set = new Set()
      this.listeners.set(topic, set)
    }
    set.add(handler)
    return () => set.delete(handler)
  }

  private emit(topic: WsTopic, payload: unknown): void {
    const msg: WsMessage = { topic, store_id: STORE_ID, payload, occurred_at: nowIso() }
    this.listeners.get(topic)?.forEach((h) => h(msg))
  }

  /* ---------- 工具 ---------- */

  private async latency(): Promise<void> {
    await delay(jitter(120))
  }

  private productById(id: string) {
    return this.products.find((p) => p.product_id === id)
  }

  private recomputeStatus(productId: string): void {
    const p = this.productById(productId)
    if (!p) return
    const next = p.stock > 0 ? 'ON_SALE' : 'SOLD_OUT'
    if (p.status !== next) {
      p.status = next
      this.emit('menu.availability_changed', { product_id: productId, status: next, available: p.stock })
    }
  }

  private toProduct(p: (typeof this.products)[number]): Product {
    const { stock: _stock, bom: _bom, ...rest } = p
    return rest
  }

  /* ---------- ApiClient ---------- */

  async health(): Promise<HealthStatus> {
    await this.latency()
    return { status: 'ok', version: 'mock-v1' }
  }

  async listInventory(_storeId?: string): Promise<InventoryItem[]> {
    await this.latency()
    return this.inventory.map((i) => ({
      ingredient_id: i.ingredient_id,
      name: i.name,
      physical: i.physical,
      defective: i.defective,
      reserved: i.reserved,
      available: i.physical - i.defective - i.reserved,
      unit: i.unit,
      tracking: i.tracking,
      updated_at: nowIso(),
    }))
  }

  async listMenu(_storeId?: string): Promise<Product[]> {
    await this.latency()
    return this.products.map((p) => this.toProduct(p))
  }

  async getMenuItem(productId: string, _storeId?: string): Promise<ProductDetail | null> {
    await this.latency()
    const p = this.productById(productId)
    return p ? { ...this.toProduct(p), bom: p.bom } : null
  }

  async createOrder(input: OrderCreateInput): Promise<Order> {
    await this.latency()

    // 校验在售与库存
    for (const item of input.items) {
      const p = this.productById(item.product_id)
      if (!p) throw new Error(`商品不存在：${item.product_id}`)
      if (p.status !== 'ON_SALE') throw new Error(`商品已售罄：${p.name}`)
      if (p.stock < item.quantity) throw new Error(`库存不足：${p.name}`)
    }

    const orderId = genId('OD')
    const now = nowIso()
    const activeCount = [...this.orderStates.values()].filter(
      (s) => !['COMPLETED', 'CANCELED'].includes(s.order.status),
    ).length
    const items = input.items.map((it) => {
      const p = this.productById(it.product_id)!
      p.stock -= it.quantity
      this.recomputeStatus(it.product_id)
      return {
        ...it,
        name: p.name,
        price_cent: p.price_cent,
        prep_time_sec: p.prep_time_sec,
        image: p.image,
      }
    })
    const total = items.reduce((sum, it) => sum + it.price_cent * it.quantity, 0)
    const maxPrep = Math.max(...items.map((it) => it.prep_time_sec))
    const waitSec = activeCount * rand(40, 90) + rand(20, 60)

    const order: Order = {
      order_id: orderId,
      store_id: input.store_id,
      customer_id: input.customer_id,
      status: 'CONFIRMED',
      items,
      total_price_cent: total,
      queue_position: activeCount + 1,
      estimated_ready_at: addSecIso(maxPrep + waitSec),
      created_at: now,
      updated_at: now,
    }
    const task: ProductionTask = {
      task_id: genId('TK'),
      order_id: orderId,
      status: 'PENDING',
      items,
      created_at: now,
    }

    this.orderStates.set(orderId, { order, task, timers: [] })
    this.logConsumption(items)
    this.emit('order.created', order)
    this.emit('production.task_created', task)
    this.emit('queue.updated', this.buildQueue())
    this.scheduleProgression(orderId)
    return order
  }

  private scheduleProgression(orderId: string): void {
    const state = this.orderStates.get(orderId)
    if (!state) return
    const advance = (status: Order['status'], taskStatus: ProductionTask['status'], topic: WsTopic, atSec: number) => {
      const timer = setTimeout(() => {
        const s = this.orderStates.get(orderId)
        if (!s || ['CANCELED', 'COMPLETED'].includes(s.order.status)) return
        s.order.status = status
        s.order.updated_at = nowIso()
        s.task.status = taskStatus
        if (taskStatus === 'PRODUCING') s.task.started_at = nowIso()
        if (taskStatus === 'READY') s.task.ready_at = nowIso()
        if (taskStatus === 'COMPLETED') s.task.completed_at = nowIso()
        this.emit(topic, s.task)
        this.emit('queue.updated', this.buildQueue())
      }, atSec * 1000)
      state.timers.push(timer)
    }
    advance('PRODUCING', 'PRODUCING', 'production.task_started', 3)
    advance('READY', 'READY', 'production.task_ready', 8)
    advance('COMPLETED', 'COMPLETED', 'production.task_completed', 14)
  }

  private clearTimers(state: MockOrderState): void {
    state.timers.forEach(clearTimeout)
    state.timers = []
  }

  async getOrder(orderId: string): Promise<Order | null> {
    await this.latency()
    return this.orderStates.get(orderId)?.order ?? null
  }

  async cancelOrder(orderId: string): Promise<Order> {
    await this.latency()
    const state = this.orderStates.get(orderId)
    if (!state) throw new Error(`订单不存在：${orderId}`)
    if (['COMPLETED', 'CANCELED'].includes(state.order.status)) throw new Error('订单状态不允许取消')
    this.clearTimers(state)
    state.order.status = 'CANCELED'
    state.order.updated_at = nowIso()
    state.task.status = 'COMPLETED'
    state.task.completed_at = nowIso()
    // 释放库存
    for (const it of state.order.items) {
      const p = this.productById(it.product_id)
      if (p) {
        p.stock += it.quantity
        this.recomputeStatus(it.product_id)
      }
    }
    this.emit('inventory.released', { order_id: orderId })
    this.emit('queue.updated', this.buildQueue())
    return state.order
  }

  async listProductionTasks(): Promise<ProductionTask[]> {
    await this.latency()
    return [...this.orderStates.values()]
      .map((s) => ({ ...s.task, items: [...s.task.items] }))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
  }

  private async transitionTask(taskId: string, status: ProductionTask['status'], topic: WsTopic): Promise<ProductionTask> {
    await this.latency()
    const state = [...this.orderStates.values()].find((s) => s.task.task_id === taskId)
    if (!state) throw new Error(`任务不存在：${taskId}`)
    this.clearTimers(state)
    state.task.status = status
    if (status === 'PRODUCING') state.task.started_at = nowIso()
    if (status === 'READY') state.task.ready_at = nowIso()
    if (status === 'COMPLETED') state.task.completed_at = nowIso()
    state.order.status = status === 'PRODUCING' ? 'PRODUCING' : status === 'READY' ? 'READY' : 'COMPLETED'
    state.order.updated_at = nowIso()
    this.emit(topic, state.task)
    this.emit('queue.updated', this.buildQueue())
    return { ...state.task, items: [...state.task.items] }
  }

  async startTask(taskId: string): Promise<ProductionTask> {
    return this.transitionTask(taskId, 'PRODUCING', 'production.task_started')
  }

  async readyTask(taskId: string): Promise<ProductionTask> {
    return this.transitionTask(taskId, 'READY', 'production.task_ready')
  }

  async completeTask(taskId: string): Promise<ProductionTask> {
    return this.transitionTask(taskId, 'COMPLETED', 'production.task_completed')
  }

  private buildQueue(): QueueSnapshot {
    const parties = [...this.orderStates.values()]
      .filter((s) => !['COMPLETED', 'CANCELED'].includes(s.order.status))
      .sort((a, b) => a.order.created_at.localeCompare(b.order.created_at))
      .map((s, idx) => {
        const waiting = Math.max(0, Math.round((Date.now() - new Date(s.order.created_at).getTime()) / 1000))
        return {
          party_id: s.order.order_id,
          status: s.order.status === 'READY' ? 'READY' : 'WAITING',
          waiting_sec: waiting,
          eta_sec: Math.max(0, Math.round((new Date(s.order.estimated_ready_at).getTime() - Date.now()) / 1000)),
          position: idx + 1,
        } as QueuePartyWithPosition
      })
    return { store_id: STORE_ID, parties, updated_at: nowIso() }
  }

  async listQueueSnapshots(_storeId: string): Promise<QueueSnapshot> {
    await this.latency()
    return this.buildQueue()
  }

  async listAlarms(_storeId: string): Promise<Alarm[]> {
    await this.latency()
    return this.alarms.map((a) => ({ ...a }))
  }

  async acknowledgeAlarm(alarmId: string): Promise<Alarm> {
    await this.latency()
    const alarm = this.alarms.find((a) => a.alarm_id === alarmId)
    if (!alarm) throw new Error(`告警不存在：${alarmId}`)
    if (alarm.status === 'OPEN') {
      alarm.status = 'ACKNOWLEDGED'
      alarm.acknowledged_at = nowIso()
      this.emit('alarm.acknowledged', alarm)
    }
    return { ...alarm }
  }

  async resolveAlarm(alarmId: string): Promise<Alarm> {
    await this.latency()
    const alarm = this.alarms.find((a) => a.alarm_id === alarmId)
    if (!alarm) throw new Error(`告警不存在：${alarmId}`)
    if (alarm.status !== 'RESOLVED') {
      alarm.status = 'RESOLVED'
      alarm.acknowledged_at = alarm.acknowledged_at ?? nowIso()
      alarm.resolved_at = nowIso()
      this.emit('alarm.resolved', alarm)
    }
    return { ...alarm }
  }

  async getAnalyticsSummary(_storeId: string, start: string, end: string): Promise<AnalyticsSummary> {
    await this.latency()
    const states = [...this.orderStates.values()]
    const revenue = states.reduce((sum, s) => sum + s.order.total_price_cent, 0)
    const orderCount = states.length
    const waiting = states
      .filter((s) => ['CONFIRMED', 'PRODUCING'].includes(s.order.status))
      .map((s) => Math.max(0, (new Date(s.order.estimated_ready_at).getTime() - Date.now()) / 1000))
    const avgWait = waiting.length
      ? Math.round(waiting.reduce((a, b) => a + b, 0) / waiting.length)
      : rand(120, 260)
    const soldOut = this.products.filter((p) => p.status === 'SOLD_OUT').length
    const openAlarms = this.alarms.filter((a) => a.status === 'OPEN').length

    return {
      store_id: STORE_ID,
      period: { start, end },
      orders: orderCount,
      revenue_cent: revenue,
      avg_order_cent: orderCount ? Math.round(revenue / orderCount) : 0,
      active_parties: this.buildQueue().parties.length,
      avg_wait_sec: avgWait,
      sold_out_count: soldOut,
      open_alarms: openAlarms,
      online_devices: 8,
      total_devices: 9,
      kpis: [
        { label: '今日订单', value: 120 + orderCount, unit: '单' },
        { label: '营业额', value: 368400 + revenue, unit: '分' },
        { label: '平均等待', value: avgWait, unit: '秒' },
        { label: '设备在线率', value: 89, unit: '%' },
      ],
    }
  }

  /* ---------- 扩展：订单列表 / 设备 / 质检 / 客流 / 流水 ---------- */

  async listOrders(_storeId?: string, status?: Order['status']): Promise<Order[]> {
    await this.latency()
    const live = [...this.orderStates.values()].map((s) => s.order)
    const all = [...live, ...this.historicalOrders].sort((a, b) => b.created_at.localeCompare(a.created_at))
    return status ? all.filter((o) => o.status === status) : all
  }

  async listDevices(_storeId?: string): Promise<Device[]> {
    await this.latency()
    return this.devices.map((d) => ({ ...d, metrics: d.metrics ? { ...d.metrics } : undefined }))
  }

  async issueDeviceCommand(deviceId: string, command: DeviceCommand): Promise<Device> {
    await this.latency()
    const d = this.devices.find((x) => x.device_id === deviceId)
    if (!d) throw new Error(`设备不存在：${deviceId}`)
    if (command.command === 'SET_TEMP' && command.value !== undefined) {
      d.target_temp_c = command.value
      d.temperature_c = command.value
      d.status = 'ONLINE'
    } else if (command.command === 'REBOOT') {
      d.status = 'OFFLINE'
      d.last_seen_at = nowIso()
      setTimeout(() => {
        d.status = 'ONLINE'
        d.online_since = nowIso()
        d.last_seen_at = nowIso()
        this.emit('device.command_result', d)
      }, 2500)
    } else {
      d.status = 'ONLINE'
    }
    d.last_seen_at = nowIso()
    this.emit('device.command_result', d)
    return { ...d, metrics: d.metrics ? { ...d.metrics } : undefined }
  }

  async listQualityEvents(_storeId?: string): Promise<QualityEvent[]> {
    await this.latency()
    return this.qualityEvents.map((q) => ({ ...q }))
  }

  async handleQualityEvent(eventId: string, status: 'INSPECTING' | 'HANDLED'): Promise<QualityEvent> {
    await this.latency()
    const q = this.qualityEvents.find((x) => x.event_id === eventId)
    if (!q) throw new Error(`质检事件不存在：${eventId}`)
    q.status = status
    if (status === 'HANDLED') q.handled_at = nowIso()
    this.emit('quality.abnormal', q)
    return { ...q }
  }

  async getTrafficSummary(_storeId: string): Promise<TrafficSummary> {
    await this.latency()
    const hourly = buildHourly()
    const peak = hourly.reduce((best, p) => (p.parties > best.parties ? p : best), hourly[0])
    return {
      store_id: STORE_ID,
      hourly,
      peak_hour: peak.hour,
      avg_daily_parties: 168,
      today_parties: this.buildQueue().parties.length + 64,
    }
  }

  async getCategoryBreakdown(_storeId: string): Promise<CategoryShare[]> {
    await this.latency()
    return buildCategoryBreakdown()
  }

  async listInventoryMovements(_storeId?: string): Promise<InventoryMovement[]> {
    await this.latency()
    return this.movements.map((m) => ({ ...m }))
  }

  private logConsumption(items: { product_id: string; quantity: number }[]): void {
    const stamp = nowIso()
    for (const it of items) {
      const p = this.productById(it.product_id)
      if (!p) continue
      for (const bom of p.bom) {
        if (bom.unlimited) continue
        this.movements.unshift({
          movement_id: genId('MV'),
          ingredient_id: bom.ingredient_id,
          name: bom.name,
          delta: -(bom.quantity * it.quantity),
          unit: bom.unit,
          reason: 'CONSUME',
          occurred_at: stamp,
        })
      }
    }
    this.movements = this.movements.slice(0, 60)
  }
}

interface QueuePartyWithPosition {
  party_id: string
  status: 'WAITING' | 'READY'
  waiting_sec: number
  eta_sec: number
  position: number
}
