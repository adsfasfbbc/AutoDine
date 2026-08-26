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
const lowStock = computed(() => tracked.value.filter((i) => (i.unit === 'pcs' ? i.available < 20 : i.available < 1000)))
const wasteTotal = computed(() =>
  movements.value.filter((m) => m.reason === 'WASTE').reduce((s, m) => s + Math.abs(m.delta), 0),
)
const restockTotal = computed(() =>
  movements.value.filter((m) => m.reason === 'RESTOCK').reduce((s, m) => s + Math.abs(m.delta), 0),
)

function isLow(item: InventoryItem): boolean {
  if (item.tracking !== 'TRACKED') return false
  return item.unit === 'pcs' ? item.available < 20 : item.available < 1000
}
</script>

<template>
  <div class="anim-fade space-y-6">
    <div class="grid grid-cols-4 gap-4">
      <StatCard label="原料总数" :value="String(inventory.length)" unit="种" tone="brand" />
      <StatCard label="低库存" :value="String(lowStock.length)" unit="种" tone="danger" />
      <StatCard label="损耗量" :value="String(Math.round(wasteTotal))" unit="g/pcs" tone="warning" :delta="-12.5" />
      <StatCard label="补货量" :value="String(Math.round(restockTotal))" unit="g/pcs" tone="success" :delta="8.1" />
    </div>

    <div class="grid grid-cols-3 items-start gap-6">
      <section class="card col-span-2 overflow-hidden">
        <header class="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 class="font-display text-lg font-semibold text-brand-900">库存总览</h2>
          <span class="text-xs text-ink-400">TRACKED 原料参与可售量计算</span>
        </header>
        <div v-if="loading" class="space-y-2 p-4">
          <div v-for="i in 6" :key="i" class="h-10 animate-pulse rounded-lg bg-brand-50" />
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-line text-left text-xs text-ink-400">
              <th class="px-6 py-3 font-medium">原料</th>
              <th class="px-3 py-3 text-right font-medium">库存量</th>
              <th class="px-3 py-3 text-right font-medium">异常</th>
              <th class="px-3 py-3 text-right font-medium">可用</th>
              <th class="px-6 py-3 text-right font-medium">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr v-for="i in inventory" :key="i.ingredient_id" class="transition-colors hover:bg-paper/60">
              <td class="px-6 py-3">
                <p class="font-medium text-ink-900">{{ i.name }}</p>
                <p class="text-[11px] text-ink-300 tabular-nums">{{ i.ingredient_id }} · {{ i.unit }}</p>
              </td>
              <td class="px-3 py-3 text-right tabular-nums">{{ i.physical }}</td>
              <td class="px-3 py-3 text-right tabular-nums" :class="i.defective > 0 ? 'text-danger-500' : 'text-ink-300'">{{ i.defective }}</td>
              <td class="px-3 py-3 text-right font-semibold tabular-nums" :class="isLow(i) ? 'text-danger-500' : 'text-ink-900'">{{ i.available }}</td>
              <td class="px-6 py-3 text-right">
                <span v-if="i.tracking === 'UNLIMITED'" class="text-xs text-ink-300">无限量</span>
                <span v-else-if="isLow(i)" class="rounded-full bg-danger-100 px-2 py-0.5 text-[11px] font-medium text-danger-500">低库存</span>
                <span v-else class="rounded-full bg-success-100 px-2 py-0.5 text-[11px] font-medium text-success-500">正常</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <div class="space-y-6">
        <!-- 流水构成 -->
        <section class="card p-6">
          <h2 class="font-display text-lg font-semibold text-brand-900">流水构成</h2>
          <div class="mt-4 space-y-3">
            <div v-for="r in ['RESTOCK', 'CONSUME', 'WASTE', 'ADJUST'] as const" :key="r" class="flex items-center gap-3">
              <span class="w-16 shrink-0 text-xs text-ink-500">{{ reasonLabel[r] }}</span>
              <div class="h-2 flex-1 overflow-hidden rounded-full bg-paper">
                <div
                  class="h-full rounded-full"
                  :class="r === 'RESTOCK' ? 'bg-success-500' : r === 'CONSUME' ? 'bg-brand-500' : r === 'WASTE' ? 'bg-danger-500' : 'bg-warning-500'"
                  :style="{ width: `${Math.min(100, (movements.filter((m) => m.reason === r).length / Math.max(1, movements.length)) * 100)}%` }"
                />
              </div>
              <span class="w-8 shrink-0 text-right text-xs text-ink-400 tabular-nums">{{ movements.filter((m) => m.reason === r).length }}</span>
            </div>
          </div>
        </section>

        <!-- 最近流水 -->
        <section class="card p-6">
          <h2 class="font-display text-lg font-semibold text-brand-900">最近流水</h2>
          <ul class="mt-4 space-y-2">
            <li v-for="m in movements.slice(0, 6)" :key="m.movement_id" class="flex items-center gap-2 text-xs">
              <span class="font-medium text-ink-700">{{ m.name }}</span>
              <span class="text-ink-300">{{ reasonLabel[m.reason] }}</span>
              <span class="ml-auto tabular-nums" :class="m.delta > 0 ? 'text-success-500' : 'text-danger-500'">
                {{ m.delta > 0 ? '+' : '' }}{{ m.delta }} {{ m.unit }}
              </span>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>
