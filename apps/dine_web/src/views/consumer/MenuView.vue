<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, realtime } from '@/api'
import type { Product, ProductDetail, ProductStatus } from '@/api/types'
import CartPanel from '@/components/CartPanel.vue'
import ProductCard from '@/components/ProductCard.vue'
import ProductImage from '@/components/ProductImage.vue'
import { ALLERGEN_LABELS, CATEGORY_LABELS } from '@/data/products'
import type { ProductCategory } from '@/api/types'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { useOrderStore } from '@/stores/order'
import { formatPriceCent, formatSeconds } from '@/utils/format'

const menu = useMenuStore()
const cart = useCartStore()
const orderStore = useOrderStore()
const router = useRouter()
const message = useMessage()

const search = ref('')
const activeCategory = ref<string>('ALL')
const kcalFilter = ref<'ALL' | 'LOW' | 'MID' | 'HIGH'>('ALL')
const allergenFilter = ref<'ALL' | 'MILK' | 'EGG' | 'GLUTEN'>('ALL')
const selected = ref<Product | null>(null)
const detail = ref<ProductDetail | null>(null)
const busy = ref(false)

const categories = computed(() => {
  const counts = new Map<string, number>()
  for (const p of menu.products) counts.set(p.category, (counts.get(p.category) ?? 0) + 1)
  return [
    { key: 'ALL', label: '全部', count: menu.products.length },
    ...[...counts.entries()].map(([key, count]) => ({
      key,
      label: CATEGORY_LABELS[key as ProductCategory],
      count,
    })),
  ]
})

const kcalOptions: { k: 'ALL' | 'LOW' | 'MID' | 'HIGH'; label: string }[] = [
  { k: 'ALL', label: '全部' },
  { k: 'LOW', label: '≤250' },
  { k: 'MID', label: '251–450' },
  { k: 'HIGH', label: '>450' },
]
const allergenOptions: { k: 'ALL' | 'MILK' | 'EGG' | 'GLUTEN'; label: string }[] = [
  { k: 'ALL', label: '不限' },
  { k: 'MILK', label: '无乳' },
  { k: 'EGG', label: '无蛋' },
  { k: 'GLUTEN', label: '无麸' },
]

const filtered = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return menu.products.filter((p) => {
    if (activeCategory.value !== 'ALL' && p.category !== activeCategory.value) return false
    if (kcalFilter.value === 'LOW' && p.calories_kcal > 250) return false
    if (kcalFilter.value === 'MID' && (p.calories_kcal <= 250 || p.calories_kcal > 450)) return false
    if (kcalFilter.value === 'HIGH' && p.calories_kcal <= 450) return false
    if (allergenFilter.value !== 'ALL' && p.allergens.includes(allergenFilter.value)) return false
    if (kw && !`${p.name}${p.tags.join('')}${p.description ?? ''}`.toLowerCase().includes(kw)) return false
    return true
  })
})

let unsubscribe: (() => void) | undefined

onMounted(async () => {
  await menu.load()
  unsubscribe = realtime.on('menu.availability_changed', (msg) => {
    menu.updateFromEvent(msg.payload as { product_id: string; status: ProductStatus })
  })
})

onUnmounted(() => unsubscribe?.())

async function openDetail(product: Product): Promise<void> {
  selected.value = product
  detail.value = null
  detail.value = await api.getMenuItem(product.product_id)
}

function closeDetail(): void {
  selected.value = null
  detail.value = null
}

function addToCart(product: Product): void {
  cart.add(product)
  message.success(`已加入：${product.name}`)
}

