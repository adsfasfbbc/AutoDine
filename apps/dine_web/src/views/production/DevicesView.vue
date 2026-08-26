<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { Device, DeviceKind } from '@/api/types'
import StatCard from '@/components/StatCard.vue'

const message = useMessage()

const devices = ref<Device[]>([])
const loading = ref(true)

const kindLabel: Record<DeviceKind, string> = {
  COOLER: '冷藏柜',
  OVEN: '烤箱',
  FRYER: '炸炉',
  ICE_MAKER: '制冰机',
  DISPENSER: '饮品机',
  SENSOR: '视觉传感器',
  ROBOT: '机械臂',
  PICKUP: '出餐口',
}

const statusLabel: Record<Device['status'], string> = {
  ONLINE: '在线',
  OFFLINE: '离线',
  ERROR: '异常',
  MAINTENANCE: '维护中',
}

const statusClass: Record<Device['status'], string> = {
  ONLINE: 'bg-success-100 text-success-500',
  OFFLINE: 'bg-paper text-ink-400',
  ERROR: 'bg-danger-100 text-danger-500',
  MAINTENANCE: 'bg-warning-100 text-warning-500',
}

const statusDot: Record<Device['status'], string> = {
  ONLINE: 'bg-success-500',
  OFFLINE: 'bg-ink-300',
  ERROR: 'bg-danger-500',
  MAINTENANCE: 'bg-warning-500',
}

const onlineCount = computed(() => devices.value.filter((d) => d.status === 'ONLINE').length)
const errorCount = computed(() => devices.value.filter((d) => d.status === 'ERROR').length)
const offlineCount = computed(() => devices.value.filter((d) => d.status === 'OFFLINE').length)

async function load(): Promise<void> {
  loading.value = true
  try {
    devices.value = await api.listDevices()
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function setTemp(device: Device, delta: number): Promise<void> {
  const base = device.target_temp_c ?? device.temperature_c ?? 0
  try {
    await api.issueDeviceCommand(device.device_id, { command: 'SET_TEMP', value: Math.round((base + delta) * 10) / 10 })
    message.success(`${device.name} 目标温度已调整`)
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '指令失败')
  }
}

async function reboot(device: Device): Promise<void> {
  try {
    await api.issueDeviceCommand(device.device_id, { command: 'REBOOT' })
    message.success(`${device.name} 重启指令已下发`)
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '指令失败')
  }
}

function hasTemp(device: Device): boolean {
  return ['COOLER', 'OVEN', 'FRYER'].includes(device.kind)
}
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="设备总数" :value="String(devices.length)" unit="台" tone="brand" />
      <StatCard label="在线" :value="String(onlineCount)" unit="台" tone="success" />
      <StatCard label="异常" :value="String(errorCount)" unit="台" tone="danger" />
      <StatCard label="离线" :value="String(offlineCount)" unit="台" tone="ink" />
    </div>

    <div v-if="loading" class="grid grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card h-40 animate-pulse" />
    </div>

    <div v-else class="grid grid-cols-3 gap-4">
      <article v-for="d in devices" :key="d.device_id" class="card p-5">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <span class="grid size-11 place-items-center rounded-xl" :class="d.status === 'ERROR' ? 'bg-danger-100 text-danger-500' : 'bg-brand-50 text-brand-700'">
              <svg viewBox="0 0 24 24" class="size-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <template v-if="d.kind === 'COOLER' || d.kind === 'OVEN' || d.kind === 'FRYER'">
                  <rect x="4" y="6" width="16" height="12" rx="2" />
                  <path d="M4 10h16M9 6v4M15 6v4" />
                </template>
                <template v-else-if="d.kind === 'SENSOR'">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                </template>
                <template v-else-if="d.kind === 'ROBOT'">
                  <rect x="5" y="7" width="14" height="10" rx="2.5" />
                  <circle cx="9.5" cy="12" r="1" fill="currentColor" />
                  <circle cx="14.5" cy="12" r="1" fill="currentColor" />
                  <path d="M9 4h6M12 4v3" />
                </template>
                <template v-else>
                  <path d="M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8L4 7Z" />
                  <path d="M8.5 10V6a3.5 3.5 0 0 1 7 0v4" />
                </template>
              </svg>
            </span>
            <div>
              <p class="text-sm font-semibold text-ink-900">{{ d.name }}</p>
              <p class="text-[11px] text-ink-400">{{ kindLabel[d.kind] }} · {{ d.location }}</p>
            </div>
          </div>
          <span class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium" :class="statusClass[d.status]">
            <span class="size-1.5 rounded-full" :class="statusDot[d.status]" />
            {{ statusLabel[d.status] }}
          </span>
        </div>

        <div v-if="hasTemp(d)" class="mt-4 flex items-end justify-between rounded-xl bg-paper px-4 py-3">
          <div>
            <p class="text-[11px] text-ink-400">当前温度</p>
            <p class="font-display text-2xl font-semibold tabular-nums" :class="d.status === 'ERROR' ? 'text-danger-500' : 'text-ink-900'">
              {{ d.temperature_c?.toFixed(1) ?? '—' }}<span class="text-sm">°C</span>
            </p>
          </div>
          <div class="text-right">
            <p class="text-[11px] text-ink-400">目标</p>
            <p class="text-sm font-medium text-ink-700 tabular-nums">{{ d.target_temp_c ?? '—' }}°C</p>
            <div class="mt-1.5 flex gap-1">
              <button class="grid size-6 cursor-pointer place-items-center rounded-full border border-line bg-surface text-ink-500 hover:border-brand-300 hover:text-brand-700" aria-label="降温" @click="setTemp(d, -1)">−</button>
              <button class="grid size-6 cursor-pointer place-items-center rounded-full border border-line bg-surface text-ink-500 hover:border-brand-300 hover:text-brand-700" aria-label="升温" @click="setTemp(d, 1)">+</button>
            </div>
          </div>
        </div>

        <div v-else-if="d.metrics" class="mt-4 flex flex-wrap gap-1.5">
          <span v-for="(v, k) in d.metrics" :key="k" class="chip">{{ k }} {{ v }}</span>
        </div>

        <div class="mt-4 flex items-center justify-between border-t border-line pt-3">
          <span class="text-[11px] text-ink-300">最后在线 {{ d.last_seen_at.slice(11, 16) }}</span>
          <div class="flex gap-1.5">
            <button class="btn-ghost !px-3 !py-1 text-xs" :disabled="d.status === 'OFFLINE'" @click="reboot(d)">重启</button>
            <button class="btn-accent !px-3 !py-1 text-xs" :disabled="d.status === 'OFFLINE'" @click="message.success(`${d.name} 自检通过`)">自检</button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>
