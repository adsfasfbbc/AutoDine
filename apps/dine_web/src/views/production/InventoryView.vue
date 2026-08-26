<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import type { InventoryItem, InventoryMovement } from '@/api/types'
import StatCard from '@/components/StatCard.vue'

const inventory = ref<InventoryItem[]>([])
const movements = ref<InventoryMovement[]>([])
const loading = ref(true)

const reasonLabel: Record<InventoryMovement['reason'], string> = {
  CONSUME: '出库消耗',
  RESTOCK: '入库补货',
  WASTE: '损耗报废',
  ADJUST: '盘点调整',
  VISUAL_CORRECTION: '视觉校正',
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [inv, mv] = await Promise.all([api.listInventory(), api.listInventoryMovements()])
    inventory.value = inv
    movements.value = mv
  } finally {
    loading.value = false
  }
}

onMounted(load)

const tracked = computed(() => inventory.value.filter((i) => i.tracking === 'TRACKED'))
const lowStock = computed(() =>
  tracked.value.filter((i) => (i.unit === 'pcs' ? i.available < 20 : i.available < 1000)),
)
const defectiveTotal = computed(() =>
  tracked.value.reduce((s, i) => s + i.defective, 0),
)

function isLow(item: InventoryItem): boolean {
  if (item.tracking !== 'TRACKED') return false
  return item.unit === 'pcs' ? item.available < 20 : item.available < 1000
}

function amountText(delta: number): string {
  return `${delta > 0 ? '+' : ''}${delta}`
}
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="追踪原料" :value="String(tracked.length)" unit="种" tone="brand" />
      <StatCard label="低库存" :value="String(lowStock.length)" unit="种" tone="danger" />
      <StatCard label="异常原料量" :value="String(Math.round(defectiveTotal))" unit="g/pcs" tone="warning" />
      <StatCard label="今日流水" :value="String(movements.length)" unit="条" tone="accent" />
    </div>

    <div class="grid grid-cols-3 items-start gap-6">
      <!-- 库存表 -->
      <section class="card col-span-2 overflow-hidden">
        <header class="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 class="font-display text-lg font-semibold text-brand-900">原料库存</h2>
          <span class="text-xs text-ink-400">available = physical − defective − reserved</span>
        </header>
        <div v-if="loading" class="space-y-2 p-4">
          <div v-for="i in 6" :key="i" class="h-10 animate-pulse rounded-lg bg-brand-50" />
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-line text-left text-xs text-ink-400">
              <th class="px-6 py-3 font-medium">原料</th>
              <th class="px-3 py-3 font-medium">追踪</th>
              <th class="px-3 py-3 text-right font-medium">physical</th>
              <th class="px-3 py-3 text-right font-medium">defective</th>
              <th class="px-3 py-3 text-right font-medium">reserved</th>
              <th class="px-3 py-3 text-right font-medium">available</th>
              <th class="px-6 py-3 text-right font-medium">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr v-for="i in inventory" :key="i.ingredient_id" class="transition-colors hover:bg-paper/60">
              <td class="px-6 py-3">
                <p class="font-medium text-ink-900">{{ i.name }}</p>
                <p class="text-[11px] text-ink-300 tabular-nums">{{ i.ingredient_id }}</p>
              </td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="i.tracking === 'TRACKED' ? 'bg-brand-50 text-brand-700' : 'bg-paper text-ink-400'">
                  {{ i.tracking === 'TRACKED' ? 'TRACKED' : 'UNLIMITED' }}
                </span>
              </td>
              <td class="px-3 py-3 text-right tabular-nums">{{ i.physical }}</td>
              <td class="px-3 py-3 text-right tabular-nums" :class="i.defective > 0 ? 'text-danger-500' : 'text-ink-500'">{{ i.defective }}</td>
              <td class="px-3 py-3 text-right tabular-nums">{{ i.reserved }}</td>
              <td class="px-3 py-3 text-right font-semibold tabular-nums" :class="isLow(i) ? 'text-danger-500' : 'text-ink-900'">{{ i.available }}</td>
              <td class="px-6 py-3 text-right">
                <span v-if="i.tracking === 'UNLIMITED'" class="text-xs text-ink-300">不参与可售量</span>
                <span v-else-if="isLow(i)" class="rounded-full bg-danger-100 px-2 py-0.5 text-[11px] font-medium text-danger-500">低库存</span>
                <span v-else class="rounded-full bg-success-100 px-2 py-0.5 text-[11px] font-medium text-success-500">正常</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 最近流水 -->
      <section class="card p-6">
        <h2 class="font-display text-lg font-semibold text-brand-900">最近流水</h2>
        <ul class="mt-4 space-y-2.5">
          <li v-for="m in movements.slice(0, 12)" :key="m.movement_id" class="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
            <span
              class="grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold"
              :class="m.delta > 0 ? 'bg-success-100 text-success-500' : 'bg-danger-100 text-danger-500'"
            >
              {{ m.delta > 0 ? '+' : '−' }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-ink-900">{{ m.name }}</p>
              <p class="text-[11px] text-ink-400">{{ reasonLabel[m.reason] }} · {{ m.occurred_at.slice(11, 16) }}</p>
            </div>
            <span class="shrink-0 text-xs font-semibold tabular-nums" :class="m.delta > 0 ? 'text-success-500' : 'text-danger-500'">
              {{ amountText(m.delta) }} {{ m.unit }}
            </span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
