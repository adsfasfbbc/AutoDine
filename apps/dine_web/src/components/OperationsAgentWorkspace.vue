<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { api } from '@/api'
import { agentApi, agentConnectionLabel } from '@/api/agent'
import type { AgentHistoryMessage } from '@/api/agent'
import type { Alarm, AnalyticsSummary, Device, InventoryItem, ProductionTask, QualityEvent } from '@/api/types'
import { formatPriceCent } from '@/utils/format'

const props = defineProps<{ mode: 'production' | 'admin' }>()

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

const config = computed(() => props.mode === 'production'
  ? {
      title: '生产协同助手',
      eyebrow: 'KITCHEN COPILOT',
      intro: '我会结合当前制作任务、设备、库存和质检状态给出排程建议。你可以问我「现在先做什么？」',
      status: '已读取生产现场 · 仅提供建议',
      prompts: ['现在优先做什么？', '检查设备异常', '盘点现场风险', '如何降低积压？'],
      asideLabel: '生产上下文',
      accentClass: 'bg-brand-900',
      avatarClass: 'bg-brand-50 text-brand-700',
      sendClass: 'btn-brand',
    }
  : {
      title: '经营决策助手',
      eyebrow: 'MANAGER COPILOT',
      intro: '我会结合今日经营指标和实时告警梳理重点。你可以问我「今天经营表现如何？」',
      status: '已读取经营数据 · 仅提供建议',
      prompts: ['今天经营表现如何？', '梳理当前风险', '等待时间是否健康？', '给我一份巡店重点'],
      asideLabel: '管理上下文',
      accentClass: 'bg-accent-500',
      avatarClass: 'bg-accent-50 text-accent-600',
      sendClass: 'btn-accent',
    })

const messages = ref<ChatMessage[]>([])
const input = ref('')
const thinking = ref(false)
const loading = ref(true)
const contextReady = ref(false)
const loadError = ref('')
const listEl = ref<HTMLElement | null>(null)

const tasks = ref<ProductionTask[]>([])
const inventory = ref<InventoryItem[]>([])
const devices = ref<Device[]>([])
const qualityEvents = ref<QualityEvent[]>([])
const analytics = ref<AnalyticsSummary | null>(null)
const alarms = ref<Alarm[]>([])

const pendingTasks = computed(() => tasks.value.filter((item) => item.status === 'PENDING').length)
const producingTasks = computed(() => tasks.value.filter((item) => item.status === 'PRODUCING').length)
const readyTasks = computed(() => tasks.value.filter((item) => item.status === 'READY').length)
const lowStock = computed(() => inventory.value.filter((item) => item.tracking === 'TRACKED' && item.available <= 10))
const abnormalDevices = computed(() => devices.value.filter((item) => item.status !== 'ONLINE'))
const openQuality = computed(() => qualityEvents.value.filter((item) => item.status !== 'HANDLED'))
const openAlarms = computed(() => alarms.value.filter((item) => item.status === 'OPEN'))
const contextStatus = computed(() => {
  if (loading.value) return '正在读取业务数据…'
  if (!contextReady.value) return '实时数据暂不可用'
  return config.value.status
})

const metrics = computed(() => props.mode === 'production'
  ? [
      { label: '待制作', value: pendingTasks.value, unit: '单', tone: 'text-accent-600' },
      { label: '制作中', value: producingTasks.value, unit: '单', tone: 'text-brand-700' },
      { label: '设备异常', value: abnormalDevices.value.length, unit: '台', tone: 'text-danger-500' },
      { label: '低库存', value: lowStock.value.length, unit: '项', tone: 'text-warning-500' },
    ]
  : [
      { label: '今日订单', value: analytics.value?.orders ?? '—', unit: '单', tone: 'text-brand-700' },
      { label: '营业额', value: analytics.value ? formatPriceCent(analytics.value.revenue_cent) : '—', unit: '', tone: 'text-accent-600' },
      { label: '平均等待', value: analytics.value ? Math.round(analytics.value.avg_wait_sec / 60) : '—', unit: '分', tone: 'text-success-500' },
      { label: '待处理告警', value: openAlarms.value.length, unit: '条', tone: 'text-danger-500' },
    ])

