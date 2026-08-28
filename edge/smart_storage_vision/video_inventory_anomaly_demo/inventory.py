from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


VALID_UNITS = {"g", "ml", "pcs"}
VALID_POLICIES = {"TRACKED", "UNLIMITED"}


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True)
class InventoryItem:
    ingredient_id: str
    name: str
    base_unit: str
    inventory_policy: str
    physical_quantity: Decimal
    defective_quantity: Decimal = Decimal("0")
    reserved_quantity: Decimal = Decimal("0")

    @property
    def available_quantity(self) -> Decimal:
        return max(
            Decimal("0"),
            self.physical_quantity - self.defective_quantity - self.reserved_quantity,
        )

    def as_dict(self, *, simulated: bool) -> dict:
        return {
            "ingredient_id": self.ingredient_id,
            "name": self.name,
            "base_unit": self.base_unit,
            "inventory_policy": self.inventory_policy,
            "physical_quantity": decimal_text(self.physical_quantity),
            "defective_quantity": decimal_text(self.defective_quantity),
            "reserved_quantity": decimal_text(self.reserved_quantity),
            "available_quantity": decimal_text(self.available_quantity),
            "simulated": simulated,
        }


@dataclass(frozen=True)
class ScheduledChange:
    at_seconds: float
    ingredient_id: str
    delta: Decimal


class DemoInventoryProvider:
    """Deterministic Word-v1.0 inventory fixture; it never writes to Core."""

    def __init__(self, fixture_path: str | Path, *, scenario_enabled: bool = True) -> None:
        payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self.specification = dict(payload["specification"])
        self.store_id = str(payload["store_id"])
        self.location_id = str(payload["location_id"])
        self.items = self._load_items(payload["ingredients"])
        self.initial_quantities = {
            ingredient_id: item.physical_quantity for ingredient_id, item in self.items.items()
        }
        self.changes = [
            ScheduledChange(
                at_seconds=float(change["at_seconds"]),
                ingredient_id=str(change["ingredient_id"]),
                delta=Decimal(str(change["delta"])),
            )
            for change in payload.get("demo_scenario", {}).get("changes", [])
        ] if scenario_enabled else []
        self.next_change_index = 0

    @staticmethod
    def _load_items(raw_items: list[dict]) -> dict[str, InventoryItem]:
        items: dict[str, InventoryItem] = {}
        for raw in raw_items:
            ingredient_id = str(raw["ingredient_id"])
            if ingredient_id in items:
                raise ValueError(f"duplicate ingredient_id: {ingredient_id}")
            unit = str(raw["base_unit"])
            policy = str(raw["inventory_policy"])
            if unit not in VALID_UNITS:
                raise ValueError(f"invalid base_unit for {ingredient_id}: {unit}")
            if policy not in VALID_POLICIES:
                raise ValueError(f"invalid inventory_policy for {ingredient_id}: {policy}")
            items[ingredient_id] = InventoryItem(
                ingredient_id=ingredient_id,
                name=str(raw["name"]),
                base_unit=unit,
                inventory_policy=policy,
                physical_quantity=Decimal(str(raw["physical_quantity"])),
            )
        expected_ids = {f"I{index:03d}" for index in range(1, 68)}
        if set(items) != expected_ids:
            missing = sorted(expected_ids - set(items))
            extra = sorted(set(items) - expected_ids)
            raise ValueError(f"Word v1.0 ingredient IDs do not match; missing={missing}, extra={extra}")
        if items["I004"].inventory_policy != "UNLIMITED" or items["I005"].inventory_policy != "UNLIMITED":
            raise ValueError("I004 and I005 must remain UNLIMITED")
        return items

    def advance(self, elapsed_seconds: float) -> list[tuple[float, InventoryItem]]:
        applied = []
        while self.next_change_index < len(self.changes):
            change = self.changes[self.next_change_index]
            if change.at_seconds > elapsed_seconds:
                break
            item = self.items[change.ingredient_id]
            if item.inventory_policy != "TRACKED":
                raise ValueError(f"cannot change UNLIMITED ingredient: {change.ingredient_id}")
            updated_quantity = item.physical_quantity + change.delta
            if updated_quantity < 0:
                raise ValueError(f"inventory became negative: {change.ingredient_id}")
            self.items[change.ingredient_id] = InventoryItem(
                ingredient_id=item.ingredient_id,
                name=item.name,
                base_unit=item.base_unit,
                inventory_policy=item.inventory_policy,
                physical_quantity=updated_quantity,
                defective_quantity=item.defective_quantity,
                reserved_quantity=item.reserved_quantity,
            )
            applied.append((change.at_seconds, self.items[change.ingredient_id]))
            self.next_change_index += 1
        return applied

    def snapshot(self) -> list[InventoryItem]:
        return [self.items[ingredient_id] for ingredient_id in sorted(self.items)]


