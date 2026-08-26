<script setup lang="ts">
import { computed } from 'vue'

import ProductImage from '@/components/ProductImage.vue'
import { useCartStore } from '@/stores/cart'

withDefaults(defineProps<{ busy?: boolean; title?: string }>(), {
  busy: false,
  title: '已选商品',
})

const emit = defineEmits<{ checkout: [] }>()

const cart = useCartStore()

const totalText = computed(() => `¥${(cart.totalPriceCent / 100).toFixed(2)}`)
const waitText = computed(() => {
  const sec = cart.maxPrepSec
  if (sec <= 0) return '—'
  return sec >= 60 ? `约 ${Math.round(sec / 60)} 分钟` : `约 ${sec} 秒`
})
</script>

<template>
  <aside
    class="card sticky top-24 flex max-h-[calc(100vh-7rem)] flex-col overflow-hidden"
    :aria-label="title"
  >
    <header class="flex items-center justify-between border-b border-line px-5 py-4">
      <h2 class="font-display text-base font-semibold text-brand-900">{{ title }}</h2>
      <span class="rounded-full bg-accent-50 px-2.5 py-0.5 text-xs font-medium text-accent-600 tabular-nums">
        {{ cart.totalCount }} 件
      </span>
    </header>

    <div v-if="cart.isEmpty" class="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <div class="grid size-14 place-items-center rounded-full bg-paper text-brand-300">
        <svg viewBox="0 0 24 24" class="size-7" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
          <path d="M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8L4 7Z" stroke-linejoin="round" />
          <path d="M8.5 10V6a3.5 3.5 0 0 1 7 0v4" stroke-linecap="round" />
        </svg>
      </div>
      <p class="text-sm text-ink-400">购物车还是空的<br />去菜单里挑几样吧</p>
    </div>

    <ul v-else class="flex-1 space-y-3 overflow-y-auto px-5 py-4">
      <li v-for="line in cart.lines" :key="line.product.product_id" class="flex items-center gap-3">
        <ProductImage :src="line.product.image" :alt="line.product.name" rounded="rounded-xl" class="size-14 shrink-0" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-ink-900">{{ line.product.name }}</p>
          <p class="text-xs text-ink-400 tabular-nums">¥{{ (line.product.price_cent / 100).toFixed(2) }}</p>
        </div>
        <div class="flex items-center gap-1.5 rounded-full border border-line px-1 py-0.5">
          <button
            class="grid size-6 place-items-center rounded-full text-ink-500 transition-colors hover:bg-paper hover:text-brand-700"
            aria-label="减少"
            @click="cart.setQuantity(line.product.product_id, line.quantity - 1)"
          >
            −
          </button>
          <span class="min-w-5 text-center text-sm tabular-nums">{{ line.quantity }}</span>
          <button
            class="grid size-6 place-items-center rounded-full text-ink-500 transition-colors hover:bg-paper hover:text-brand-700"
            aria-label="增加"
            @click="cart.add(line.product)"
          >
            +
          </button>
        </div>
      </li>
    </ul>

    <footer class="border-t border-line px-5 py-4">
      <div class="flex items-center justify-between text-sm">
        <span class="text-ink-500">小计</span>
        <span class="font-semibold text-ink-900 tabular-nums">{{ totalText }}</span>
      </div>
      <div class="mt-1 flex items-center justify-between text-xs text-ink-400">
        <span>预计制作</span>
        <span class="tabular-nums">{{ waitText }}</span>
      </div>
      <button class="btn-accent mt-3 w-full" :disabled="cart.isEmpty || busy" @click="emit('checkout')">
        {{ busy ? '提交中…' : '确认订单' }}
      </button>
    </footer>
  </aside>
</template>
