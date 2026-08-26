import type { MockApiClient } from './adapter'
import type { RealtimeClient, WsHandler, WsMessage, WsTopic } from '../ws'

/** Mock 实时客户端：直接桥接 MockApiClient 的事件发射器 */
export class MockRealtimeClient implements RealtimeClient {
  constructor(private readonly source: MockApiClient) {}

  connect(): void {
    /* mock 无需连接 */
  }

  disconnect(): void {
    /* noop */
  }

  on<T = unknown>(topic: WsTopic, handler: WsHandler<T>): () => void {
    return this.source.onTopic(topic, handler as (msg: WsMessage) => void)
  }
}
