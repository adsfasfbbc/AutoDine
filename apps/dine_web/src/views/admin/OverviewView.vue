<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'

import { api } from '@/api'
import type { Alarm, AnalyticsSummary } from '@/api/types'
import StatCard from '@/components/StatCard.vue'
import { formatPriceCent } from '@/utils/format'

const message = useMessage()

const analytics = ref<AnalyticsSummary | null>(null)
const alarms = ref<Alarm[]>([])

const revenueText = computed(() =>
  analytics.value ? formatPriceCent(analytics.value.revenue_cent) : '—',
)
const waitText = computed(() => {
  if (!analytics.value) return '—'
  const s = analytics.value.avg_wait_sec
  return s >= 60 ? `${Math.round(s / 60)} 分` : `${s} 秒`
})
const openAlarms = computed(() => alarms.value.filter((a) => a.status === 'OPEN'))
const alarmSeverityLabel: Record<Alarm['severity'], string> = {
  CRITICAL: '严重',
  WARNING: '警告',
  INFO: '提示',
}

async function load(): Promise<void> {
  const [a, al] = await Promise.all([
    api.getAnalyticsSummary('store-main', new Date(Date.now() - 86_400_000).toISOString(), new Date().toISOString()),
    api.listAlarms('store-main'),
  ])
  analytics.value = a
  alarms.value = al
}

onMounted(load)

async function acknowledge(alarm: Alarm): Promise<void> {
  try {
    await api.acknowledgeAlarm(alarm.alarm_id)
    message.success('告警已确认')
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function resolve(alarm: Alarm): Promise<void> {
  try {
    await api.resolveAlarm(alarm.alarm_id)
    message.success('告警已解决')
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}
</script>

<template>
  <div class="anim-fade space-y-6">
    <!-- KPI -->
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="今日订单" :value="String(analytics?.orders ?? '—')" unit="单" tone="brand" :delta="8.2" />
      <StatCard label="营业额" :value="revenueText" tone="accent" :delta="5.4" />
      <StatCard label="平均等待" :value="waitText" tone="success" :delta="-3.1" />
      <StatCard label="设备在线率" :value="analytics ? `${analytics.online_devices}/${analytics.total_devices}` : '—'" tone="ink" :delta="1.2" />
    </div>

    <div class="grid grid-cols-3 gap-6">
      <!-- 告警中心预览 -->
      <section class="card col-span-2 flex flex-col p-6">
        <div class="flex items-center justify-between">
          <h2 class="font-display text-lg font-semibold text-brand-900">待处理告警</h2>
          <span class="text-xs text-ink-400">{{ openAlarms.length }} 条待处理</span>
        </div>

        <div v-if="openAlarms.length === 0" class="mt-8 flex flex-1 items-center justify-center gap-2 text-sm text-ink-400">
          <svg viewBox="0 0 24 24" class="size-5 text-success-500" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
            <path d="m8.5 12 2.4 2.4L15.5 9.5" />
          </svg>
          暂无待处理告警
        </div>

        <ul v-else class="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
          <li v-for="a in openAlarms" :key="a.alarm_id" class="flex items-start gap-3 rounded-2xl border border-line p-4">
            <span
              class="mt-0.5 size-2.5 shrink-0 rounded-full"
              :class="a.severity === 'CRITICAL' ? 'bg-danger-500' : a.severity === 'WARNING' ? 'bg-warning-500' : 'bg-brand-400'"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p class="truncate text-sm font-semibold text-ink-900">{{ a.title }}</p>
                <span class="shrink-0 rounded-full bg-paper px-2 py-0.5 text-[10px] font-medium text-ink-500">
                  {{ alarmSeverityLabel[a.severity] }}
                </span>
              </div>
              <p class="mt-1 text-xs leading-relaxed text-ink-400">{{ a.message }}</p>
            </div>
            <div class="flex shrink-0 gap-1.5">
              <button class="btn-ghost !px-3 !py-1 text-xs" @click="acknowledge(a)">确认</button>
              <button class="btn-accent !px-3 !py-1 text-xs" @click="resolve(a)">解决</button>
            </div>
          </li>
        </ul>
      </section>

      <!-- 快捷入口 -->
      <section class="card p-6">
        <h2 class="font-display text-lg font-semibold text-brand-900">经营模块</h2>
        <p class="mt-1 text-xs text-ink-400">以下模块将在后续迭代逐步实现</p>
        <ul class="mt-4 space-y-2">
          <li v-for="item in [
            { to: '/admin/orders', label: '订单管理', icon: 'receipt' },
            { to: '/admin/traffic', label: '客流分析', icon: 'users' },
            { to: '/admin/inventory', label: '库存管理', icon: 'box' },
            { to: '/admin/analytics', label: '经营分析', icon: 'activity' },
          ]" :key="item.to">
            <RouterLink
              :to="item.to"
              class="flex items-center gap-3 rounded-xl border border-line px-4 py-3 text-sm font-medium text-ink-700 transition-colors hover:border-brand-300 hover:text-brand-800"
            >
              <svg viewBox="0 0 24 24" class="size-[18px] text-brand-600" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8L4 7Z" />
                <path d="M8.5 10V6a3.5 3.5 0 0 1 7 0v4" />
              </svg>
              {{ item.label }}
              <span class="ml-auto text-ink-300">→</span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
