<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, realtime } from '@/api'
import type { QueueSnapshot } from '@/api/types'
import { useOrderStore } from '@/stores/order'
import { formatCountdown, formatSeconds } from '@/utils/format'

const orderStore = useOrderStore()
const router = useRouter()

const snapshot = ref<QueueSnapshot | null>(null)
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
let unsubscribe: (() => void) | undefined

async function load(): Promise<void> {
  try {
    snapshot.value = await api.listQueueSnapshots('store-main')
  } catch {
    /* 队列快照获取失败时保持上次状态 */
  }
}

onMounted(async () => {
  await load()
  unsubscribe = realtime.on('queue.updated', () => void load())
  timer = setInterval(() => (now.value = Date.now()), 1000)
})

onUnmounted(() => {
  unsubscribe?.()
  if (timer) clearInterval(timer)
})

const myOrder = computed(() => orderStore.currentOrder)
const myParty = computed(() => snapshot.value?.parties.find((p) => p.party_id === myOrder.value?.order_id) ?? null)
const waitSec = computed(() => {
  if (!myOrder.value) return 0
  const eta = myParty.value?.eta_sec
  if (eta !== undefined) return eta
  return Math.max(0, Math.round((new Date(myOrder.value.estimated_ready_at).getTime() - now.value) / 1000))
})
const aheadCount = computed(() => {
  if (!myOrder.value) return 0
  return (snapshot.value?.parties ?? []).filter(
    (p) => p.status === 'WAITING' && p.party_id !== myOrder.value?.order_id,
  ).length
})
</script>

<template>
  <div class="anim-fade grid grid-cols-5 gap-6">
    <!-- 我的排队 -->
    <section class="card col-span-2 flex flex-col p-8">
      <p class="eyebrow">My Queue</p>
      <h2 class="mt-2 font-display text-2xl font-semibold text-brand-950">我的排队</h2>

      <div v-if="myOrder" class="mt-8 flex flex-1 flex-col items-center justify-center text-center">
        <div class="relative grid size-40 place-items-center rounded-full border-[10px] border-accent-100 bg-accent-50">
          <div>
            <p class="text-[11px] uppercase tracking-[0.2em] text-accent-600">前面还有</p>
            <p class="font-display text-6xl font-semibold text-accent-600 tabular-nums">{{ aheadCount }}</p>
            <p class="text-xs text-ink-400">位顾客</p>
          </div>
        </div>

        <div class="mt-6 flex items-center gap-2">
          <span
            class="rounded-full px-3 py-1 text-xs font-semibold"
            :class="myOrder.status === 'READY' ? 'bg-success-100 text-success-500' : myOrder.status === 'PRODUCING' ? 'bg-brand-50 text-brand-700' : 'bg-accent-50 text-accent-600'"
          >
            {{ { CONFIRMED: '等待制作', PRODUCING: '制作中', READY: '请取餐', COMPLETED: '已完成', PENDING: '等待确认', CANCELED: '已取消' }[myOrder.status] }}
          </span>
          <span class="text-sm text-ink-500">预计等待</span>
          <span class="font-display text-xl font-semibold text-ink-900 tabular-nums">{{ formatCountdown(waitSec) }}</span>
        </div>

        <div class="mt-4 flex items-center gap-2 text-xs text-ink-400">
          <span class="rounded-full bg-paper px-3 py-1">取餐码</span>
          <span class="font-display text-lg font-semibold tracking-widest text-brand-900">{{ myOrder.order_id.slice(-4) }}</span>
        </div>

        <button class="btn-ghost mt-8 text-xs" @click="router.push({ name: 'consumer-orders' })">查看订单详情 →</button>
      </div>

      <div v-else class="mt-8 flex flex-1 flex-col items-center justify-center gap-4 text-center">
        <div class="grid size-16 place-items-center rounded-full bg-paper text-brand-300">
          <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8L4 7Z" />
            <path d="M8.5 10V6a3.5 3.5 0 0 1 7 0v4" />
          </svg>
        </div>
        <p class="text-sm text-ink-400">还没有进行中的订单</p>
        <button class="btn-accent" @click="router.push({ name: 'consumer-menu' })">去点餐</button>
      </div>
    </section>

    <!-- 当前队列 -->
    <section class="card col-span-3 flex flex-col p-8">
      <div class="flex items-baseline justify-between">
        <div>
          <p class="eyebrow">Live Queue</p>
          <h2 class="mt-2 font-display text-2xl font-semibold text-brand-950">当前队列</h2>
        </div>
        <span class="flex items-center gap-1.5 text-xs text-ink-400">
          <span class="size-1.5 animate-pulse rounded-full bg-success-500" />
          {{ snapshot?.parties.length ?? 0 }} 个进行中订单 · 实时更新
        </span>
      </div>

      <div v-if="!snapshot || snapshot.parties.length === 0" class="flex flex-1 items-center justify-center text-sm text-ink-400">
        当前没有进行中的订单，队列空闲
      </div>

      <ul v-else class="mt-6 flex-1 space-y-2 overflow-y-auto pr-1">
        <li
          v-for="(p, i) in snapshot.parties"
          :key="p.party_id"
          class="flex items-center gap-4 rounded-2xl border border-line px-4 py-3"
          :class="p.party_id === myOrder?.order_id && 'border-brand-400 bg-brand-50/60'"
        >
          <span class="grid size-9 shrink-0 place-items-center rounded-full bg-paper text-sm font-semibold text-ink-500 tabular-nums">
            {{ i + 1 }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-ink-900">
              订单 {{ p.party_id }}
              <span v-if="p.party_id === myOrder?.order_id" class="ml-1 rounded-full bg-accent-500 px-2 py-0.5 text-[10px] font-semibold text-white">我</span>
            </p>
            <p class="text-xs text-ink-400 tabular-nums">已等待 {{ formatSeconds(p.waiting_sec) }}</p>
          </div>
          <span
            class="shrink-0 rounded-full px-3 py-1 text-xs font-medium"
            :class="p.status === 'READY' ? 'bg-success-100 text-success-500' : 'bg-brand-50 text-brand-700'"
          >
            {{ p.status === 'READY' ? '待取餐' : '制作中' }}
          </span>
          <span class="w-16 shrink-0 text-right text-xs text-ink-400 tabular-nums">{{ formatSeconds(p.eta_sec) }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>