const productionPriorities = computed(() => tasks.value
  .filter((item) => item.status === 'PENDING' || item.status === 'PRODUCING')
  .slice(0, 4))

async function scrollToBottom(): Promise<void> {
  await nextTick()
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'smooth' })
}

async function loadContext(): Promise<void> {
  loading.value = true
  contextReady.value = false
  loadError.value = ''
  try {
    if (props.mode === 'production') {
      const [taskData, inventoryData, deviceData, qualityData] = await Promise.all([
        api.listProductionTasks(),
        api.listInventory(),
        api.listDevices(),
        api.listQualityEvents(),
      ])
      tasks.value = taskData
      inventory.value = inventoryData
      devices.value = deviceData
      qualityEvents.value = qualityData
    } else {
      const [summary, alarmData] = await Promise.all([
        api.getAnalyticsSummary('store-main', new Date(Date.now() - 86_400_000).toISOString(), new Date().toISOString()),
        api.listAlarms('store-main'),
      ])
      analytics.value = summary
      alarms.value = alarmData
    }
    contextReady.value = true
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '上下文数据加载失败'
  } finally {
    loading.value = false
  }
}

function buildContext(): Record<string, unknown> {
  if (props.mode === 'production') {
    return {
      pendingTasks: pendingTasks.value,
      producingTasks: producingTasks.value,
      readyTasks: readyTasks.value,
      riskCount: abnormalDevices.value.length + lowStock.value.length + openQuality.value.length,
    }
  }
  return {
    orders: analytics.value?.orders ?? 0,
    revenueCent: analytics.value?.revenue_cent ?? 0,
    avgWaitMinutes: analytics.value ? Math.round(analytics.value.avg_wait_sec / 60) : 0,
    openAlarms: openAlarms.value.length,
  }
}

async function send(text: string): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed || thinking.value || !contextReady.value) return
  const history: AgentHistoryMessage[] = messages.value.map((item) => ({ role: item.role, content: item.text }))
  messages.value.push({ role: 'user', text: trimmed })
  input.value = ''
  thinking.value = true
  await scrollToBottom()
  try {
    const response = await agentApi.chat(props.mode === 'production' ? 'kitchen' : 'manager', {
      message: trimmed,
      history,
      context: buildContext(),
    })
    messages.value.push({ role: 'assistant', text: response.reply })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      text: error instanceof Error ? `助手暂时无法响应：${error.message}` : '助手暂时无法响应，请稍后再试。',
    })
  } finally {
    thinking.value = false
    await scrollToBottom()
  }
}

onMounted(() => {
  messages.value = [{ role: 'assistant', text: config.value.intro }]
  void loadContext()
  void scrollToBottom()
})
</script>

