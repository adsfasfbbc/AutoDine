<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'

import { api } from '@/api'
import type { Alarm, ProductionTask } from '@/api/types'
import StatCard from '@/components/StatCard.vue'

const message = useMessage()

const tasks = ref<ProductionTask[]>([])
const alarms = ref<Alarm[]>([])
const loading = ref(true)

const producing = computed(() => tasks.value.filter((t) => t.status === 'PRODUCING').length)
const pending = computed(() => tasks.value.filter((t) => t.status === 'PENDING').length)
const ready = computed(() => tasks.value.filter((t) => t.status === 'READY').length)
const openAlarms = computed(() => alarms.value.filter((a) => a.status === 'OPEN').length)

const taskStatusLabel: Record<ProductionTask['status'], string> = {
  PENDING: '待制作',
  PRODUCING: '制作中',
  READY: '待取餐',
  COMPLETED: '已完成',
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [t, a] = await Promise.all([api.listProductionTasks(), api.listAlarms('store-main')])
    tasks.value = t
    alarms.value = a
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function transition(task: ProductionTask, action: 'start' | 'ready' | 'complete'): Promise<void> {
  try {
    if (action === 'start') await api.startTask(task.task_id)
    else if (action === 'ready') await api.readyTask(task.task_id)
    else await api.completeTask(task.task_id)
    message.success('任务状态已更新')
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
      <StatCard label="制作中" :value="String(producing)" unit="单" tone="accent" />
      <StatCard label="待制作" :value="String(pending)" unit="单" tone="brand" />
      <StatCard label="待取餐" :value="String(ready)" unit="单" tone="success" />
      <StatCard label="待处理告警" :value="String(openAlarms)" unit="条" tone="danger" />
    </div>

    <div class="grid grid-cols-3 gap-6">
      <!-- 制作任务预览 -->
      <section class="card col-span-2 flex flex-col p-6">
        <div class="flex items-center justify-between">
          <h2 class="font-display text-lg font-semibold text-brand-900">制作任务</h2>
          <span class="text-xs text-ink-400">共 {{ tasks.length }} 单 · 手动流转演示</span>
        </div>

        <div v-if="loading" class="mt-4 space-y-2">
          <div v-for="i in 4" :key="i" class="h-14 animate-pulse rounded-xl bg-brand-50" />
        </div>

        <div v-else-if="tasks.length === 0" class="mt-8 flex flex-1 items-center justify-center text-sm text-ink-400">
          暂无制作任务——到用户端点一单试试
        </div>

        <ul v-else class="mt-4 flex-1 space-y-2 overflow-y-auto pr-1">
          <li v-for="t in tasks.slice(0, 8)" :key="t.task_id" class="flex items-center gap-3 rounded-2xl border border-line px-4 py-3">
            <span class="text-xs font-semibold text-ink-500 tabular-nums">{{ t.task_id }}</span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink-900">
                {{ t.items.map((i) => `${i.name}×${i.quantity}`).join('、') }}
              </p>
              <p class="text-xs text-ink-400">订单 {{ t.order_id }}</p>
            </div>
            <span
              class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
              :class="t.status === 'PRODUCING' ? 'bg-brand-50 text-brand-700' : t.status === 'READY' ? 'bg-success-100 text-success-500' : t.status === 'COMPLETED' ? 'bg-paper text-ink-400' : 'bg-accent-50 text-accent-600'"
            >
              {{ taskStatusLabel[t.status] }}
            </span>
            <div v-if="t.status === 'PENDING'" class="flex shrink-0 gap-1.5">
              <button class="btn-accent !px-3 !py-1 text-xs" @click="transition(t, 'start')">开始制作</button>
            </div>
            <div v-else-if="t.status === 'PRODUCING'" class="flex shrink-0 gap-1.5">
              <button class="btn-accent !px-3 !py-1 text-xs" @click="transition(t, 'ready')">出餐</button>
            </div>
            <div v-else-if="t.status === 'READY'" class="flex shrink-0 gap-1.5">
              <button class="btn-ghost !px-3 !py-1 text-xs" @click="transition(t, 'complete')">完成</button>
            </div>
          </li>
        </ul>
      </section>

      <!-- 告警速览 -->
      <section class="card flex flex-col p-6">
        <div class="flex items-center justify-between">
          <h2 class="font-display text-lg font-semibold text-brand-900">告警速览</h2>
          <span class="text-xs text-ink-400">{{ alarms.length }} 条</span>
        </div>
        <ul class="mt-4 flex-1 space-y-2.5 overflow-y-auto pr-1">
          <li v-for="a in alarms.slice(0, 5)" :key="a.alarm_id" class="rounded-2xl border border-line p-3">
            <div class="flex items-center gap-2">
              <span
                class="size-2 shrink-0 rounded-full"
                :class="a.severity === 'CRITICAL' ? 'bg-danger-500' : a.severity === 'WARNING' ? 'bg-warning-500' : 'bg-brand-400'"
              />
              <p class="truncate text-sm font-medium text-ink-900">{{ a.title }}</p>
            </div>
            <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-400">{{ a.message }}</p>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
