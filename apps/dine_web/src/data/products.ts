import type { Allergen, BomItem, Product, ProductCategory } from '@/api/types'

/**
 * P0 演示商品数据
 * 来源：《autoDine_菜单与BOM数据规范_开发交付版_v1.0.docx》
 * P0 8 个商品：P001、P003、P004、P011、P012、P021、P027、P029
 * 覆盖果茶、杯装甜品、蛋糕与热食，同时覆盖草莓/芒果视觉库存联动。
 *
 * 说明：
 * - `price_cent` 为人民币分；显示时统一由 price_cent 换算。
 * - `stock` 为 Mock 专用字段，用于演示库存驱动的在售/售罄联动；
 *   真实接入后由 Core 菜单可售量接口提供，前端不维护。
 * - `image` 指向 public/img/ 下的演示配图。
 */

export const CATEGORY_LABELS: Record<ProductCategory, string> = {
  DRINK: '饮品',
  CUP_DESSERT: '杯装甜品',
  CAKE: '蛋糕烘焙',
  HOT_FOOD: '热食小吃',
  LIGHT_MEAL: '轻食',
}

export const ALLERGEN_LABELS: Record<Allergen, string> = {
  MILK: '乳制品',
  EGG: '鸡蛋',
  GLUTEN: '麸质',
  SOY: '大豆',
  SEAFOOD: '海鲜',
  PEANUT: '花生',
  TREE_NUT: '坚果',
}

export interface ProductSeed extends Product {
  stock: number
  bom: BomItem[]
}

export const P0_PRODUCTS: ProductSeed[] = [
  {
    product_id: 'P001',
    name: '金桔柠檬水',
    category: 'DRINK',
    price_cent: 1500,
    calories_kcal: 125,
    serving_size: '500 ml',
    prep_time_sec: 120,
    status: 'ON_SALE',
    tags: ['果茶', '酸甜', '清爽'],
    allergens: [],
    stock: 48,
    image: '/img/p001.jpg',
    description: '香水柠檬与金桔现捣出汁，蜂蜜调和，冰爽解腻的招牌果茶。',
    bom: [
      { ingredient_id: 'I001', name: '香水柠檬', quantity: 1, unit: 'pcs' },
      { ingredient_id: 'I002', name: '金桔', quantity: 3, unit: 'pcs' },
      { ingredient_id: 'I003', name: '蜂蜜', quantity: 20, unit: 'g' },
      { ingredient_id: 'I005', name: '纯净水', quantity: 300, unit: 'ml', unlimited: true },
      { ingredient_id: 'I004', name: '冰块', quantity: 100, unit: 'g', unlimited: true },
    ],
  },
  {
    product_id: 'P003',
    name: '草莓茉莉冰茶',
    category: 'DRINK',
    price_cent: 1800,
    calories_kcal: 135,
    serving_size: '500 ml',
    prep_time_sec: 180,
    status: 'ON_SALE',
    tags: ['草莓', '果茶', '清爽'],
    allergens: [],
    stock: 36,
    image: '/img/p003.jpg',
    description: '当季草莓与茉莉茶汤的轻盈组合，果香清透，微甜不腻。',
    bom: [
      { ingredient_id: 'I011', name: '草莓', quantity: 80, unit: 'g' },
      { ingredient_id: 'I006', name: '茉莉茶汤', quantity: 280, unit: 'ml' },
      { ingredient_id: 'I025', name: '糖浆', quantity: 18, unit: 'g' },
      { ingredient_id: 'I004', name: '冰块', quantity: 100, unit: 'g', unlimited: true },
    ],
  },
  {
    product_id: 'P004',
    name: '芒果乌龙茶',
    category: 'DRINK',
    price_cent: 1800,
    calories_kcal: 150,
    serving_size: '500 ml',
    prep_time_sec: 180,
    status: 'ON_SALE',
    tags: ['芒果', '乌龙', '果茶'],
    allergens: [],
    stock: 32,
    image: '/img/p004.jpg',
    description: '台农芒果肉与醇厚乌龙茶汤，热带果香与茶感平衡的一杯。',
    bom: [
      { ingredient_id: 'I012', name: '芒果', quantity: 100, unit: 'g' },
      { ingredient_id: 'I007', name: '乌龙茶汤', quantity: 280, unit: 'ml' },
      { ingredient_id: 'I025', name: '糖浆', quantity: 15, unit: 'g' },
      { ingredient_id: 'I004', name: '冰块', quantity: 100, unit: 'g', unlimited: true },
    ],
  },
  {
    product_id: 'P011',
    name: '草莓奶油杯',
    category: 'CUP_DESSERT',
    price_cent: 2600,
    calories_kcal: 440,
    serving_size: '1 cup',
    prep_time_sec: 240,
    status: 'ON_SALE',
    tags: ['草莓', '奶油', '招牌'],
    allergens: ['MILK', 'EGG', 'GLUTEN'],
    stock: 24,
    image: '/img/p011.jpg',
    description: '草莓、轻盈淡奶油与蛋糕胚层层叠叠，招牌杯装甜品。',
    bom: [
      { ingredient_id: 'I011', name: '草莓', quantity: 120, unit: 'g' },
      { ingredient_id: 'I010', name: '淡奶油', quantity: 80, unit: 'g' },
      { ingredient_id: 'I026', name: '蛋糕胚', quantity: 70, unit: 'g' },
    ],
  },
  {
    product_id: 'P012',
    name: '芒果奶油杯',
    category: 'CUP_DESSERT',
    price_cent: 2600,
    calories_kcal: 450,
    serving_size: '1 cup',
    prep_time_sec: 240,
    status: 'ON_SALE',
    tags: ['芒果', '奶油'],
    allergens: ['MILK', 'EGG', 'GLUTEN'],
    stock: 18,
    image: '/img/p012.jpg',
    description: '大块芒果肉配轻乳奶油，果香浓郁的热带风味甜杯。',
    bom: [
      { ingredient_id: 'I012', name: '芒果', quantity: 120, unit: 'g' },
      { ingredient_id: 'I010', name: '淡奶油', quantity: 80, unit: 'g' },
      { ingredient_id: 'I026', name: '蛋糕胚', quantity: 70, unit: 'g' },
    ],
  },
  {
    product_id: 'P021',
    name: '草莓芝士蛋糕',
    category: 'CAKE',
    price_cent: 3200,
    calories_kcal: 510,
    serving_size: '1 slice',
    prep_time_sec: 120,
    status: 'ON_SALE',
    tags: ['草莓', '芝士', '招牌'],
    allergens: ['MILK', 'EGG', 'GLUTEN'],
    stock: 16,
    image: '/img/p021.jpg',
    description: '奶油奶酪芝士体配新鲜草莓，绵密与果酸相得益彰。',
    bom: [
      { ingredient_id: 'I030', name: '奶油奶酪', quantity: 100, unit: 'g' },
      { ingredient_id: 'I011', name: '草莓', quantity: 80, unit: 'g' },
      { ingredient_id: 'I026', name: '蛋糕胚', quantity: 70, unit: 'g' },
      { ingredient_id: 'I010', name: '淡奶油', quantity: 40, unit: 'g' },
      { ingredient_id: 'I031', name: '吉利丁', quantity: 3, unit: 'g' },
    ],
  },
  {
    product_id: 'P027',
    name: '黄金薯条',
    category: 'HOT_FOOD',
    price_cent: 1500,
    calories_kcal: 510,
    serving_size: '1 serving',
    prep_time_sec: 360,
    status: 'ON_SALE',
    tags: ['咸香', '热食', '经典'],
    allergens: [],
    stock: 40,
    image: '/img/p027.jpg',
    description: '现炸金黄薯条，外脆内糯，配番茄酱的经典热食。',
    bom: [
      { ingredient_id: 'I041', name: '冷冻薯条', quantity: 180, unit: 'g' },
      { ingredient_id: 'I042', name: '食用油', quantity: 10, unit: 'g' },
      { ingredient_id: 'I043', name: '食盐', quantity: 2, unit: 'g' },
      { ingredient_id: 'I044', name: '番茄酱', quantity: 20, unit: 'g' },
    ],
  },
  {
    product_id: 'P029',
    name: '盐酥鸡',
    category: 'HOT_FOOD',
    price_cent: 2200,
    calories_kcal: 570,
    serving_size: '1 serving',
    prep_time_sec: 480,
    status: 'ON_SALE',
    tags: ['鸡肉', '咸香', '热食'],
    allergens: ['GLUTEN'],
    stock: 28,
    image: '/img/p029.jpg',
    description: '鸡腿肉裹粉现炸，外酥里嫩，撒椒盐提味的热门小吃。',
    bom: [
      { ingredient_id: 'I048', name: '鸡腿肉', quantity: 180, unit: 'g' },
      { ingredient_id: 'I049', name: '裹粉', quantity: 30, unit: 'g' },
      { ingredient_id: 'I042', name: '食用油', quantity: 15, unit: 'g' },
      { ingredient_id: 'I047', name: '椒盐', quantity: 3, unit: 'g' },
    ],
  },
]

