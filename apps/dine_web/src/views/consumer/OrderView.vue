<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, realtime } from '@/api'
import type { OrderStatus } from '@/api/types'
import type { WsTopic } from '@/api/ws'
import ProductImage from '@/components/ProductImage.vue'
import { useOrderStore } from '@/stores/order'
import { formatPriceCent, pickupCode } from '@/utils/format'

const orderStore = useOrderStore()
const router = useRouter()

const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
let unsubscribes: (() => void)[] = []

const order = computed(() => orderStore.currentOrder)

const steps: { key: OrderStatus; label: string; hint: string }[] = [
  { key: 'CONFIRMED', label: '已确认', hint: '订单已受理' },
  { key: 'PRODUCING', label: '制作中', hint: '后厨正在制作' },
  { key: 'READY', label: '待取餐', hint: '请前往取餐口' },
  { key: 'COMPLETED', label: '已完成', hint: '取餐完成' },
]

const stepIndex = computed(() => {
  if (!order.value) return -1
  const idx = steps.findIndex((s) => s.key === order.value!.status)
  return idx >= 0 ? idx : 0
})

const waitSec = computed(() => {
  if (!order.value || ['READY', 'COMPLETED', 'CANCELED'].includes(order.value.status)) return 0
  return Math.max(0, Math.round((new Date(order.value.estimated_ready_at).getTime() - now.value) / 1000))
})

const statusLabel: Record<OrderStatus, string> = {
  PENDING: '等待确认',
  CONFIRMED: '已确认',
  PRODUCING: '制作中',
  READY: '待取餐',
  COMPLETED: '已完成',
  CANCELED: '已取消',
}

onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 1000)
  const subscribe = (topic: WsTopic, status: OrderStatus) => {
    unsubscribes.push(
      realtime.on(topic, (msg) => {
        const payload = msg.payload as { order_id?: string }
        if (payload.order_id) orderStore.applyStatus(payload.order_id, status)
      }),
    )
  }
  subscribe('production.task_started', 'PRODUCING')
  subscribe('production.task_ready', 'READY')
  subscribe('production.task_completed', 'COMPLETED')
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  unsubscribes.forEach((off) => off())
  unsubscribes = []
})

async function cancelOrder(): Promise<void> {
  if (!order.value) return
  try {
    await api.cancelOrder(order.value.order_id)
    orderStore.refresh(order.value.order_id)
  } catch {
    /* 忽略取消失败提示，保持现状 */
  }
}
</script>

<template>
  <div class="anim-fade mx-auto max-w-4xl space-y-6">
    <!-- 当前订单 -->
    <section v-if="order" class="card overflow-hidden">
      <header class="flex items-center justify-between border-b border-line bg-paper/60 px-8 py-5">
        <div>
          <p class="eyebrow">Order</p>
          <h2 class="mt-1 font-display text-xl font-semibold text-brand-950">
            订单 {{ order.order_id }}
            <span class="ml-2 align-middle text-sm font-sans text-ink-400">{{ statusLabel[order.status] }}</span>
          </h2>
        </div>
        <div class="text-right">
          <p class="text-[11px] uppercase tracking-widest text-ink-400">取餐码</p>
          <p class="font-display text-3xl font-semibold tracking-[0.3em] text-accent-600">{{ pickupCode(order.order_id) }}</p>
        </div>
      </header>

      <!-- 状态进度 -->
      <div class="px-8 py-7">
        <div class="flex items-center">
          <template v-for="(step, i) in steps" :key="step.key">
            <div class="flex flex-col items-center" style="width: 72px">
              <span
                class="grid size-9 place-items-center rounded-full border-2 text-sm font-semibold transition-colors"
                :class="i < stepIndex ? 'border-success-500 bg-success-500 text-white' : i === stepIndex ? 'border-accent-500 bg-accent-50 text-accent-600' : 'border-line bg-surface text-ink-300'"
              >
                <svg v-if="i < stepIndex" viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="m5 13 4 4L19 7" />
                </svg>
                <span v-else>{{ i + 1 }}</span>
              </span>
              <span class="mt-2 text-xs font-medium" :class="i === stepIndex ? 'text-accent-600' : i < stepIndex ? 'text-ink-900' : 'text-ink-300'">
                {{ step.label }}
              </span>
            </div>
            <div
              v-if="i < steps.length - 1"
              class="mx-1 h-0.5 flex-1 rounded-full"
              :class="i < stepIndex ? 'bg-success-500' : 'bg-line'"
            />
          </template>
        </div>
        <div class="mt-4 flex items-center justify-between text-xs text-ink-400">
          <span>排队位置：{{ order.queue_position }}</span>
          <span v-if="waitSec > 0">预计 {{ Math.ceil(waitSec / 60) }} 分钟内可取餐</span>
        </div>
      </div>

      <!-- 商品清单 -->
      <ul class="divide-y divide-line border-t border-line px-8">
        <li v-for="item in order.items" :key="item.product_id" class="flex items-center gap-4 py-4">
          <ProductImage :src="item.image" :alt="item.name" rounded="rounded-xl" class="size-14 shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-ink-900">{{ item.name }}</p>
            <p class="text-xs text-ink-400">× {{ item.quantity }}</p>
          </div>
          <span class="text-sm font-medium text-ink-900 tabular-nums">{{ formatPriceCent(item.price_cent * item.quantity) }}</span>
        </li>
      </ul>

      <footer class="flex items-center justify-between border-t border-line px-8 py-5">
        <button v-if="order.status === 'CONFIRMED' || order.status === 'PRODUCING'" class="btn-ghost !py-1.5 text-xs" @click="cancelOrder">
          取消订单
        </button>
        <span v-else class="text-xs text-ink-300">{{ order.created_at.slice(0, 16).replace('T', ' ') }} 下单</span>
        <div class="flex items-center gap-3">
          <span class="text-sm text-ink-500">合计</span>
          <span class="font-display text-2xl font-semibold text-ink-900 tabular-nums">{{ formatPriceCent(order.total_price_cent) }}</span>
        </div>
      </footer>
    </section>

    <!-- 空状态 -->
    <section v-else class="card flex flex-col items-center gap-4 p-16 text-center">
      <div class="grid size-16 place-items-center rounded-full bg-paper text-brand-300">
        <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" />
          <path d="M9.5 8h5M9.5 12h5" />
        </svg>
      </div>
      <p class="text-sm text-ink-400">还没有订单，去菜单挑选喜欢的商品吧</p>
      <button class="btn-accent" @click="router.push({ name: 'consumer-menu' })">去点餐</button>
    </section>

    <!-- 最近订单 -->
    <section v-if="orderStore.recentOrders.length > 0" class="card p-6">
      <h3 class="text-sm font-semibold text-ink-900">最近订单</h3>
      <ul class="mt-3 divide-y divide-line">
        <li v-for="o in orderStore.recentOrders" :key="o.order_id" class="flex items-center gap-3 py-3">
          <span class="text-sm font-medium text-ink-900">{{ o.order_id }}</span>
          <span class="text-xs text-ink-400">{{ o.items.length }} 件 · {{ formatPriceCent(o.total_price_cent) }}</span>
          <span class="ml-auto rounded-full px-2.5 py-0.5 text-[11px] font-medium" :class="o.status === 'COMPLETED' ? 'bg-success-100 text-success-500' : o.status === 'CANCELED' ? 'bg-paper text-ink-400' : 'bg-brand-50 text-brand-700'">
            {{ statusLabel[o.status] }}
          </span>
        </li>
      </ul>
    </section>
  </div>
</template>
