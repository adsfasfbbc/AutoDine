<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { nextTick, onMounted, ref } from 'vue'

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

function matchBudget(text: string): number | null {
  const m = text.match(/(\d+)\s*元/)
  return m ? Number(m[1]) : null
}

function recommend(text: string): Product[] {
  const budgetYuan = matchBudget(text)
  const lowCal = /低卡|低热量|热量低/.test(text)
  const noMilk = /无乳|不含乳/.test(text)
  const noEgg = /无蛋/.test(text)
  const noGluten = /无麸/.test(text)
  const wantsDrink = /饮品|茶|果茶|饮料/.test(text)
  const wantsCup = /甜品|杯|奶油杯/.test(text)
  const wantsCake = /蛋糕|芝士|烘焙/.test(text)
  const wantsHot = /热食|小吃|炸|薯条|鸡/.test(text)
  const wantsSignature = /招牌/.test(text)

  const candidates = menu.products.filter((p) => {
    if (p.status !== 'ON_SALE') return false
    if (lowCal && p.calories_kcal > 250) return false
    if (noMilk && p.allergens.includes('MILK')) return false
    if (noEgg && p.allergens.includes('EGG')) return false
    if (noGluten && p.allergens.includes('GLUTEN')) return false
    if (budgetYuan !== null && p.price_cent > budgetYuan * 100) return false
    if (wantsDrink && p.category !== 'DRINK') return false
    if (wantsCup && p.category !== 'CUP_DESSERT') return false
    if (wantsCake && p.category !== 'CAKE') return false
    if (wantsHot && p.category !== 'HOT_FOOD') return false
    if (wantsSignature && !p.tags.includes('招牌')) return false
    return true
  })

  const sortKey = lowCal ? (p: Product) => p.calories_kcal : (p: Product) => p.price_cent
  return [...candidates].sort((a, b) => sortKey(a) - sortKey(b)).slice(0, 4)
}

function buildReply(text: string, picks: Product[]): string {
  const lines: string[] = []
  if (picks.length === 0) {
    return '暂时没有完全符合的在售商品，试试放宽条件，比如去掉过敏原或预算限制？'
  }
  lines.push(`为你找到 ${picks.length} 款在售商品：`)
  if (/低卡|低热量/.test(text)) lines.push('已按热量从低到高排序，都是 250 kcal 以内的轻负担选择。')
  if (matchBudget(text) !== null) lines.push(`已按预算 ¥${matchBudget(text)} 以内筛选。`)
  lines.push('点击卡片右下角即可加入购物车。')
  return lines.join('\n')
}

async function send(text: string): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed || thinking.value) return
  messages.value.push({ role: 'user', text: trimmed })
  input.value = ''
  thinking.value = true
  await scrollToBottom()

  // 模拟 Agent 推理延迟
  await new Promise((r) => setTimeout(r, 650 + Math.random() * 400))

  const picks = recommend(trimmed)
  messages.value.push({ role: 'assistant', text: buildReply(trimmed, picks), products: picks })
  thinking.value = false
  await scrollToBottom()
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
            <span class="size-1.5 animate-bounce rounded-full bg-brand-400" />
            <span class="size-1.5 animate-bounce rounded-full bg-brand-400 [animation-delay:120ms]" />
            <span class="size-1.5 animate-bounce rounded-full bg-brand-400 [animation-delay:240ms]" />
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
          <input v-model="input" type="text" class="field flex-1" placeholder="输入你的口味偏好，例如：来一杯清爽的果茶…" :disabled="thinking" />
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
    <aside class="sticky top-24 col-span-2">
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
