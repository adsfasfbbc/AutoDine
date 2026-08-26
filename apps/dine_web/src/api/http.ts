import type { ApiEnvelope } from './types'

export class ApiError extends Error {
  readonly code: number
  readonly status: number
  readonly requestId?: string

  constructor(message: string, code: number, status: number, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/**
 * 统一信封请求封装（契约：code/message/request_id/timestamp/data）。
 * - HTTP 非 2xx 或 envelope.code !== 0 时抛出 ApiError。
 * - 10s 超时自动中止。
 */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10_000)
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    })
    let envelope: ApiEnvelope<T> | undefined
    try {
      envelope = (await res.json()) as ApiEnvelope<T>
    } catch {
      /* 非 JSON 响应（如健康检查） */
    }
    if (!res.ok || !envelope || envelope.code !== 0) {
      throw new ApiError(
        envelope?.message ?? `HTTP ${res.status} ${res.statusText}`,
        envelope?.code ?? res.status,
        res.status,
        envelope?.request_id,
      )
    }
    return envelope.data
  } finally {
    clearTimeout(timer)
  }
}
