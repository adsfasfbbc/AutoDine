/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 是否启用 Mock 数据源；'false' 时切换为真实 HTTP 客户端 */
  readonly VITE_USE_MOCK?: string
  /** 真实 Core API 基地址，默认 http://localhost:8000 */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
