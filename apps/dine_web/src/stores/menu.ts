import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/api'
import type { Product, ProductStatus } from '@/api/types'

/** 菜单投影：由 Mock / Core 菜单接口驱动，监听可用性事件即时更新 */
export const useMenuStore = defineStore('menu', () => {
  const products = ref<Product[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    loading.value = true
    error.value = null
    try {
      products.value = await api.listMenu()
      loaded.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  const byId = computed(() => new Map(products.value.map((p) => [p.product_id, p])))

  function updateFromEvent(payload: { product_id: string; status: ProductStatus; available?: number }): void {
    const target = products.value.find((p) => p.product_id === payload.product_id)
    if (target) target.status = payload.status
  }

  return { products, loading, loaded, error, load, byId, updateFromEvent }
})
