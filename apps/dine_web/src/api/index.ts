import { HttpApiClient } from './client'
import type { ApiClient } from './client'
import { MockApiClient } from './mock/adapter'
import { MockRealtimeClient } from './mock/realtime'
import { HttpRealtimeClient } from './ws'
import type { RealtimeClient } from './ws'

/**
 * 数据源选择：
 * - 默认使用 Mock（视觉与演示阶段）；
 * - 设置 VITE_USE_MOCK=false 且 Core 就绪后，切换为真实 HTTP/WS 客户端。
 */
const useMock = import.meta.env.VITE_USE_MOCK !== 'false'

let mockClient: MockApiClient | null = null
function getMock(): MockApiClient {
  mockClient ??= new MockApiClient()
  return mockClient
}

export const api: ApiClient = useMock ? getMock() : new HttpApiClient()
export const realtime: RealtimeClient = useMock ? new MockRealtimeClient(getMock()) : new HttpRealtimeClient()
