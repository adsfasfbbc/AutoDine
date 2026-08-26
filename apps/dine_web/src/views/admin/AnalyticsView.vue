<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { AnalyticsSummary, CategoryShare, TrafficSummary } from '@/api/types'
import BarChart from '@/components/charts/BarChart.vue'
import DonutChart from '@/components/charts/DonutChart.vue'
import StatCard from '@/components/StatCard.vue'
import { formatPriceCent } from '@/utils/format'

const analytics = ref<AnalyticsSummary | null>(null)
const traffic = ref<TrafficSummary | null>(null)
const categories = ref<CategoryShare[]>([])

const DONUT_COLORS = ['#2c5a80', '#5d90b5', '#d97a2e', '#e9a15c', '#9da9b3']

const revenueData = computed(() =>
  (traffic.value?.hourly ?? []).map((p) => ({
    label: `${p.hour}:00`,
    value: p.revenue_cent,
    color: p.hour === traffic.value?.peak_hour ? '#d97a2e' : '#2c5a80',
  })),
)

const donutSegments = computed(() =>
  categories.value.map((c, i) => ({
    label: c.label,
    value: c.revenue_cent,
    color: DONUT_COLORS[i % DONUT_COLORS.length],
  })),
)

const peakText = computed(() => {
  if (!traffic.value) return '—'
  return `${String(traffic.value.peak_hour).padStart(2, '0')}:00`
})

const avgOrderText = computed(() =>
  analytics.value ? formatPriceCent(analytics.value.avg_order_cent) : '—',
)

const waitText = computed(() => {
  if (!analytics.value) return '—'
  const s = analytics.value.avg_wait_sec
  return s >= 60 ? `${Math.round(s / 60)} 分 ${s % 60} 秒` : `${s} 秒`
})

async function load(): Promise<void> {
  const [a, t, c] = await Promise.all([
    api.getAnalyticsSummary('store-main', new Date(Date.now() - 86_400_000).toISOString(), new Date().toISOString()),
    api.getTrafficSummary('store-main'),
    api.getCategoryBreakdown('store-main'),
  ])
  analytics.value = a
  traffic.value = t
  categories.value = c
}

onMounted(load)
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="今日订单" :value="String(analytics?.orders ?? '—')" unit="单" tone="brand" :delta="8.2" />
      <StatCard label="营业额" :value="analytics ? formatPriceCent(analytics.revenue_cent) : '—'" tone="accent" :delta="5.4" />
      <StatCard label="客单价" :value="avgOrderText" tone="success" :delta="1.8" />
      <StatCard label="平均等待" :value="waitText" tone="ink" :delta="-3.1" />
    </div>

    <div class="grid grid-cols-3 items-start gap-6">
      <!-- 分时营收 -->
      <section class="card col-span-2 p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="font-display text-lg font-semibold text-brand-900">分时营收</h2>
            <p class="mt-0.5 text-xs text-ink-400">按小时统计营业额，橙色为峰值时段</p>
          </div>
          <span class="text-xs text-ink-400">峰值 <span class="font-semibold text-accent-600">{{ peakText }}</span></span>
        </div>
        <div class="mt-6">
          <BarChart :data="revenueData" :height="210" :value-format="(v) => `¥${Math.round(v / 100)}`" />
        </div>
      </section>

      <!-- 品类构成 -->
      <section class="card p-6">
        <h2 class="font-display text-lg font-semibold text-brand-900">品类构成</h2>
        <p class="mt-0.5 text-xs text-ink-400">按营收占比统计</p>
        <div class="mt-5">
          <DonutChart :segments="donutSegments" center-value="¥3.7k" center-label="今日营收" />
        </div>
      </section>
    </div>

    <div class="grid grid-cols-3 gap-6">
      <section class="card p-6">
        <h2 class="text-sm font-semibold text-ink-900">时段洞察</h2>
        <div class="mt-4 space-y-3 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-ink-500">营业高峰</span>
            <span class="font-semibold text-ink-900 tabular-nums">{{ peakText }} – {{ String((traffic?.peak_hour ?? 0) + 1).padStart(2, '0') }}:00</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-ink-500">平均每日客流</span>
            <span class="font-semibold text-ink-900 tabular-nums">{{ traffic?.avg_daily_parties ?? '—' }} 人次</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-ink-500">售罄商品</span>
            <span class="font-semibold text-ink-900 tabular-nums">{{ analytics?.sold_out_count ?? '—' }} 款</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-ink-500">待处理告警</span>
            <span class="font-semibold tabular-nums" :class="(analytics?.open_alarms ?? 0) > 0 ? 'text-danger-500' : 'text-ink-900'">{{ analytics?.open_alarms ?? '—' }} 条</span>
          </div>
        </div>
      </section>

      <section class="card col-span-2 p-6">
        <h2 class="text-sm font-semibold text-ink-900">品类营收排名</h2>
        <ul class="mt-4 space-y-2.5">
          <li v-for="(c, i) in [...categories].sort((a, b) => b.revenue_cent - a.revenue_cent)" :key="c.category" class="flex items-center gap-3">
            <span class="grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold" :class="i === 0 ? 'bg-accent-500 text-white' : 'bg-paper text-ink-500'">{{ i + 1 }}</span>
            <span class="size-2.5 shrink-0 rounded-sm" :style="{ background: DONUT_COLORS[categories.indexOf(c) % DONUT_COLORS.length] }" />
            <span class="text-sm text-ink-700">{{ c.label }}</span>
            <span class="text-xs text-ink-400 tabular-nums">{{ c.orders }} 单</span>
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-paper">
              <div class="h-full rounded-full bg-brand-500" :style="{ width: `${(c.revenue_cent / Math.max(1, categories[0]?.revenue_cent ?? 1)) * 100}%` }" />
            </div>
            <span class="w-20 shrink-0 text-right text-sm font-medium tabular-nums">{{ formatPriceCent(c.revenue_cent) }}</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
