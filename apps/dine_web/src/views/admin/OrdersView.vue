<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { Order, OrderStatus } from '@/api/types'
import ProductImage from '@/components/ProductImage.vue'
import { formatPriceCent, pickupCode } from '@/utils/format'

const message = useMessage()

const orders = ref<Order[]>([])
const loading = ref(true)
const statusFilter = ref<'ALL' | OrderStatus>('ALL')
const search = ref('')
const selected = ref<Order | null>(null)

const statusLabel: Record<OrderStatus, string> = {
  PENDING: '等待确认',
  CONFIRMED: '已确认',
  PRODUCING: '制作中',
  READY: '待取餐',
  COMPLETED: '已完成',
  CANCELED: '已取消',
}

const statusClass: Record<OrderStatus, string> = {
  PENDING: 'bg-paper text-ink-400',
  CONFIRMED: 'bg-accent-50 text-accent-600',
  PRODUCING: 'bg-brand-50 text-brand-700',
  READY: 'bg-success-100 text-success-500',
  COMPLETED: 'bg-paper text-ink-500',
  CANCELED: 'bg-paper text-ink-300',
}

const filters: { key: 'ALL' | OrderStatus; label: string }[] = [
  { key: 'ALL', label: '全部' },
  { key: 'CONFIRMED', label: '已确认' },
  { key: 'PRODUCING', label: '制作中' },
  { key: 'READY', label: '待取餐' },
  { key: 'COMPLETED', label: '已完成' },
  { key: 'CANCELED', label: '已取消' },
]

const counts = computed(() => {
  const map = new Map<string, number>()
  for (const o of orders.value) map.set(o.status, (map.get(o.status) ?? 0) + 1)
  return map
})

const filtered = computed(() => {
  const kw = search.value.trim().toUpperCase()
  return orders.value.filter((o) => {
    if (statusFilter.value !== 'ALL' && o.status !== statusFilter.value) return false
    if (kw && !o.order_id.includes(kw)) return false
    return true
  })
})

