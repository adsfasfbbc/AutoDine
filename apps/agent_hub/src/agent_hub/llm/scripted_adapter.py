from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..tools.base import ToolDefinition
from .base import ChatMessage, LLMResponse, ToolCall

# Product aliases covering the seeded catalog (Chinese + English names).
CATALOG_ALIASES: Dict[str, str] = {
    "美式": "americano",
    "americano": "americano",
    "冰美式": "iced_americano",
    "iced americano": "iced_americano",
    "拿铁": "latte",
    "latte": "latte",
    "卡布奇诺": "cappuccino",
    "cappuccino": "cappuccino",
    "摩卡": "mocha",
    "mocha": "mocha",
    "香草拿铁": "vanilla_latte",
    "vanilla latte": "vanilla_latte",
    "燕麦拿铁": "oat_latte",
    "oat latte": "oat_latte",
    "抹茶拿铁": "matcha_latte",
    "matcha": "matcha_latte",
    "柠檬茶": "lemon_tea",
    "lemon tea": "lemon_tea",
    "冰柠檬茶": "iced_lemon_tea",
    "红茶": "black_tea",
    "black tea": "black_tea",
    "巧克力奶": "chocolate_milk",
    "汉堡": "beef_burger",
    "牛肉汉堡": "beef_burger",
    "beef burger": "beef_burger",
    "鸡排堡": "chicken_burger",
    "chicken burger": "chicken_burger",
    "芝士汉堡": "cheese_burger",
    "薯条": "french_fries",
    "fries": "french_fries",
    "套餐": "burger_combo",
}

_NUM_CN = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_HEX_RE = re.compile(r"\b[0-9a-fA-F]{8,64}\b")

_INTENT_RULES: List[tuple] = [
    (("总结", "运营", "报表", "概览", "业绩", "今日", "今天"), "summary"),
    (("库存", "存货", "原料", "备货", "用料"), "inventory"),
    (("告警", "报警", "质量", "异常", "安全"), "alarm"),
    (("排队", "等位", "客流"), "queue"),
    (("取消", "退单", "撤销"), "cancel"),
    (("生产", "领料", "制作", "出餐", "备餐", "任务", "后厨", "开始做", "做好", "完成"), "production"),
    (("订单", "查单", "进度"), "order_status"),
    (("下单", "买", "来一杯", "来一份", "来一个", "点一杯", "点一份", "点单", "我要", "想要"), "order"),
    (("菜单", "推荐", "有什么", "有哪些", "喝", "饮品", "饮料", "点餐"), "menu"),
]


def _detect_intent(text: str) -> Optional[str]:
    for keywords, intent in _INTENT_RULES:
        if any(k in text for k in keywords):
            return intent
    return None


def _find_product(text: str) -> Optional[str]:
    lowered = text.lower()
    for alias in sorted(CATALOG_ALIASES, key=len, reverse=True):
        if alias.lower() in lowered:
            return CATALOG_ALIASES[alias]
    return None