@dataclass(frozen=True)
class InventoryAnomaly:
    ingredient_id: str
    ingredient_name: str
    unit: str
    window_seconds: float
    decrease_quantity: Decimal
    decrease_rate: Decimal
    consecutive_drops: int
    baseline_quantity: Decimal
    current_quantity: Decimal

    def as_dict(self, timestamp: str) -> dict:
        return {
            "event_type": "inventory.anomaly_suspected",
            "timestamp": timestamp,
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient_name,
            "unit": self.unit,
            "window_seconds": round(self.window_seconds, 2),
            "decrease_quantity": decimal_text(self.decrease_quantity),
            "decrease_rate_per_second": decimal_text(self.decrease_rate),
            "consecutive_drops": self.consecutive_drops,
            "baseline_quantity": decimal_text(self.baseline_quantity),
            "current_quantity": decimal_text(self.current_quantity),
            "simulated": True,
            "published_to_core": False,
        }


class InventoryAnomalyDetector:
    """Detect sudden, fast, sustained and finally large unexplained reductions."""

    def __init__(
        self,
        *,
        window_seconds: float = 10.0,
        min_consecutive_drops: int = 4,
        minimum_drop_ratio: Decimal = Decimal("0.20"),
        absolute_thresholds: dict[str, Decimal] | None = None,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if min_consecutive_drops < 2:
            raise ValueError("min_consecutive_drops must be at least 2")
        self.window_seconds = window_seconds
        self.min_consecutive_drops = min_consecutive_drops
        self.minimum_drop_ratio = minimum_drop_ratio
        self.absolute_thresholds = absolute_thresholds or {
            "g": Decimal("500"),
            "ml": Decimal("1000"),
            "pcs": Decimal("5"),
        }
        self.histories: dict[str, deque[tuple[float, Decimal]]] = {}
        self.active_incidents: set[str] = set()

    def observe(self, elapsed_seconds: float, item: InventoryItem) -> InventoryAnomaly | None:
        if item.inventory_policy != "TRACKED":
            return None
        history = self.histories.setdefault(item.ingredient_id, deque())
        if history and history[-1][1] == item.physical_quantity:
            return None
        if history and item.physical_quantity > history[-1][1]:
            self.active_incidents.discard(item.ingredient_id)
        history.append((elapsed_seconds, item.physical_quantity))
        while history and elapsed_seconds - history[0][0] > self.window_seconds:
            history.popleft()
        if item.ingredient_id in self.active_incidents or len(history) < self.min_consecutive_drops + 1:
            return None

        consecutive = [history[-1]]
        for earlier in reversed(list(history)[:-1]):
            if earlier[1] <= consecutive[-1][1]:
                break
            consecutive.append(earlier)
        consecutive.reverse()
        if len(consecutive) - 1 < self.min_consecutive_drops:
            return None

        first_time, baseline = consecutive[0]
        last_time, current = consecutive[-1]
        duration = last_time - first_time
        decrease = baseline - current
        absolute_threshold = self.absolute_thresholds[item.base_unit]
        required_drop = max(absolute_threshold, baseline * self.minimum_drop_ratio)
        single_drops = [
            consecutive[index - 1][1] - consecutive[index][1]
            for index in range(1, len(consecutive))
        ]
        sudden = max(single_drops) >= required_drop * Decimal("0.20")
        fast = duration > 0 and decrease / Decimal(str(duration)) >= required_drop / Decimal(str(self.window_seconds))
        if not (sudden and fast and decrease >= required_drop):
            return None

        self.active_incidents.add(item.ingredient_id)
        return InventoryAnomaly(
            ingredient_id=item.ingredient_id,
            ingredient_name=item.name,
            unit=item.base_unit,
            window_seconds=duration,
            decrease_quantity=decrease,
            decrease_rate=decrease / Decimal(str(duration)),
            consecutive_drops=len(consecutive) - 1,
            baseline_quantity=baseline,
            current_quantity=current,
        )