async function load(): Promise<void> {
  loading.value = true
  try {
    orders.value = await api.listOrders()
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function cancelOrder(order: Order): Promise<void> {
  try {
    await api.cancelOrder(order.order_id)
    message.success('订单已取消')
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '取消失败')
  }
}

function timeText(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ')
}
</script>

<template>
  <div class="anim-fade space-y-4">
    <!-- 筛选 -->
    <div class="flex flex-wrap items-center gap-2">
      <button
        v-for="f in filters"
        :key="f.key"
        class="chip"
        :class="statusFilter === f.key && 'chip-active'"
        @click="statusFilter = f.key"
      >
        {{ f.label }}
        <span v-if="f.key !== 'ALL'" class="tabular-nums opacity-70">{{ counts.get(f.key) ?? 0 }}</span>
      </button>
      <div class="relative ml-auto w-64">
        <svg viewBox="0 0 24 24" class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-300" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input v-model="search" type="search" class="field !pl-9" placeholder="按订单号搜索…" />
      </div>
    </div>

    <!-- 表格 -->
    <section class="card overflow-hidden">
      <div v-if="loading" class="space-y-2 p-4">
        <div v-for="i in 6" :key="i" class="h-12 animate-pulse rounded-lg bg-brand-50" />
      </div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-line text-left text-xs text-ink-400">
            <th class="px-6 py-3 font-medium">订单号</th>
            <th class="px-3 py-3 font-medium">下单时间</th>
            <th class="px-3 py-3 font-medium">商品</th>
            <th class="px-3 py-3 text-right font-medium">金额</th>
            <th class="px-3 py-3 font-medium">状态</th>
            <th class="px-6 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="o in filtered" :key="o.order_id" class="transition-colors hover:bg-paper/60">
            <td class="px-6 py-3">
              <p class="font-medium text-ink-900 tabular-nums">{{ o.order_id }}</p>
              <p class="text-[11px] text-ink-300">取餐码 {{ pickupCode(o.order_id) }}</p>
            </td>
            <td class="px-3 py-3 text-xs text-ink-500 tabular-nums">{{ timeText(o.created_at) }}</td>
            <td class="max-w-56 px-3 py-3">
              <div class="flex flex-wrap gap-1">
                <span v-for="it in o.items.slice(0, 3)" :key="it.product_id" class="rounded-full bg-paper px-2 py-0.5 text-[11px] text-ink-600">
                  {{ it.name }}×{{ it.quantity }}
                </span>
                <span v-if="o.items.length > 3" class="rounded-full bg-paper px-2 py-0.5 text-[11px] text-ink-300">+{{ o.items.length - 3 }}</span>
              </div>
            </td>
            <td class="px-3 py-3 text-right font-semibold tabular-nums">{{ formatPriceCent(o.total_price_cent) }}</td>
            <td class="px-3 py-3">
              <span class="rounded-full px-2.5 py-1 text-[11px] font-medium" :class="statusClass[o.status]">{{ statusLabel[o.status] }}</span>
            </td>
            <td class="px-6 py-3 text-right">
              <div class="flex justify-end gap-1.5">
                <button class="btn-ghost !px-3 !py-1 text-xs" @click="selected = o">详情</button>
                <button v-if="['CONFIRMED', 'PRODUCING'].includes(o.status)" class="btn-accent !px-3 !py-1 text-xs" @click="cancelOrder(o)">取消</button>
              </div>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="6" class="px-6 py-12 text-center text-sm text-ink-400">没有符合条件的订单</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 详情抽屉 -->
    <Transition name="drawer">
      <div v-if="selected" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-ink-900/30 backdrop-blur-[2px]" @click="selected = null" />
        <div class="anim-rise relative flex h-full w-[440px] flex-col bg-surface shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-5">
            <div>
              <p class="eyebrow">Order Detail</p>
              <h2 class="mt-1 font-display text-lg font-semibold text-brand-950 tabular-nums">{{ selected.order_id }}</h2>
            </div>
            <button class="grid size-9 cursor-pointer place-items-center rounded-full bg-paper text-ink-500 transition-transform hover:scale-105" aria-label="关闭" @click="selected = null">
              <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
            </button>
          </header>

          <div class="flex-1 overflow-y-auto px-6 py-5">
            <div class="flex items-center justify-between text-sm">
              <span class="text-ink-400">下单时间</span>
              <span class="text-ink-700 tabular-nums">{{ timeText(selected.created_at) }}</span>
            </div>
            <div class="mt-2 flex items-center justify-between text-sm">
              <span class="text-ink-400">状态</span>
              <span class="rounded-full px-2.5 py-0.5 text-[11px] font-medium" :class="statusClass[selected.status]">{{ statusLabel[selected.status] }}</span>
            </div>
            <div class="mt-2 flex items-center justify-between text-sm">
              <span class="text-ink-400">取餐码</span>
              <span class="font-display text-base font-semibold tracking-[0.25em] text-accent-600">{{ pickupCode(selected.order_id) }}</span>
            </div>

            <h3 class="mt-6 text-sm font-semibold text-ink-900">商品清单</h3>
            <ul class="mt-3 divide-y divide-line rounded-2xl border border-line">
              <li v-for="it in selected.items" :key="it.product_id" class="flex items-center gap-3 px-4 py-3">
                <ProductImage :src="it.image" :alt="it.name" rounded="rounded-lg" class="size-11 shrink-0" />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm text-ink-900">{{ it.name }}</p>
                  <p class="text-[11px] text-ink-400">× {{ it.quantity }}</p>
                </div>
                <span class="text-sm tabular-nums">{{ formatPriceCent(it.price_cent * it.quantity) }}</span>
              </li>
            </ul>

            <div class="mt-4 flex items-center justify-between">
              <span class="text-sm text-ink-500">合计</span>
              <span class="font-display text-xl font-semibold text-ink-900 tabular-nums">{{ formatPriceCent(selected.total_price_cent) }}</span>
            </div>
          </div>

          <footer v-if="['CONFIRMED', 'PRODUCING'].includes(selected.status)" class="border-t border-line px-6 py-4">
            <button class="btn-accent w-full" @click="cancelOrder(selected); selected = null">取消该订单</button>
          </footer>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s var(--ease-standard);
}
.drawer-enter-active .anim-rise,
.drawer-leave-active .anim-rise {
  transition: transform 0.28s var(--ease-standard);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .anim-rise,
.drawer-leave-to .anim-rise {
  transform: translateX(40px);
}
</style>
