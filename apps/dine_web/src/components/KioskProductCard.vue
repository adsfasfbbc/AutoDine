<script setup lang="ts">
import type { Product } from '@/api/types'
import ProductImage from '@/components/ProductImage.vue'
import { formatPriceCent, formatSeconds } from '@/utils/format'

defineProps<{ product: Product }>()

const emit = defineEmits<{
  add: [product: Product]
}>()

function accessiblePrice(cent: number): string {
  return `${(cent / 100).toFixed(cent % 100 === 0 ? 0 : 2)} 元`
}
</script>

<template>
  <article class="kiosk-product group relative overflow-hidden rounded-[26px] border border-white/70 bg-white shadow-[0_18px_50px_-34px_rgba(12,27,41,0.5)]">
    <div class="relative overflow-hidden">
      <ProductImage
        :src="product.image"
        :alt="product.name"
        rounded="rounded-none"
        class="aspect-[4/3]"
      />
      <div class="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-brand-950/75 via-brand-950/10 to-transparent px-4 pb-3 pt-12">
        <span class="rounded-full bg-white/92 px-2.5 py-1 text-[11px] font-semibold text-brand-900 backdrop-blur">
          {{ product.calories_kcal }} kcal · {{ formatSeconds(product.prep_time_sec) }}
        </span>
        <span
          v-if="product.status !== 'ON_SALE'"
          class="rounded-full bg-danger-500 px-2.5 py-1 text-[11px] font-semibold text-white"
        >
          已售罄
        </span>
      </div>
    </div>

    <div class="p-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="truncate font-display text-lg font-semibold text-brand-950">{{ product.name }}</h2>
          <p class="mt-1 line-clamp-1 text-xs text-ink-400">{{ product.description }}</p>
        </div>
        <strong class="shrink-0 text-lg text-accent-600 tabular-nums">{{ formatPriceCent(product.price_cent) }}</strong>
      </div>

      <div class="mt-3 flex min-h-6 flex-wrap gap-1.5">
        <span
          v-for="tag in product.tags.slice(0, 3)"
          :key="tag"
          class="rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-medium text-brand-700"
        >
          {{ tag }}
        </span>
      </div>

      <button
        class="kiosk-stamp mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-brand-950 px-4 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:bg-ink-300"
        :aria-label="product.status === 'ON_SALE' ? `加入 ${product.name} ${accessiblePrice(product.price_cent)}` : `${product.name} 已售罄`"
        :disabled="product.status !== 'ON_SALE'"
        @click="emit('add', product)"
      >
        <svg v-if="product.status === 'ON_SALE'" viewBox="0 0 20 20" class="size-5" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M10 4v12M4 10h12" stroke-linecap="round" />
        </svg>
        {{ product.status === 'ON_SALE' ? '加入订单' : '暂时售罄' }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.kiosk-product {
  transition:
    transform 260ms var(--ease-standard),
    box-shadow 260ms var(--ease-standard);
}

.kiosk-product:hover {
  transform: translateY(-5px);
  box-shadow: 0 24px 60px -32px rgba(12, 27, 41, 0.62);
}
</style>