/** 演示用库存快照：覆盖 P0 主要原料，含视觉计数来源（草莓/芒果） */
export const INVENTORY_SEED: InventorySeedItem[] = [
  { ingredient_id: 'I011', name: '草莓', physical: 4200, defective: 60, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '视觉计数' },
  { ingredient_id: 'I012', name: '芒果', physical: 3600, defective: 40, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '视觉计数' },
  { ingredient_id: 'I001', name: '香水柠檬', physical: 120, defective: 2, reserved: 0, unit: 'pcs', tracking: 'TRACKED', source: '视觉计数' },
  { ingredient_id: 'I002', name: '金桔', physical: 260, defective: 0, reserved: 0, unit: 'pcs', tracking: 'TRACKED', source: '视觉计数' },
  { ingredient_id: 'I003', name: '蜂蜜', physical: 8000, defective: 0, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I006', name: '茉莉茶汤', physical: 15000, defective: 0, reserved: 0, unit: 'ml', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I007', name: '乌龙茶汤', physical: 12000, defective: 0, reserved: 0, unit: 'ml', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I010', name: '淡奶油', physical: 9000, defective: 0, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I026', name: '蛋糕胚', physical: 60, defective: 0, reserved: 0, unit: 'pcs', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I041', name: '冷冻薯条', physical: 20000, defective: 0, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I048', name: '鸡腿肉', physical: 9000, defective: 0, reserved: 0, unit: 'g', tracking: 'TRACKED', source: '人工盘点' },
  { ingredient_id: 'I004', name: '冰块', physical: 0, defective: 0, reserved: 0, unit: 'g', tracking: 'UNLIMITED', source: '-' },
  { ingredient_id: 'I005', name: '纯净水', physical: 0, defective: 0, reserved: 0, unit: 'ml', tracking: 'UNLIMITED', source: '-' },
]

export interface InventorySeedItem {
  ingredient_id: string
  name: string
  physical: number
  defective: number
  reserved: number
  unit: 'pcs' | 'g' | 'ml'
  tracking: 'TRACKED' | 'UNLIMITED'
  source: string
}
