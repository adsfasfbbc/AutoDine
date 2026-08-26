/**
 * 实时事件客户端
 * 对齐团队仓库 contracts/websocket/topics.yaml（v1）：
 * endpoint /ws/stores/{store_id}，消息为 ADP 兼容信封。
 */

export const WS_TOPICS = [
  'vision.storage.detected',
  'vision.storage.security',
  'vision.front.queue',
  'inventory.changed',
  'inventory.reserved',
  'inventory.released',
  'menu.availability_changed',
  'order.created',
  'production.task_created',
  'production.task_started',
  'production.task_ready',
  'production.task_completed',
  'queue.updated',
  'device.command',
  'device.command_result',
  'quality.abnormal',
  'robot.status',
  'alarm.opened',
  'alarm.acknowledged',
  'alarm.resolved',
  'alarm.updated',
] as const

export type WsTopic = (typeof WS_TOPICS)[number]

export interface WsMessage<T = unknown> {
  topic: WsTopic
  store_id: string
  payload: T
  occurred_at: string
}

export type WsHandler<T = unknown> = (msg: WsMessage<T>) => void

export interface RealtimeClient {
  connect(): void
  disconnect(): void
  /** 订阅主题，返回取消订阅函数 */
  on<T = unknown>(topic: WsTopic, handler: WsHandler<T>): () => void
}

const WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000').replace(/\/+$/, '')

/** 真实 WebSocket 实现（按 store_id 订阅 /ws/stores/{store_id}） */
export class HttpRealtimeClient implements RealtimeClient {
  private ws: WebSocket | null = null
  private handlers = new Map<WsTopic, Set<WsHandler>>()
  private storeId: string
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private closedByUser = false

  constructor(storeId = 'store-main') {
    this.storeId = storeId
  }

  connect(): void {
    this.closedByUser = false
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return
    this.ws = new WebSocket(`${WS_BASE_URL}/ws/stores/${this.storeId}`)
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsMessage
        if (!msg || typeof msg.topic !== 'string') return
        this.handlers.get(msg.topic as WsTopic)?.forEach((h) => h(msg))
      } catch {
        /* 忽略无法解析的消息 */
      }
    }
    this.ws.onclose = () => {
      if (!this.closedByUser) {
        this.retryTimer = setTimeout(() => this.connect(), 3_000)
      }
    }
  }

  disconnect(): void {
    this.closedByUser = true
    if (this.retryTimer) clearTimeout(this.retryTimer)
    this.ws?.close()
    this.ws = null
  }

  on<T = unknown>(topic: WsTopic, handler: WsHandler<T>): () => void {
    let set = this.handlers.get(topic)
    if (!set) {
      set = new Set()
      this.handlers.set(topic, set)
    }
    set.add(handler as WsHandler)
    return () => {
      set?.delete(handler as WsHandler)
    }
  }
}
