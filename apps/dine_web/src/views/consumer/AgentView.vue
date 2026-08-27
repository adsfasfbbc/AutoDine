<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { nextTick, onMounted, ref } from 'vue'

import { agentApi, agentConnectionLabel } from '@/api/agent'
import type { Product } from '@/api/types'
import ProductImage from '@/components/ProductImage.vue'
import { ALLERGEN_LABELS } from '@/data/products'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { formatPriceCent } from '@/utils/format'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  products?: Product[]
}

const message = useMessage()
const menu = useMenuStore()
const cart = useCartStore()

const messages = ref<ChatMessage[]>([
  {
    role: 'assistant',
    text: '你好，我是 AutoDine 智能点餐助手 🍓\n告诉我你的口味偏好，比如「推荐低卡饮品」或「来点无乳的甜品」，我会从在售菜单里为你挑选。',
  },
])
const input = ref('')
const thinking = ref(false)
const listEl = ref<HTMLElement | null>(null)

const quickPrompts = ['推荐低卡饮品', '来点无乳的甜品', '预算 50 元内推荐', '推荐招牌甜品']

async function scrollToBottom(): Promise<void> {
  await nextTick()
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'smooth' })
}

onMounted(() => {
  void menu.load()
  void scrollToBottom()
})

async function send(text: string): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed || thinking.value) return
  const history = messages.value.map((item) => ({ role: item.role, content: item.text }))
  messages.value.push({ role: 'user', text: trimmed })
  input.value = ''
  thinking.value = true
  await scrollToBottom()

  try {
    const response = await agentApi.chat('consumer', {
      message: trimmed,
      history,
      context: { products: menu.products },
    })
    const productIds = new Set(response.suggestions?.filter((item) => item.kind === 'product').map((item) => item.id))
    const picks = menu.products.filter((product) => productIds.has(product.product_id))
    messages.value.push({ role: 'assistant', text: response.reply, products: picks })
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

function addToCart(product: Product): void {
  cart.add(product)
  message.success(`已加入：${product.name}`)
}
</script>

<template>
  <div class="anim-fade mx-auto grid max-w-5xl grid-cols-5 gap-6 items-start">
    <!-- 对话区 -->
    <section class="card col-span-3 flex h-[calc(100vh-10.5rem)] flex-col overflow-hidden">
      <header class="flex items-center gap-3 border-b border-line px-6 py-4">
        <span class="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 text-white">
          <svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
            <path d="M19 15l.7 2.1L21.8 18l-2.1.7L19 21l-.7-2.3-2.1-.7 2.1-.9L19 15Z" />
          </svg>
        </span>
        <div>
          <h2 class="font-display text-lg font-semibold text-brand-950">智能点餐助手</h2>
          <p class="flex items-center gap-1.5 text-xs text-ink-400">
            <span class="size-1.5 rounded-full bg-success-500" />
            已连接菜单 · 只推荐在售商品
          </p>
        </div>
        <span class="ml-auto rounded-full border border-line bg-paper px-3 py-1 text-[11px] font-medium text-ink-500">{{ agentConnectionLabel }}</span>
      </header>

      <div ref="listEl" class="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        <div v-for="(m, i) in messages" :key="i" class="flex gap-3" :class="m.role === 'user' ? 'flex-row-reverse' : ''">
          <span
            class="grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold"
            :class="m.role === 'user' ? 'bg-brand-900 text-white' : 'bg-accent-50 text-accent-600'"
          >
            {{ m.role === 'user' ? '我' : 'AI' }}
          </span>
          <div class="max-w-[85%]">
            <div
              class="whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-relaxed"
              :class="m.role === 'user' ? 'rounded-tr-sm bg-brand-900 text-white' : 'rounded-tl-sm bg-paper text-ink-700'"
            >
              {{ m.text }}
            </div>
            <div v-if="m.products && m.products.length > 0" class="mt-2 grid gap-2">
              <div v-for="p in m.products" :key="p.product_id" class="flex items-center gap-3 rounded-2xl border border-line bg-surface p-2.5 transition-shadow hover:shadow-[0_8px_20px_-12px_rgba(20,41,61,0.2)]">
                <ProductImage :src="p.image" :alt="p.name" rounded="rounded-xl" class="size-12 shrink-0" />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-ink-900">{{ p.name }}</p>
                  <p class="text-[11px] text-ink-400 tabular-nums">{{ p.calories_kcal }} kcal · {{ formatPriceCent(p.price_cent) }}</p>
                  <div v-if="p.allergens.length > 0" class="mt-0.5 flex gap-1">
                    <span v-for="a in p.allergens" :key="a" class="rounded bg-danger-50 px-1 py-0.5 text-[9px] text-danger-500">{{ ALLERGEN_LABELS[a] }}</span>
                  </div>
                </div>
                <button class="btn-accent !px-3 !py-1.5 text-xs" @click="addToCart(p)">加入</button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="thinking" class="flex gap-3">
          <span class="grid size-8 shrink-0 place-items-center rounded-full bg-accent-50 text-xs font-semibold text-accent-600">AI</span>
          <div class="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-paper px-4 py-3.5">
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400" />
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:120ms]" />
            <span class="size-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:240ms]" />
          </div>
        </div>
      </div>

      <footer class="border-t border-line px-4 py-3.5">
        <div class="mb-2.5 flex flex-wrap gap-1.5">
          <button v-for="q in quickPrompts" :key="q" class="chip hover:border-accent-300 hover:text-accent-600" :disabled="thinking" @click="send(q)">
            {{ q }}
          </button>
        </div>
        <form class="flex items-center gap-2" @submit.prevent="send(input)">
          <input v-model="input" type="text" class="field flex-1" aria-label="向助手提问" placeholder="输入你的口味偏好，例如：来一杯清爽的果茶…" :disabled="thinking" />
          <button class="btn-accent shrink-0" type="submit" :disabled="thinking || !input.trim()">
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
            发送
          </button>
        </form>
      </footer>
    </section>

    <!-- 购物车 -->
    <aside class="sticky top-24 col-span-2" aria-label="点餐上下文">
      <div class="card p-6">
        <h2 class="font-display text-lg font-semibold text-brand-950">已选清单</h2>
        <p class="mt-1 text-xs text-ink-400">助手推荐的商品可直接加入</p>
        <ul v-if="cart.lines.length > 0" class="mt-4 space-y-3">
          <li v-for="line in cart.lines" :key="line.product.product_id" class="flex items-center gap-3">
            <ProductImage :src="line.product.image" :alt="line.product.name" rounded="rounded-xl" class="size-11 shrink-0" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-ink-900">{{ line.product.name }}</p>
              <p class="text-xs text-ink-400 tabular-nums">¥{{ (line.product.price_cent / 100).toFixed(2) }} × {{ line.quantity }}</p>
            </div>
            <div class="flex items-center gap-1.5 rounded-full border border-line px-1 py-0.5">
              <button class="grid size-5 cursor-pointer place-items-center rounded-full text-ink-500 hover:bg-paper" aria-label="减少" @click="cart.setQuantity(line.product.product_id, line.quantity - 1)">−</button>
              <span class="min-w-4 text-center text-sm tabular-nums">{{ line.quantity }}</span>
              <button class="grid size-5 cursor-pointer place-items-center rounded-full text-ink-500 hover:bg-paper" aria-label="增加" @click="cart.add(line.product)">+</button>
            </div>
          </li>
        </ul>
        <p v-else class="mt-6 text-center text-sm text-ink-400">清单还是空的</p>
        <div class="mt-5 flex items-center justify-between border-t border-line pt-4">
          <span class="text-sm text-ink-500">合计</span>
          <span class="font-display text-xl font-semibold text-ink-900 tabular-nums">¥{{ (cart.totalPriceCent / 100).toFixed(2) }}</span>
        </div>
        <RouterLink to="/consumer/menu" class="btn-accent mt-3 w-full">
          去购物车确认下单 →
        </RouterLink>
      </div>
    </aside>
  </div>
</template>
