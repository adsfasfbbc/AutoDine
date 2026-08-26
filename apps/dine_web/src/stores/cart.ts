import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { Product } from '@/api/types'

export interface CartLine {
  product: Product
  quantity: number
}

/** 持久购物车：菜单浏览时右侧持续显示 */
export const useCartStore = defineStore('cart', () => {
  const lines = ref<CartLine[]>([])

  const totalCount = computed(() => lines.value.reduce((n, l) => n + l.quantity, 0))
  const totalPriceCent = computed(() => lines.value.reduce((n, l) => n + l.product.price_cent * l.quantity, 0))
  const maxPrepSec = computed(() => Math.max(0, ...lines.value.map((l) => l.product.prep_time_sec)))
  const isEmpty = computed(() => lines.value.length === 0)

  function add(product: Product, quantity = 1): void {
    if (product.status !== 'ON_SALE') return
    const line = lines.value.find((l) => l.product.product_id === product.product_id)
    if (line) line.quantity += quantity
    else lines.value.push({ product, quantity })
  }

  function setQuantity(productId: string, quantity: number): void {
    const line = lines.value.find((l) => l.product.product_id === productId)
    if (!line) return
    if (quantity <= 0) {
      lines.value = lines.value.filter((l) => l.product.product_id !== productId)
    } else {
      line.quantity = quantity
    }
  }

  function remove(productId: string): void {
    lines.value = lines.value.filter((l) => l.product.product_id !== productId)
  }

  function clear(): void {
    lines.value = []
  }

  return {
    lines,
    totalCount,
    totalPriceCent,
    maxPrepSec,
    isEmpty,
    add,
    setQuantity,
    remove,
    clear,
  }
})
