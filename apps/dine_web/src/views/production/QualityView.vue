<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { QualityEvent } from '@/api/types'
import StatCard from '@/components/StatCard.vue'

const message = useMessage()

const events = ref<QualityEvent[]>([])
const loading = ref(true)

const typeLabel: Record<QualityEvent['type'], string> = {
  VISUAL_DEFECT: '视觉缺陷',
  TEMP_ABNORMAL: '温度异常',
  EXPIRY: '临近过期',
  CONTAMINATION: '污染风险',
}

const statusLabel: Record<QualityEvent['status'], string> = {
  OPEN: '待处理',
  INSPECTING: '复核中',
  HANDLED: '已处理',
}

const openCount = computed(() => events.value.filter((e) => e.status === 'OPEN').length)
const inspectingCount = computed(() => events.value.filter((e) => e.status === 'INSPECTING').length)
const handledCount = computed(() => events.value.filter((e) => e.status === 'HANDLED').length)

async function load(): Promise<void> {
  loading.value = true
  try {
    events.value = await api.listQualityEvents()
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function handle(event: QualityEvent, status: 'INSPECTING' | 'HANDLED'): Promise<void> {
  try {
    await api.handleQualityEvent(event.event_id, status)
    message.success(status === 'HANDLED' ? '质检事件已处理' : '已标记复核中')
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

function severityClass(severity: QualityEvent['severity']): string {
  if (severity === 'HIGH') return 'bg-danger-100 text-danger-500'
  if (severity === 'MEDIUM') return 'bg-warning-100 text-warning-500'
  return 'bg-brand-50 text-brand-700'
}
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <StatCard label="待处理" :value="String(openCount)" unit="条" tone="danger" />
      <StatCard label="复核中" :value="String(inspectingCount)" unit="条" tone="warning" />
      <StatCard label="已处理" :value="String(handledCount)" unit="条" tone="success" />
    </div>

    <section class="card overflow-hidden">
      <header class="flex items-center justify-between border-b border-line px-6 py-4">
        <h2 class="font-display text-lg font-semibold text-brand-900">质检事件</h2>
        <span class="text-xs text-ink-400">来源：视觉质检 / 温控监测 / 人工巡检</span>
      </header>
      <div v-if="loading" class="space-y-2 p-4">
        <div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-brand-50" />
      </div>
      <ul v-else class="divide-y divide-line">
        <li v-for="e in events" :key="e.event_id" class="flex items-center gap-4 px-6 py-4">
          <span class="size-2.5 shrink-0 rounded-full" :class="e.status === 'HANDLED' ? 'bg-success-500' : e.status === 'INSPECTING' ? 'bg-warning-500' : 'bg-danger-500'" />
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="text-sm font-semibold text-ink-900">{{ e.ingredient_name }}</p>
              <span class="rounded-full px-2 py-0.5 text-[10px] font-medium" :class="severityClass(e.severity)">
                {{ typeLabel[e.type] }}
              </span>
              <span class="text-xs text-ink-400 tabular-nums">{{ e.quantity }} {{ e.unit }}</span>
            </div>
            <p class="mt-0.5 truncate text-xs text-ink-500">{{ e.note }}</p>
            <p class="mt-0.5 text-[11px] text-ink-300">
              {{ e.source }} · {{ e.detected_at.slice(0, 16).replace('T', ' ') }}
            </p>
          </div>
          <span class="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium" :class="e.status === 'HANDLED' ? 'bg-success-100 text-success-500' : e.status === 'INSPECTING' ? 'bg-warning-100 text-warning-500' : 'bg-danger-100 text-danger-500'">
            {{ statusLabel[e.status] }}
          </span>
          <div v-if="e.status === 'OPEN'" class="flex shrink-0 gap-1.5">
            <button class="btn-ghost !px-3 !py-1 text-xs" @click="handle(e, 'INSPECTING')">复核</button>
            <button class="btn-accent !px-3 !py-1 text-xs" @click="handle(e, 'HANDLED')">处理完成</button>
          </div>
          <div v-else-if="e.status === 'INSPECTING'" class="shrink-0">
            <button class="btn-accent !px-3 !py-1 text-xs" @click="handle(e, 'HANDLED')">完成处理</button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
