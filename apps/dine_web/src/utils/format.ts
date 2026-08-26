/** 展示格式化工具：金额 / 时长 */
export function formatPriceCent(cent: number): string {
  return `¥${(cent / 100).toFixed(cent % 100 === 0 ? 0 : 2)}`
}

/** 秒 → 「X 分钟 Y 秒」，不足一分钟仅显示秒 */
export function formatSeconds(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60)
  const rest = s % 60
  return rest === 0 ? `${m} 分钟` : `${m} 分 ${rest} 秒`
}

/** 秒 → 倒计时 mm:ss */
export function formatCountdown(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

/** 取餐码：订单号后四位 */
export function pickupCode(orderId: string): string {
  return orderId.slice(-4)
}
