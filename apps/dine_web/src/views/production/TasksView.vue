<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { api, realtime } from '@/api'
import type { ProductionTask, ProductionTaskStatus } from '@/api/types'
import { formatPriceCent } from '@/utils/format'

const message = useMessage()

const tasks = ref<ProductionTask[]>([])
const loading = ref(true)
let unsubscribe: (() => void)[] = []

const columns: { key: ProductionTaskStatus; label: string; dot: string }[] = [
  { key: 'PENDING', label: '待制作', dot: 'bg-accent-500' },
  { key: 'PRODUCING', label: '制作中', dot: 'bg-brand-500' },
  { key: 'READY', label: '待取餐', dot: 'bg-success-500' },
  { key: 'COMPLETED', label: '已完成', dot: 'bg-ink-300' },
]

const byStatus = computed(() => {
  const map = new Map<ProductionTaskStatus, ProductionTask[]>()
  for (const c of columns) map.set(c.key, [])
  for (const t of tasks.value) map.get(t.status)?.push(t)
  return map
})

async function load(): Promise<void> {
  loading.value = true
  try {
    tasks.value = await api.listProductionTasks()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  for (const topic of ['production.task_created', 'production.task_started', 'production.task_ready', 'production.task_completed'] as const) {
    unsubscribe.push(realtime.on(topic, () => void load()))
  }
})

onUnmounted(() => unsubscribe.forEach((off) => off()))

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

function timeText(iso: string): string {
  return iso.slice(11, 16)
}

function itemsText(task: ProductionTask): string {
  return task.items.map((i) => `${i.name}×${i.quantity}`).join('、')
}
</script>

<template>
  <div class="anim-fade space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm text-ink-500">
        共 <span class="font-semibold text-ink-900">{{ tasks.length }}</span> 个任务 · 卡片随订单自动流转，也可手动操作
      </p>
      <span class="text-xs text-ink-300">实时刷新</span>
    </div>

    <div v-if="loading" class="grid grid-cols-4 gap-4">
      <div v-for="i in 4" :key="i" class="card h-72 animate-pulse p-4">
        <div class="h-4 w-1/3 rounded bg-brand-100" />
      </div>
    </div>

    <div v-else class="grid grid-cols-4 items-start gap-4">
      <section v-for="col in columns" :key="col.key" class="card flex min-h-[420px] flex-col p-3">
        <header class="flex items-center gap-2 px-2 py-1.5">
          <span class="size-2 rounded-full" :class="col.dot" />
          <h3 class="text-sm font-semibold text-ink-900">{{ col.label }}</h3>
          <span class="ml-auto rounded-full bg-paper px-2 py-0.5 text-xs text-ink-500 tabular-nums">
            {{ byStatus.get(col.key)?.length ?? 0 }}
          </span>
        </header>

        <div v-if="(byStatus.get(col.key)?.length ?? 0) === 0" class="flex flex-1 items-center justify-center text-xs text-ink-300">
          暂无任务
        </div>

        <div class="mt-2 space-y-2.5">
          <article v-for="t in byStatus.get(col.key)" :key="t.task_id" class="rounded-xl border border-line p-3 transition-shadow hover:shadow-[0_8px_20px_-10px_rgba(20,41,61,0.15)]">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-brand-800 tabular-nums">{{ t.task_id }}</span>
              <span class="text-[10px] text-ink-300 tabular-nums">{{ timeText(t.created_at) }} 创建</span>
            </div>
            <p class="mt-2 line-clamp-2 text-[13px] leading-snug text-ink-700">{{ itemsText(t) }}</p>
            <p class="mt-1.5 text-[11px] text-ink-400">订单 {{ t.order_id }}</p>
            <p class="mt-1 text-xs font-medium text-ink-500 tabular-nums">{{ formatPriceCent(t.items.reduce((s, i) => s + i.price_cent * i.quantity, 0)) }}</p>
            <div v-if="t.status === 'PENDING'" class="mt-3">
              <button class="btn-accent w-full !py-1.5 text-xs" @click="transition(t, 'start')">开始制作</button>
            </div>
            <div v-else-if="t.status === 'PRODUCING'" class="mt-3 grid grid-cols-2 gap-2">
              <button class="btn-ghost !py-1.5 text-xs" @click="transition(t, 'complete')">完成</button>
              <button class="btn-accent !py-1.5 text-xs" @click="transition(t, 'ready')">出餐</button>
            </div>
            <div v-else-if="t.status === 'READY'" class="mt-3">
              <button class="btn-ghost w-full !py-1.5 text-xs" @click="transition(t, 'complete')">标记完成</button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
