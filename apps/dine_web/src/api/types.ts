/**
 * 契约层类型定义
 * 对齐团队仓库 contracts/openapi/autodine-core-v1.yaml 与
 * 《autoDine_菜单与BOM数据规范_开发交付版_v1.0.docx》。
 * 字段命名沿用 ADP v1.0 snake_case 约定。
 */

/** 统一响应信封（契约：code/message/request_id/timestamp/data） */
export interface ApiEnvelope<T> {
  code: number
  message: string
  request_id: string
  timestamp: string
  data: T
}

export type ProductStatus = 'ON_SALE' | 'SOLD_OUT' | 'HIDDEN'
export type ProductCategory = 'DRINK' | 'CUP_DESSERT' | 'CAKE' | 'HOT_FOOD' | 'LIGHT_MEAL'
export type Allergen = 'MILK' | 'EGG' | 'GLUTEN' | 'SOY' | 'SEAFOOD' | 'PEANUT' | 'TREE_NUT'

export interface Product {
  product_id: string
  name: string
  category: ProductCategory
  price_cent: number
  calories_kcal: number
  serving_size: string
  prep_time_sec: number
  status: ProductStatus
  tags: string[]
  allergens: Allergen[]
  image?: string
  description?: string
}

export interface BomItem {
  ingredient_id: string
  name: string
  quantity: number
  unit: 'pcs' | 'g' | 'ml'
  /** 契约约定：[UNLIMITED] 原料不参与可售量计算 */
  unlimited?: boolean
}

export interface ProductDetail extends Product {
  bom: BomItem[]
}

export type TrackingMode = 'TRACKED' | 'UNLIMITED'

export interface InventoryItem {
  ingredient_id: string
  name: string
  physical: number
  defective: number
  reserved: number
  /** 契约约定：available = physical - defective - reserved */
  available: number
  unit: 'pcs' | 'g' | 'ml'
  tracking: TrackingMode
  updated_at: string
}

export interface OrderItemInput {
  product_id: string
  quantity: number
}

export interface OrderCreateInput {
  store_id: string
  customer_id?: string
  idempotency_key: string
  items: OrderItemInput[]
}

export type OrderStatus = 'PENDING' | 'CONFIRMED' | 'PRODUCING' | 'READY' | 'COMPLETED' | 'CANCELED'

export interface OrderItem extends OrderItemInput {
  name: string
  price_cent: number
  prep_time_sec: number
  image?: string
}

export interface Order {
  order_id: string
  store_id: string
  customer_id?: string
  status: OrderStatus
  items: OrderItem[]
  total_price_cent: number
  queue_position: number
  estimated_ready_at: string
  created_at: string
  updated_at: string
}

export type QueuePartyStatus = 'WAITING' | 'READY' | 'PICKED_UP'

export interface QueueParty {
  party_id: string
  status: QueuePartyStatus
  waiting_sec: number
  eta_sec: number
}

export interface QueueSnapshot {
  store_id: string
  parties: QueueParty[]
  updated_at: string
}

export type AlarmSeverity = 'INFO' | 'WARNING' | 'CRITICAL'
export type AlarmStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
export type AlarmCategory = 'DEVICE' | 'INVENTORY' | 'QUALITY' | 'QUEUE' | 'OTHER'

export interface Alarm {
  alarm_id: string
  store_id: string
  severity: AlarmSeverity
  category: AlarmCategory
  title: string
  message: string
  status: AlarmStatus
  created_at: string
  acknowledged_at?: string
  resolved_at?: string
}

export type ProductionTaskStatus = 'PENDING' | 'PRODUCING' | 'READY' | 'COMPLETED'

export interface ProductionTask {
  task_id: string
  order_id: string
  status: ProductionTaskStatus
  items: OrderItem[]
  started_at?: string
  ready_at?: string
  completed_at?: string
  created_at: string
}

export interface KpiMetric {
  label: string
  value: number
  unit?: string
  delta?: number
}

export interface AnalyticsSummary {
  store_id: string
  period: { start: string; end: string }
  orders: number
  revenue_cent: number
  avg_order_cent: number
  active_parties: number
  avg_wait_sec: number
  sold_out_count: number
  open_alarms: number
  online_devices: number
  total_devices: number
  kpis: KpiMetric[]
}

export interface HealthStatus {
  status: string
  version?: string
}

/* ---------- 设备 ---------- */

export type DeviceStatus = 'ONLINE' | 'OFFLINE' | 'ERROR' | 'MAINTENANCE'
export type DeviceKind =
  | 'COOLER'
  | 'OVEN'
  | 'FRYER'
  | 'ICE_MAKER'
  | 'DISPENSER'
  | 'SENSOR'
  | 'ROBOT'
  | 'PICKUP'

export interface Device {
  device_id: string
  name: string
  kind: DeviceKind
  location: string
  status: DeviceStatus
  temperature_c?: number
  target_temp_c?: number
  online_since?: string
  last_seen_at: string
  metrics?: Record<string, number>
}

export interface DeviceCommand {
  command: 'SET_TEMP' | 'REBOOT' | 'SELF_CHECK' | 'PING'
  value?: number
  store_id?: string
}

/* ---------- 质检 ---------- */

export type QualityEventStatus = 'OPEN' | 'INSPECTING' | 'HANDLED'
export type QualityEventType = 'VISUAL_DEFECT' | 'TEMP_ABNORMAL' | 'EXPIRY' | 'CONTAMINATION'

export interface QualityEvent {
  event_id: string
  ingredient_id: string
  ingredient_name: string
  type: QualityEventType
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  quantity: number
  unit: string
  note: string
  status: QualityEventStatus
  detected_at: string
  handled_at?: string
  source: string
}

/* ---------- 客流与经营分析 ---------- */

export interface HourlyPoint {
  hour: number
  orders: number
  revenue_cent: number
  parties: number
}

export interface TrafficSummary {
  store_id: string
  hourly: HourlyPoint[]
  peak_hour: number
  avg_daily_parties: number
  today_parties: number
}

export interface CategoryShare {
  category: ProductCategory
  label: string
  orders: number
  revenue_cent: number
}

/* ---------- 库存流水 ---------- */

export type MovementReason = 'CONSUME' | 'RESTOCK' | 'WASTE' | 'ADJUST' | 'VISUAL_CORRECTION'

export interface InventoryMovement {
  movement_id: string
  ingredient_id: string
  name: string
  delta: number
  unit: 'pcs' | 'g' | 'ml'
  reason: MovementReason
  occurred_at: string
}