<template>
  <div class="anim-fade mx-auto grid max-w-[1440px] grid-cols-5 items-start gap-6">
    <section class="card col-span-3 flex h-[calc(100vh-7rem)] min-h-[620px] flex-col overflow-hidden">
      <header class="flex items-center gap-3 border-b border-line px-6 py-4">
        <span class="relative grid size-11 place-items-center rounded-2xl text-white shadow-[0_10px_24px_-14px_rgba(20,41,61,0.8)]" :class="config.accentClass">
          <svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
            <path d="M19 15.5l.7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7.7-2.1Z" />
          </svg>
          <span class="absolute -right-0.5 -top-0.5 size-2.5 rounded-full border-2 border-white bg-success-500" />
        </span>
        <div class="min-w-0">
          <p class="text-[10px] font-semibold tracking-[0.18em] text-ink-400">{{ config.eyebrow }}</p>
          <h2 class="font-display text-xl font-semibold text-brand-950">{{ config.title }}</h2>
          <p class="mt-0.5 flex items-center gap-1.5 text-xs text-ink-400">
            <span class="size-1.5 rounded-full bg-success-500" />
            {{ contextStatus }}
          </p>
        </div>
        <span class="ml-auto rounded-full border border-line bg-paper px-3 py-1 text-[11px] font-medium text-ink-500">{{ agentConnectionLabel }}</span>
      </header>

      <div ref="listEl" class="flex-1 space-y-5 overflow-y-auto px-6 py-5" aria-live="polite">
        <div v-for="(item, index) in messages" :key="index" class="flex gap-3" :class="item.role === 'user' ? 'flex-row-reverse' : ''">
          <span class="grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold" :class="item.role === 'user' ? 'bg-ink-900 text-white' : config.avatarClass">
            {{ item.role === 'user' ? '我' : 'AI' }}
          </span>
          <div class="max-w-[82%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-6" :class="item.role === 'user' ? 'rounded-tr-sm bg-ink-900 text-white' : 'rounded-tl-sm bg-paper text-ink-700'">
            {{ item.text }}
          </div>
        </div>

        <div v-if="thinking" class="flex gap-3">
          <span class="grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold" :class="config.avatarClass">AI</span>
          <div class="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-paper px-4 py-3.5" aria-label="助手正在思考">
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400" />
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:120ms]" />
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:240ms]" />
          </div>
        </div>
      </div>

      <footer class="border-t border-line bg-white px-4 py-3.5">
        <div class="mb-2.5 flex flex-wrap gap-1.5">
          <button v-for="prompt in config.prompts" :key="prompt" class="chip hover:border-brand-300 hover:text-brand-700" :disabled="thinking || !contextReady" @click="send(prompt)">
            {{ prompt }}
          </button>
        </div>
        <form class="flex items-center gap-2" @submit.prevent="send(input)">
          <input v-model="input" class="field flex-1" type="text" aria-label="向助手提问" placeholder="输入问题，让助手结合右侧实时数据分析…" :disabled="thinking || !contextReady" />
          <button type="submit" class="shrink-0" :class="config.sendClass" :disabled="thinking || !contextReady || !input.trim()">
            发送
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        </form>
        <p class="mt-2 text-center text-[10px] text-ink-300">当前助手只生成建议，不会自动执行生产或管理操作</p>
      </footer>
    </section>

    <aside class="card sticky top-20 col-span-2 h-[calc(100vh-7rem)] min-h-[620px] overflow-y-auto p-0" :aria-label="config.asideLabel">
      <div class="border-b border-line px-5 py-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-[10px] font-semibold tracking-[0.16em] text-ink-400">LIVE CONTEXT</p>
            <h3 class="mt-0.5 font-display text-lg font-semibold text-brand-950">{{ props.mode === 'production' ? '现场态势' : '经营快照' }}</h3>
          </div>
          <button class="btn-ghost !px-3 !py-1.5 text-xs" :disabled="loading" @click="loadContext">刷新</button>
        </div>
        <p class="mt-2 text-xs leading-5 text-ink-400">这里展示现有业务接口的关键数据，并作为后续 Agent 的上下文来源。</p>
      </div>

      <div v-if="loading" class="space-y-3 p-5">
        <div class="grid grid-cols-2 gap-3">
          <div v-for="item in 4" :key="item" class="h-20 animate-pulse rounded-2xl bg-brand-50" />
        </div>
        <div class="h-44 animate-pulse rounded-2xl bg-paper" />
      </div>
      <div v-else-if="loadError" class="p-5">
        <div class="rounded-2xl border border-danger-100 bg-danger-50 p-4 text-sm text-danger-500">
          <p class="font-semibold">数据暂时不可用</p>
          <p class="mt-1 text-xs leading-5">{{ loadError }}</p>
          <button class="mt-3 underline" @click="loadContext">重新加载</button>
        </div>
      </div>
      <div v-else class="p-5">
        <dl class="grid grid-cols-2 gap-x-5 gap-y-4 border-b border-line pb-5">
          <div v-for="metric in metrics" :key="metric.label">
            <dt class="text-[11px] font-medium text-ink-400">{{ metric.label }}</dt>
            <dd class="mt-1 font-display text-2xl font-semibold tabular-nums" :class="metric.tone">
              {{ metric.value }}<span class="ml-1 text-xs font-normal text-ink-400">{{ metric.unit }}</span>
            </dd>
          </div>
        </dl>

        <section v-if="props.mode === 'production'" class="pt-5">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-semibold text-ink-900">任务焦点</h4>
            <RouterLink to="/production/tasks" class="text-xs font-medium text-brand-700 hover:text-brand-900">查看任务 →</RouterLink>
          </div>
          <ul v-if="productionPriorities.length" class="mt-3 divide-y divide-line">
            <li v-for="task in productionPriorities" :key="task.task_id" class="flex items-center gap-3 py-3 first:pt-0">
              <span class="size-2 shrink-0 rounded-full" :class="task.status === 'PRODUCING' ? 'bg-brand-500' : 'bg-accent-500'" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-xs font-medium text-ink-800">{{ task.items.map((item) => `${item.name}×${item.quantity}`).join('、') }}</p>
                <p class="mt-0.5 text-[10px] text-ink-400">{{ task.task_id }} · {{ task.status === 'PRODUCING' ? '制作中' : '待制作' }}</p>
              </div>
            </li>
          </ul>
          <p v-else class="mt-3 rounded-xl bg-paper px-3 py-4 text-center text-xs text-ink-400">当前没有待关注任务</p>

          <div class="mt-5 flex items-center justify-between border-t border-line pt-5">
            <h4 class="text-sm font-semibold text-ink-900">现场风险</h4>
            <span class="text-xs text-ink-400">质检 {{ openQuality.length }} · 设备 {{ abnormalDevices.length }}</span>
          </div>
          <p class="mt-2 text-xs leading-5 text-ink-500">{{ lowStock.length ? `${lowStock.slice(0, 3).map((item) => item.name).join('、')} 库存偏低` : '关键原料库存充足' }}</p>
        </section>

        <section v-else class="pt-5">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-semibold text-ink-900">重点告警</h4>
            <RouterLink to="/admin/alarms" class="text-xs font-medium text-brand-700 hover:text-brand-900">告警中心 →</RouterLink>
          </div>
          <ul v-if="openAlarms.length" class="mt-3 divide-y divide-line">
            <li v-for="alarm in openAlarms.slice(0, 4)" :key="alarm.alarm_id" class="flex gap-3 py-3 first:pt-0">
              <span class="mt-1 size-2 shrink-0 rounded-full" :class="alarm.severity === 'CRITICAL' ? 'bg-danger-500' : alarm.severity === 'WARNING' ? 'bg-warning-500' : 'bg-brand-400'" />
              <div class="min-w-0">
                <p class="truncate text-xs font-medium text-ink-800">{{ alarm.title }}</p>
                <p class="mt-0.5 line-clamp-2 text-[10px] leading-4 text-ink-400">{{ alarm.message }}</p>
              </div>
            </li>
          </ul>
          <p v-else class="mt-3 rounded-xl bg-success-100 px-3 py-4 text-center text-xs text-success-500">当前没有待处理告警</p>

          <div class="mt-5 border-t border-line pt-5">
            <div class="flex items-center justify-between text-xs">
              <span class="font-medium text-ink-700">设备在线率</span>
              <span class="font-semibold text-brand-800">{{ analytics ? `${analytics.online_devices}/${analytics.total_devices}` : '—' }}</span>
            </div>
            <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-brand-50">
              <div class="h-full rounded-full bg-brand-600 transition-[width] duration-200" :style="{ width: analytics?.total_devices ? `${analytics.online_devices / analytics.total_devices * 100}%` : '0%' }" />
            </div>
          </div>
        </section>
      </div>
    </aside>
  </div>
</template>
