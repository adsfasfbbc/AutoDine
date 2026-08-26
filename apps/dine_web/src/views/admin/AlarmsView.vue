<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { Alarm, AlarmSeverity, AlarmStatus } from '@/api/types'
import StatCard from '@/components/StatCard.vue'

const message = useMessage()

const alarms = ref<Alarm[]>([])
const loading = ref(true)
const severityFilter = ref<'ALL' | AlarmSeverity>('ALL')
const statusFilter = ref<'ALL' | AlarmStatus>('ALL')

const severityLabel: Record<AlarmSeverity, string> = {
  CRITICAL: '严重',
  WARNING: '警告',
  INFO: '提示',
}

const severityClass: Record<AlarmSeverity, string> = {
  CRITICAL: 'bg-danger-100 text-danger-500',
  WARNING: 'bg-warning-100 text-warning-500',
  INFO: 'bg-brand-50 text-brand-700',
}

const severityDot: Record<AlarmSeverity, string> = {
  CRITICAL: 'bg-danger-500',
  WARNING: 'bg-warning-500',
  INFO: 'bg-brand-400',
}

const categoryLabel: Record<Alarm['category'], string> = {
  DEVICE: '设备',
  INVENTORY: '库存',
  QUALITY: '质检',
  QUEUE: '排队',
  OTHER: '其他',
}

const statusLabel: Record<AlarmStatus, string> = {
  OPEN: '待处理',
  ACKNOWLEDGED: '已确认',
  RESOLVED: '已解决',
}

const statusClass: Record<AlarmStatus, string> = {
  OPEN: 'bg-danger-100 text-danger-500',
  ACKNOWLEDGED: 'bg-warning-100 text-warning-500',
  RESOLVED: 'bg-success-100 text-success-500',
}

const severityOptions: { k: 'ALL' | AlarmSeverity; label: string }[] = [
  { k: 'ALL', label: '全部' },
  { k: 'CRITICAL', label: '严重' },
  { k: 'WARNING', label: '警告' },
  { k: 'INFO', label: '提示' },
]

const statusOptions: { k: 'ALL' | AlarmStatus; label: string }[] = [
  { k: 'ALL', label: '全部' },
  { k: 'OPEN', label: '待处理' },
  { k: 'ACKNOWLEDGED', label: '已确认' },
  { k: 'RESOLVED', label: '已解决' },
]

const criticalCount = computed(() => alarms.value.filter((a) => a.severity === 'CRITICAL' && a.status !== 'RESOLVED').length)
const warningCount = computed(() => alarms.value.filter((a) => a.severity === 'WARNING' && a.status !== 'RESOLVED').length)
const openCount = computed(() => alarms.value.filter((a) => a.status === 'OPEN').length)

const filtered = computed(() =>
  alarms.value.filter((a) => {
    if (severityFilter.value !== 'ALL' && a.severity !== severityFilter.value) return false
    if (statusFilter.value !== 'ALL' && a.status !== statusFilter.value) return false
    return true
  }),
)

async function load(): Promise<void> {
  loading.value = true
  try {
    alarms.value = await api.listAlarms('store-main')
  } finally {
    loading.value = false
  }
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

function timeText(iso?: string): string {
  return iso ? iso.slice(0, 16).replace('T', ' ') : '—'
}
</script>

<template>
  <div class="anim-fade space-y-4">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="待处理" :value="String(openCount)" unit="条" tone="danger" />
      <StatCard label="严重未解决" :value="String(criticalCount)" unit="条" tone="danger" />
      <StatCard label="警告未解决" :value="String(warningCount)" unit="条" tone="warning" />
      <StatCard label="告警总数" :value="String(alarms.length)" unit="条" tone="brand" />
    </div>

    <div class="flex items-center gap-2">
      <span class="text-xs text-ink-400">级别</span>
      <button v-for="s in severityOptions" :key="s.k" class="chip" :class="severityFilter === s.k && 'chip-active'" @click="severityFilter = s.k">
        {{ s.label }}
      </button>
      <span class="ml-4 text-xs text-ink-400">状态</span>
      <button v-for="s in statusOptions" :key="s.k" class="chip" :class="statusFilter === s.k && 'chip-active'" @click="statusFilter = s.k">
        {{ s.label }}
      </button>
    </div>

    <section class="card overflow-hidden">
      <div v-if="loading" class="space-y-2 p-4">
        <div v-for="i in 4" :key="i" class="h-16 animate-pulse rounded-xl bg-brand-50" />
      </div>
      <ul v-else class="divide-y divide-line">
        <li v-for="a in filtered" :key="a.alarm_id" class="flex items-center gap-4 px-6 py-4">
          <span class="size-2.5 shrink-0 rounded-full" :class="severityDot[a.severity]" />
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="text-sm font-semibold text-ink-900">{{ a.title }}</p>
              <span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="severityClass[a.severity]">{{ severityLabel[a.severity] }}</span>
              <span class="rounded-full bg-paper px-2 py-0.5 text-[10px] text-ink-400">{{ categoryLabel[a.category] }}</span>
            </div>
            <p class="mt-0.5 truncate text-xs text-ink-500">{{ a.message }}</p>
            <p class="mt-0.5 text-[11px] text-ink-300">{{ timeText(a.created_at) }}</p>
          </div>
          <span class="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium" :class="statusClass[a.status]">{{ statusLabel[a.status] }}</span>
          <div class="flex shrink-0 gap-1.5">
            <button v-if="a.status === 'OPEN'" class="btn-ghost !px-3 !py-1 text-xs" @click="acknowledge(a)">确认</button>
            <button v-if="a.status !== 'RESOLVED'" class="btn-accent !px-3 !py-1 text-xs" @click="resolve(a)">解决</button>
          </div>
        </li>
        <li v-if="filtered.length === 0" class="px-6 py-12 text-center text-sm text-ink-400">没有符合条件的告警</li>
      </ul>
    </section>
  </div>
</template>
