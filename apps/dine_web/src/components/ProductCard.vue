<script setup lang="ts">
import type { Product } from '@/api/types'

import ProductImage from './ProductImage.vue'

defineProps<{ product: Product }>()

const emit = defineEmits<{
  open: [product: Product]
  add: [product: Product]
}>()

function formatPrice(cent: number): string {
  return `¥${(cent / 100).toFixed(cent % 100 === 0 ? 0 : 1)}`
}

function prepText(sec: number): string {
  return sec >= 60 ? `${Math.round(sec / 60)} 分钟` : `${sec} 秒`
}
</script>

<template>
  <article
    class="card group cursor-pointer overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_32px_-12px_rgba(20,41,61,0.18)]"
    @click="emit('open', product)"
  >
    <div class="relative">
      <ProductImage :src="product.image" :alt="product.name" rounded="rounded-none" class="aspect-[4/3]" />
      <div
        class="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-ink-900/70 via-ink-900/10 to-transparent px-3 pb-2.5 pt-8"
      >
        <span class="rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-medium text-ink-700 tabular-nums backdrop-blur">
          {{ product.calories_kcal }} kcal · {{ prepText(product.prep_time_sec) }}
        </span>
        <span
          v-if="product.status === 'SOLD_OUT'"
          class="rounded-full bg-danger-500 px-2 py-0.5 text-[11px] font-semibold text-white"
        >
          售罄
        </span>
        <span v-else class="rounded-full bg-success-500 px-2 py-0.5 text-[11px] font-semibold text-white">在售</span>
      </div>
    </div>

    <div class="p-4">
      <div class="flex items-start justify-between gap-2">
        <h3 class="font-display text-[15px] font-semibold text-ink-900">{{ product.name }}</h3>
        <span class="whitespace-nowrap text-xs text-ink-300">{{ product.serving_size }}</span>
      </div>
      <div class="mt-2 flex flex-wrap gap-1">
        <span v-for="tag in product.tags.slice(0, 3)" :key="tag" class="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] text-brand-700">
          {{ tag }}
        </span>
      </div>
      <div class="mt-3 flex items-center justify-between">
        <span class="text-lg font-semibold text-ink-900 tabular-nums">
          {{ formatPrice(product.price_cent) }}
        </span>
        <button
          class="btn-accent !px-3.5 !py-1.5 text-xs"
          :disabled="product.status !== 'ON_SALE'"
          @click.stop="emit('add', product)"
        >
          <svg viewBox="0 0 20 20" class="size-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M10 4v12M4 10h12" stroke-linecap="round" />
          </svg>
          {{ product.status === 'ON_SALE' ? '加入' : '售罄' }}
        </button>
      </div>
    </div>
  </article>
</template>
