import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/api'
import type { Order, OrderItemInput } from '@/api/types'

const STORE_ID = 'store-main'

/** 订单：下单、当前订单状态与最近订单 */
export const useOrderStore = defineStore('order', () => {
  const currentOrder = ref<Order | null>(null)
  const recentOrders = ref<Order[]>([])
  const submitting = ref(false)
  const lastError = ref<string | null>(null)

  async function placeOrder(items: OrderItemInput[]): Promise<Order> {
    submitting.value = true
    lastError.value = null
    try {
      const order = await api.createOrder({
        store_id: STORE_ID,
        customer_id: 'demo-customer',
        idempotency_key: crypto.randomUUID(),
        items,
      })
      currentOrder.value = order
      recentOrders.value = [order, ...recentOrders.value.filter((o) => o.order_id !== order.order_id)].slice(0, 8)
      return order
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      submitting.value = false
    }
  }

  async function refresh(orderId: string): Promise<void> {
    const order = await api.getOrder(orderId)
    if (order) {
      currentOrder.value = order
      const idx = recentOrders.value.findIndex((o) => o.order_id === orderId)
      if (idx >= 0) recentOrders.value[idx] = order
    }
  }

  function applyStatus(orderId: string, status: Order['status']): void {
    if (currentOrder.value?.order_id === orderId) currentOrder.value.status = status
    const o = recentOrders.value.find((x) => x.order_id === orderId)
    if (o) o.status = status
  }

  return { currentOrder, recentOrders, submitting, lastError, placeOrder, refresh, applyStatus }
})
