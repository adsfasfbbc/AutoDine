<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { QueueSnapshot, TrafficSummary } from '@/api/types'
import BarChart from '@/components/charts/BarChart.vue'
import StatCard from '@/components/StatCard.vue'

const traffic = ref<TrafficSummary | null>(null)
const queue = ref<QueueSnapshot | null>(null)

const chartData = computed(() =>
  (traffic.value?.hourly ?? []).map((p) => ({
    label: `${p.hour}:00`,
    value: p.parties,
    color: p.hour === traffic.value?.peak_hour ? '#d97a2e' : '#3b729c',
  })),
)

const peakText = computed(() => {
  if (!traffic.value) return '—'
  const h = traffic.value.peak_hour
  return `${String(h).padStart(2, '0')}:00 – ${String(h + 1).padStart(2, '0')}:00`
})

async function load(): Promise<void> {
  const [t, q] = await Promise.all([api.getTrafficSummary('store-main'), api.listQueueSnapshots('store-main')])
  traffic.value = t
  queue.value = q
}

onMounted(load)
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="今日客流" :value="String(traffic?.today_parties ?? '—')" unit="人次" tone="accent" :delta="6.8" />
      <StatCard label="峰值时段" :value="peakText" tone="brand" />
      <StatCard label="日均客流" :value="String(traffic?.avg_daily_parties ?? '—')" unit="人次" tone="ink" :delta="2.4" />
      <StatCard label="当前排队" :value="String(queue?.parties.length ?? '—')" unit="单" tone="success" />
    </div>

    <div class="grid grid-cols-3 items-start gap-6">
      <!-- 分时客流 -->
      <section class="card col-span-2 p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="font-display text-lg font-semibold text-brand-900">分时客流</h2>
            <p class="mt-0.5 text-xs text-ink-400">按小时统计到场人次，橙色为峰值时段</p>
          </div>
          <span class="flex items-center gap-4 text-xs text-ink-400">
            <span class="flex items-center gap-1.5"><span class="size-2.5 rounded-sm bg-brand-500" />常规</span>
            <span class="flex items-center gap-1.5"><span class="size-2.5 rounded-sm bg-accent-500" />峰值</span>
          </span>
        </div>
        <div class="mt-6">
          <BarChart :data="chartData" :height="200" />
        </div>
      </section>

      <!-- 排队水位 -->
      <section class="card p-6">
        <h2 class="font-display text-lg font-semibold text-brand-900">排队水位</h2>
        <ul v-if="queue && queue.parties.length > 0" class="mt-4 space-y-2.5">
          <li v-for="(p, i) in queue.parties.slice(0, 8)" :key="p.party_id" class="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
            <span class="grid size-7 shrink-0 place-items-center rounded-full bg-paper text-xs font-semibold text-ink-500 tabular-nums">{{ i + 1 }}</span>
            <span class="truncate text-xs text-ink-700 tabular-nums">{{ p.party_id }}</span>
            <span class="ml-auto shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium" :class="p.status === 'READY' ? 'bg-success-100 text-success-500' : 'bg-brand-50 text-brand-700'">
              {{ p.status === 'READY' ? '待取餐' : '制作中' }}
            </span>
          </li>
        </ul>
        <p v-else class="mt-6 text-center text-sm text-ink-400">当前无排队订单</p>
      </section>
    </div>
  </div>
</template>