def _find_quantity(text: str) -> int:
    m = re.search(r"(\d+)\s*(杯|个|份|件|套)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"([一两二三四五六七八九十])\s*(杯|个|份|件|套)", text)
    if m:
        return _NUM_CN.get(m.group(1), 1)
    return 1


def _find_id(text: str) -> Optional[str]:
    m = _HEX_RE.search(text)
    return m.group(0) if m else None


def _pick_list_to_consumption(pick_list: List[Dict[str, Any]], location_id: str) -> List[Dict[str, Any]]:
    return [
        {"ingredient_id": item["ingredient_id"], "location_id": location_id, "quantity": item["quantity"]}
        for item in pick_list
    ]


def _error_reply(data: Any, verb: str = "操作") -> Optional[str]:
    """Return a friendly message when a tool surfaced an error dict."""
    if isinstance(data, dict) and "error" in data:
        return (
            f"{verb}失败：{data['error']}\n"
            "请确认 AutoDineCore 中台已启动（默认 http://localhost:8000），"
            "并正确配置 AGENT_HUB_CORE_BASE_URL。"
        )
    return None


# --- Result formatters -------------------------------------------------------


def _format_menu(data: Any) -> str:
    err = _error_reply(data, "获取菜单")
    if err:
        return err
    if not isinstance(data, list):
        return f"菜单数据异常：{data}"
    on_sale = [p for p in data if p.get("status") == "ON_SALE"]
    sold_out = [p for p in data if p.get("status") != "ON_SALE"]
    lines = ["当前在售："]
    for p in on_sale[:12]:
        lines.append(f"- {p['name']}（{p['product_id']}）¥{p['price']}，可售 {p['available_product_quantity']}")
    text = "\n".join(lines)
    if sold_out:
        text += "\n已售罄：" + "、".join(p["name"] for p in sold_out)
    if not on_sale:
        text = "当前暂无在售商品。"
    return text


def _format_order(data: Any) -> str:
    err = _error_reply(data, "操作")
    if err:
        return err
    items = "、".join(f"{i['product_id']}×{i['quantity']}" for i in data.get("items", []))
    text = f"订单 {data.get('order_id')}｜状态 {data.get('status')}｜金额 {data.get('total_amount')}｜商品：{items}"
    task = data.get("task")
    if task:
        text += f"｜生产任务 {task['task_id']}（{task['status']}）"
        pick_list = task.get("pick_list") or []
        if pick_list:
            pl = "、".join(f"{p['ingredient_id']}×{p['quantity']}{p['unit']}" for p in pick_list)
            text += f"｜领料清单：{pl}"
    return text


def _format_task(data: Any, verb: str) -> str:
    err = _error_reply(data, verb)
    if err:
        return err
    return (
        f"{verb}成功：任务 {data.get('task_id')} 状态 {data.get('status')}"
        f"，订单 {data.get('order_id')} 状态 {data.get('order_status')}"
    )


def _format_inventory(data: Any) -> str:
    err = _error_reply(data, "获取库存")
    if err:
        return err
    if not isinstance(data, list):
        return f"库存数据异常：{data}"
    lines = ["库存概览："]
    for inv in data[:15]:
        defective = inv.get("defective_quantity")
        flag = " [有瑕疵]" if defective and float(defective) > 0 else ""
        lines.append(
            f"- {inv.get('ingredient_id')}：可用 {inv.get('available_quantity')}"
            f" / 实物 {inv.get('physical_quantity')} / 瑕疵 {defective}"
            f" / 预留 {inv.get('reserved_quantity')}{flag}"
        )
    return "\n".join(lines)


def _format_alarms(data: Any) -> str:
    err = _error_reply(data, "获取告警")
    if err:
        return err
    items = data.get("items", []) if isinstance(data, dict) else (data or [])
    if not items:
        return "当前没有告警，一切正常。"
    lines = ["当前告警："]
    for a in items:
        lines.append(f"- [{a.get('severity')}] {a.get('source_key')}：{a.get('message')}（{a.get('status')}）")
    return "\n".join(lines)


def _format_queue(data: Any) -> str:
    err = _error_reply(data, "获取排队")
    if err:
        return err
    items = data.get("items", []) if isinstance(data, dict) else (data or [])
    if not items:
        return "当前没有排队数据。"
    lines = ["排队情况："]
    for q in items:
        wait = q.get("estimated_wait_seconds")
        wait_text = f"{wait} 秒" if wait is not None else "未知"
        lines.append(f"- 区域 {q.get('zone_id')}：等待 {q.get('waiting_count')} 人，预估 {wait_text}")
    return "\n".join(lines)


def _format_summary(data: Any) -> str:
    err = _error_reply(data, "获取运营总结")
    if err:
        return err
    metrics = data.get("metrics", {})
    window = data.get("window", {})
    return "\n".join(
        [
            f"运营总结（{window.get('start', '')} ~ {window.get('end', '')}）：",
            f"- 订单数：{metrics.get('order_count', 0)}",
            f"- 生产任务数：{metrics.get('production_task_count', 0)}",
            f"- 库存位置数：{metrics.get('inventory_location_count', 0)}",
            f"- 未关闭告警数：{metrics.get('open_alarm_count', 0)}",
        ]
    )


class ScriptedAdapter:
    """Deterministic, offline fallback adapter.

    Maps a user message to a fixed sequence of tool calls (keyword/rule based)
    and drives the same execution loop as the OpenAI adapter. It lets the hub
    run without any external AI service and backs the test suite.
    """

    def __init__(self, *, default_store_id: str, default_location_id: str) -> None:
        self.default_store_id = default_store_id
        self.default_location_id = default_location_id
        self._counter = 0
        self._handlers = {
            "menu": self._handle_menu,
            "order": self._handle_order,
            "order_status": self._handle_order_status,
            "cancel": self._handle_cancel,
            "production": self._handle_production,
            "inventory": self._handle_inventory,
            "alarm": self._handle_alarm,
            "queue": self._handle_queue,
            "summary": self._handle_summary,
        }

    def generate(self, messages: List[ChatMessage], tools: List[ToolDefinition]) -> LLMResponse:
        instruction = self._last_user(messages)
        results = self._tool_results(messages)
        intent = _detect_intent(instruction)
        handler = self._handlers.get(intent)
        if handler is None:
            return LLMResponse(
                text="抱歉，我暂时只能处理点餐、菜单推荐、生产咨询、库存/质量查询和运营总结。请换一种说法。"
            )
        return handler(instruction, results)

    # --- helpers -------------------------------------------------------------

    def _new_id(self) -> str:
        self._counter += 1
        return f"scripted-{self._counter}"

    @staticmethod
    def _last_user(messages: List[ChatMessage]) -> str:
        for m in reversed(messages):
            if m.role == "user":
                return m.content or ""
        return ""

    @staticmethod
    def _tool_results(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for m in messages:
            if m.role == "tool":
                try:
                    data = json.loads(m.content or "{}")
                except json.JSONDecodeError:
                    data = {"error": m.content}
                results.append({"tool_call_id": m.tool_call_id, "data": data})
        return results

    def _call(self, name: str, arguments: Dict[str, Any]) -> LLMResponse:
        return LLMResponse(tool_calls=[ToolCall(id=self._new_id(), name=name, arguments=arguments)])

    # --- intent handlers -----------------------------------------------------

    def _handle_menu(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            return self._call("list_menu", {"store_id": self.default_store_id})
        return LLMResponse(text=_format_menu(results[-1]["data"]))

    def _handle_order(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            product_id = _find_product(instruction)
            if product_id is None:
                return LLMResponse(text="抱歉，我没识别出你要点哪个商品，请说出商品名，例如「点一杯美式」。")
            arguments = {
                "store_id": self.default_store_id,
                "items": [{"product_id": product_id, "quantity": _find_quantity(instruction)}],
            }
            return self._call("create_order", arguments)
        return LLMResponse(text=_format_order(results[-1]["data"]))

    def _handle_order_status(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            order_id = _find_id(instruction)
            if not order_id:
                return LLMResponse(text="请提供订单 ID（order_id）。")
            return self._call("get_order", {"order_id": order_id})
        return LLMResponse(text=_format_order(results[-1]["data"]))

    def _handle_cancel(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            order_id = _find_id(instruction)
            if not order_id:
                return LLMResponse(text="请提供要取消的订单 ID（order_id）。")
            return self._call("cancel_order", {"order_id": order_id})
        return LLMResponse(text=_format_order(results[-1]["data"]))

    def _handle_inventory(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            return self._call("list_inventory", {})
        return LLMResponse(text=_format_inventory(results[-1]["data"]))

    def _handle_alarm(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            return self._call("list_alarms", {"store_id": self.default_store_id})
        return LLMResponse(text=_format_alarms(results[-1]["data"]))

    def _handle_queue(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            return self._call("list_queue_snapshots", {"store_id": self.default_store_id})
        return LLMResponse(text=_format_queue(results[-1]["data"]))

    def _handle_summary(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if not results:
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=24)
            return self._call(
                "get_analytics_summary",
                {
                    "store_id": self.default_store_id,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )
        return LLMResponse(text=_format_summary(results[-1]["data"]))

    def _handle_production(self, instruction: str, results: List[Dict[str, Any]]) -> LLMResponse:
        if "开始" in instruction or "start" in instruction.lower():
            if not results:
                task_id = _find_id(instruction)
                if not task_id:
                    return LLMResponse(text="请提供要开始的生产任务 ID（task_id）。")
                return self._call("start_production_task", {"task_id": task_id})
            return LLMResponse(text=_format_task(results[-1]["data"], "开始生产"))

        if "出餐" in instruction or "备餐" in instruction or "做好" in instruction or "ready" in instruction.lower():
            if not results:
                task_id = _find_id(instruction)
                if not task_id:
                    return LLMResponse(text="请提供要出餐的生产任务 ID（task_id）。")
                return self._call("ready_production_task", {"task_id": task_id})
            return LLMResponse(text=_format_task(results[-1]["data"], "出餐"))

        if "完成" in instruction or "complete" in instruction.lower():
            if len(results) == 0:
                order_id = _find_id(instruction)
                if not order_id:
                    return LLMResponse(text="请提供要完成的订单 ID（order_id）。")
                return self._call("get_order", {"order_id": order_id})
            if len(results) == 1:
                order_data = results[0]["data"]
                task = order_data.get("task") if isinstance(order_data, dict) else None
                if not task:
                    return LLMResponse(text=f"订单 {order_data.get('order_id')} 没有可完成的生产任务。")
                actual = _pick_list_to_consumption(task.get("pick_list", []), self.default_location_id)
                return self._call(
                    "complete_production_task",
                    {"task_id": task["task_id"], "actual_consumption": actual},
                )
            return LLMResponse(text=_format_task(results[-1]["data"], "完成生产"))

        # Default: view production task / pick list via the order.
        if not results:
            order_id = _find_id(instruction)
            if not order_id:
                return LLMResponse(text="请提供订单 ID（order_id），我来查看该订单的生产任务与领料清单。")
            return self._call("get_order", {"order_id": order_id})
        return LLMResponse(text=_format_order(results[-1]["data"]))