async function checkout(): Promise<void> {
  if (cart.isEmpty || busy.value) return
  busy.value = true
  try {
    const items = cart.lines.map((l) => ({ product_id: l.product.product_id, quantity: l.quantity }))
    const order = await orderStore.placeOrder(items)
    cart.clear()
    message.success(`订单 ${order.order_id} 已提交，正在排队`)
    router.push({ name: 'consumer-orders' })
  } catch (e) {
    message.error(e instanceof Error ? e.message : '下单失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="anim-fade flex items-start gap-6">
    <!-- 分类栏 -->
    <nav class="sticky top-24 w-40 shrink-0" aria-label="菜单分类">
      <div class="card overflow-hidden p-2">
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="flex w-full cursor-pointer items-center justify-between rounded-xl px-3 py-2 text-sm transition-colors"
          :class="activeCategory === cat.key ? 'bg-brand-900 font-medium text-white' : 'text-ink-700 hover:bg-brand-50'"
          @click="activeCategory = cat.key"
        >
          <span>{{ cat.label }}</span>
          <span class="text-xs tabular-nums" :class="activeCategory === cat.key ? 'text-brand-200' : 'text-ink-300'">
            {{ cat.count }}
          </span>
        </button>
      </div>
    </nav>

    <!-- 菜单主体 -->
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-3">
        <div class="relative flex-1">
          <svg viewBox="0 0 24 24" class="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink-300" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input v-model="search" type="search" class="field !pl-10" placeholder="搜索菜品、标签…" />
        </div>
        <div class="flex items-center gap-1.5">
          <span class="mr-1 text-xs text-ink-400">热量</span>
          <button v-for="opt in kcalOptions" :key="opt.k" class="chip" :class="kcalFilter === opt.k && 'chip-active'" @click="kcalFilter = opt.k">
            {{ opt.label }}
          </button>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="mr-1 text-xs text-ink-400">过敏原</span>
          <button v-for="opt in allergenOptions" :key="opt.k" class="chip" :class="allergenFilter === opt.k && 'chip-active'" @click="allergenFilter = opt.k">
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- 骨架屏 -->
      <div v-if="menu.loading && !menu.loaded" class="mt-6 grid grid-cols-3 gap-5">
        <div v-for="i in 6" :key="i" class="card animate-pulse overflow-hidden">
          <div class="aspect-[4/3] bg-brand-100/60" />
          <div class="space-y-2 p-4">
            <div class="h-3.5 w-2/3 rounded bg-brand-100" />
            <div class="h-3 w-1/3 rounded bg-brand-100" />
          </div>
        </div>
      </div>

      <div v-else-if="menu.error" class="card mt-6 p-8 text-center text-sm text-danger-500">
        菜单加载失败：{{ menu.error }}
      </div>

      <!-- 空结果 -->
      <div v-else-if="filtered.length === 0" class="card mt-6 p-12 text-center">
        <p class="text-sm text-ink-400">没有符合条件的商品，试试调整筛选条件</p>
      </div>

      <div v-else class="mt-6 grid grid-cols-3 gap-5">
        <ProductCard v-for="p in filtered" :key="p.product_id" :product="p" @open="openDetail" @add="addToCart" />
      </div>
    </div>

    <!-- 持久购物车 -->
    <div class="w-[330px] shrink-0">
      <CartPanel :busy="busy" @checkout="checkout" />
    </div>

    <!-- 商品详情抽屉 -->
    <Transition name="drawer">
      <div v-if="selected" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-ink-900/30 backdrop-blur-[2px]" @click="closeDetail" />
        <div class="anim-rise relative flex h-full w-[460px] flex-col bg-surface shadow-2xl">
          <div class="relative">
            <ProductImage :src="selected.image" :alt="selected.name" rounded="rounded-none" class="aspect-[16/10]" />
            <button class="absolute right-4 top-4 grid size-9 cursor-pointer place-items-center rounded-full bg-white/90 text-ink-700 shadow transition-transform hover:scale-105" aria-label="关闭" @click="closeDetail">
              <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
            </button>
            <span v-if="selected.status === 'SOLD_OUT'" class="absolute bottom-4 left-4 rounded-full bg-danger-500 px-3 py-1 text-xs font-semibold text-white">已售罄</span>
          </div>

          <div class="flex-1 overflow-y-auto px-6 py-5">
            <div class="flex items-start justify-between gap-3">
              <div>
                <h2 class="font-display text-2xl font-semibold text-brand-950">{{ selected.name }}</h2>
                <p class="mt-1 text-xs text-ink-400">{{ CATEGORY_LABELS[selected.category] }} · {{ selected.serving_size }}</p>
              </div>
              <span class="whitespace-nowrap text-2xl font-semibold text-accent-600 tabular-nums">{{ formatPriceCent(selected.price_cent) }}</span>
            </div>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <span v-for="tag in selected.tags" :key="tag" class="chip">{{ tag }}</span>
            </div>

            <div class="mt-4 grid grid-cols-3 gap-2 rounded-2xl bg-paper p-3 text-center">
              <div>
                <p class="text-sm font-semibold text-ink-900 tabular-nums">{{ selected.calories_kcal }}</p>
                <p class="text-[11px] text-ink-400">kcal</p>
              </div>
              <div>
                <p class="text-sm font-semibold text-ink-900 tabular-nums">{{ formatSeconds(selected.prep_time_sec) }}</p>
                <p class="text-[11px] text-ink-400">制作时间</p>
              </div>
              <div>
                <p class="text-sm font-semibold text-ink-900">{{ selected.serving_size }}</p>
                <p class="text-[11px] text-ink-400">单份规格</p>
              </div>
            </div>

            <p v-if="selected.description" class="mt-4 text-sm leading-relaxed text-ink-500">{{ selected.description }}</p>

            <!-- 配料与过敏原 -->
            <h3 class="mt-6 text-sm font-semibold text-ink-900">配料（单份 BOM）</h3>
            <ul v-if="detail" class="mt-2 divide-y divide-line rounded-2xl border border-line">
              <li v-for="b in detail.bom" :key="b.ingredient_id" class="flex items-center justify-between px-4 py-2.5 text-sm">
                <span class="text-ink-700">{{ b.name }}</span>
                <span class="flex items-center gap-2 text-ink-400 tabular-nums">
                  <span v-if="b.unlimited" class="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-700">无限量</span>
                  {{ b.quantity }} {{ b.unit }}
                </span>
              </li>
            </ul>
            <div v-else class="mt-2 animate-pulse space-y-2">
              <div v-for="i in 4" :key="i" class="h-9 rounded-xl bg-brand-50" />
            </div>

            <h3 class="mt-6 text-sm font-semibold text-ink-900">过敏原提示</h3>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <template v-if="selected.allergens.length > 0">
                <span v-for="a in selected.allergens" :key="a" class="rounded-full bg-danger-100 px-2.5 py-1 text-xs font-medium text-danger-500">
                  {{ ALLERGEN_LABELS[a] }}
                </span>
              </template>
              <span v-else class="rounded-full bg-success-100 px-2.5 py-1 text-xs font-medium text-success-500">无主要常见过敏原</span>
            </div>
          </div>

          <footer class="border-t border-line px-6 py-4">
            <button class="btn-accent w-full" :disabled="selected.status !== 'ON_SALE'" @click="addToCart(selected); closeDetail()">
              {{ selected.status === 'ON_SALE' ? '加入购物车' : '已售罄' }}
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s var(--ease-standard);
}
.drawer-enter-active .anim-rise,
.drawer-leave-active .anim-rise {
  transition: transform 0.28s var(--ease-standard);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .anim-rise,
.drawer-leave-to .anim-rise {
  transform: translateX(40px);
}
</style>
