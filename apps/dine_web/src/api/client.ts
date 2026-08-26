import { request } from './http'
import type {
  Alarm,
  AnalyticsSummary,
  CategoryShare,
  Device,
  DeviceCommand,
  HealthStatus,
  InventoryItem,
  InventoryMovement,
  Order,
  OrderCreateInput,
  OrderStatus,
  ProductionTask,
  Product,
  ProductDetail,
  QualityEvent,
  QueueSnapshot,
  TrafficSummary,
} from './types'

export interface ApiClient {
  health(): Promise<HealthStatus>
  listInventory(storeId?: string): Promise<InventoryItem[]>
  listMenu(storeId?: string): Promise<Product[]>
  getMenuItem(productId: string, storeId?: string): Promise<ProductDetail | null>
  createOrder(input: OrderCreateInput): Promise<Order>
  getOrder(orderId: string): Promise<Order | null>
  cancelOrder(orderId: string): Promise<Order>
  listOrders(storeId?: string, status?: OrderStatus): Promise<Order[]>
  listProductionTasks(): Promise<ProductionTask[]>
  startTask(taskId: string): Promise<ProductionTask>
  readyTask(taskId: string): Promise<ProductionTask>
  completeTask(taskId: string): Promise<ProductionTask>
  listQueueSnapshots(storeId: string): Promise<QueueSnapshot>
  listDevices(storeId?: string): Promise<Device[]>
  issueDeviceCommand(deviceId: string, command: DeviceCommand): Promise<Device>
  listQualityEvents(storeId?: string): Promise<QualityEvent[]>
  handleQualityEvent(eventId: string, status: 'INSPECTING' | 'HANDLED'): Promise<QualityEvent>
  listAlarms(storeId: string): Promise<Alarm[]>
  acknowledgeAlarm(alarmId: string): Promise<Alarm>
  resolveAlarm(alarmId: string): Promise<Alarm>
  getAnalyticsSummary(storeId: string, start: string, end: string): Promise<AnalyticsSummary>
  getTrafficSummary(storeId: string): Promise<TrafficSummary>
  getCategoryBreakdown(storeId: string): Promise<CategoryShare[]>
  listInventoryMovements(storeId?: string): Promise<InventoryMovement[]>
}

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return `?${entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')}`
}

/**
 * 真实 Core API 客户端。
 * 路径与 operationId 对齐 contracts/openapi/autodine-core-v1.yaml。
 */
export class HttpApiClient implements ApiClient {
  async health(): Promise<HealthStatus> {
    return request<HealthStatus>('/health')
  }

  async listInventory(storeId?: string): Promise<InventoryItem[]> {
    return request<InventoryItem[]>(`/api/v1/inventory${qs({ store_id: storeId })}`)
  }

  async listMenu(storeId?: string): Promise<Product[]> {
    return request<Product[]>(`/api/v1/menu${qs({ store_id: storeId })}`)
  }

  async getMenuItem(productId: string, storeId?: string): Promise<ProductDetail | null> {
    return request<ProductDetail>(`/api/v1/menu/${encodeURIComponent(productId)}${qs({ store_id: storeId })}`)
  }

  async createOrder(input: OrderCreateInput): Promise<Order> {
    return request<Order>('/api/v1/orders', { method: 'POST', body: JSON.stringify(input) })
  }

  async getOrder(orderId: string): Promise<Order | null> {
    return request<Order>(`/api/v1/orders/${encodeURIComponent(orderId)}`)
  }

  async cancelOrder(orderId: string): Promise<Order> {
    return request<Order>(`/api/v1/orders/${encodeURIComponent(orderId)}/cancel`, { method: 'POST' })
  }

  /** OpenAPI v1 未提供任务列表端点，真实接入前标记为未实现 */
  async listProductionTasks(): Promise<ProductionTask[]> {
    throw new Error('listProductionTasks: 契约 v1 未定义任务列表端点，请使用 Mock 或后续契约版本')
  }

  async startTask(taskId: string): Promise<ProductionTask> {
    return request<ProductionTask>(`/api/v1/production/tasks/${encodeURIComponent(taskId)}/start`, { method: 'POST' })
  }

  async readyTask(taskId: string): Promise<ProductionTask> {
    return request<ProductionTask>(`/api/v1/production/tasks/${encodeURIComponent(taskId)}/ready`, { method: 'POST' })
  }

  async completeTask(taskId: string): Promise<ProductionTask> {
    return request<ProductionTask>(`/api/v1/production/tasks/${encodeURIComponent(taskId)}/complete`, { method: 'POST' })
  }

  /** 契约 v1 未定义订单列表端点，管理端使用 Mock 或后续契约版本 */
  async listOrders(_storeId?: string, _status?: OrderStatus): Promise<Order[]> {
    throw new Error('listOrders: 契约 v1 未定义订单列表端点，请使用 Mock 或后续契约版本')
  }

  /** 契约 v1 未定义设备列表端点 */
  async listDevices(_storeId?: string): Promise<Device[]> {
    throw new Error('listDevices: 契约 v1 未定义设备列表端点，请使用 Mock 或后续契约版本')
  }

  async issueDeviceCommand(deviceId: string, command: DeviceCommand): Promise<Device> {
    return request<Device>(`/api/v1/devices/${encodeURIComponent(deviceId)}/commands`, {
      method: 'POST',
      body: JSON.stringify(command),
    })
  }

  /** 质检事件列表为 Mock 扩展能力（实时事件走 quality.abnormal 主题） */
  async listQualityEvents(_storeId?: string): Promise<QualityEvent[]> {
    throw new Error('listQualityEvents: 契约 v1 未定义质检列表端点，请使用 Mock 或后续契约版本')
  }

  async handleQualityEvent(_eventId: string, _status: 'INSPECTING' | 'HANDLED'): Promise<QualityEvent> {
    throw new Error('handleQualityEvent: 契约 v1 未定义质检处理端点，请使用 Mock 或后续契约版本')
  }

  async getTrafficSummary(_storeId: string): Promise<TrafficSummary> {
    throw new Error('getTrafficSummary: 契约 v1 未定义客流汇总端点，请使用 Mock 或后续契约版本')
  }

  async getCategoryBreakdown(_storeId: string): Promise<CategoryShare[]> {
    throw new Error('getCategoryBreakdown: 契约 v1 未定义品类构成端点，请使用 Mock 或后续契约版本')
  }

  async listInventoryMovements(_storeId?: string): Promise<InventoryMovement[]> {
    throw new Error('listInventoryMovements: 契约 v1 未定义库存流水端点，请使用 Mock 或后续契约版本')
  }

  async listQueueSnapshots(storeId: string): Promise<QueueSnapshot> {
    return request<QueueSnapshot>(`/api/v1/queues/${encodeURIComponent(storeId)}`)
  }

  async listAlarms(storeId: string): Promise<Alarm[]> {
    return request<Alarm[]>(`/api/v1/alarms${qs({ store_id: storeId })}`)
  }

  async acknowledgeAlarm(alarmId: string): Promise<Alarm> {
    return request<Alarm>(`/api/v1/alarms/${encodeURIComponent(alarmId)}/acknowledge`, { method: 'POST' })
  }

  async resolveAlarm(alarmId: string): Promise<Alarm> {
    return request<Alarm>(`/api/v1/alarms/${encodeURIComponent(alarmId)}/resolve`, { method: 'POST' })
  }

  async getAnalyticsSummary(storeId: string, start: string, end: string): Promise<AnalyticsSummary> {
    return request<AnalyticsSummary>(`/api/v1/analytics/summary${qs({ store_id: storeId, start, end })}`)
  }
}
