"""Core logic for customer-reactivation-planner (crp).

Turns a customer CSV into a prioritized win-back plan. Standard library only.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "business_name": "Sample Home Services",
    "owner_name": "Sam",
    "booking_link": "https://example.com/book",
    "offer_text": "10% off your next visit",
    "tiers": [
        {"name": "check_in", "min_days": 90, "max_days": 179, "use_offer": False},
        {"name": "win_back", "min_days": 180, "max_days": 364, "use_offer": True},
        {"name": "last_call", "min_days": 365, "max_days": 100000, "use_offer": True},
    ],
    "cooldown_days": 30,
    "min_lifetime_value": 0,
    "vip_lifetime_value": 1000,
    "max_per_day": 25,
}

TRUE_VALUES = {"1", "true", "yes", "y", "t"}


@dataclass
class Customer:
    """One row of the input CSV."""

    name: str
    phone: str = ""
    email: str = ""
    last_service_date: Optional[date] = None
    last_service: str = ""
    lifetime_value: float = 0.0
    visits: int = 0
    opted_out: bool = False
    last_contacted: Optional[date] = None
    service_interval_days: Optional[int] = None


@dataclass
class PlanItem:
    """One recommended outreach."""

    name: str
    channel: str
    contact: str
    tier: str
    days_dormant: int
    priority: float
    lifetime_value: float
    vip: bool
    message: str = ""
    subject: str = ""


@dataclass
class Skipped:
    """A customer who was intentionally not contacted, with the reason."""

    name: str
    reason: str


@dataclass
class Plan:
    today: date
    items: List[PlanItem] = field(default_factory=list)
    skipped: List[Skipped] = field(default_factory=list)
    deferred: int = 0

    def revenue_at_stake(self) -> float:
        """Sum of historical lifetime value of customers in the plan (NOT a forecast)."""
        return round(sum(i.lifetime_value for i in self.items), 2)


def parse_date(value: str) -> Optional[date]:
    """Parse YYYY-MM-DD (also accepts DD/MM/YYYY-free ISO only). Empty -> None."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Bad date '{value}': use YYYY-MM-DD") from exc


def _num(value: str, cast=float, default=0):
    value = (value or "").strip().replace("$", "").replace(",", "")
    if not value:
        return default
    try:
        return cast(value)
    except ValueError:
        return default


def load_customers(path: str) -> List[Customer]:
    """Load customers from a CSV file. Required column: name."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "name" not in [f.strip().lower() for f in reader.fieldnames]:
            raise ValueError("CSV must have a 'name' column (see example_customers.csv)")
        rows = []
        for raw in reader:
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            if not row.get("name"):
                continue
            interval = _num(row.get("service_interval_days", ""), int, None)
            rows.append(
                Customer(
                    name=row["name"],
                    phone=row.get("phone", ""),
                    email=row.get("email", ""),
                    last_service_date=parse_date(row.get("last_service_date", "")),
                    last_service=row.get("last_service", ""),
                    lifetime_value=_num(row.get("lifetime_value", ""), float, 0.0),
                    visits=_num(row.get("visits", ""), int, 0),
                    opted_out=row.get("opted_out", "").lower() in TRUE_VALUES,
                    last_contacted=parse_date(row.get("last_contacted", "")),
                    service_interval_days=interval,
                )
            )
    return rows


def load_config(path: Optional[str]) -> Dict[str, Any]:
    """Merge a JSON config over DEFAULT_CONFIG."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    return cfg


def pick_tier(days: int, tiers: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the tier whose [min_days, max_days] contains `days`."""
    for tier in tiers:
        if tier["min_days"] <= days <= tier["max_days"]:
            return tier
    return None


def priority_score(c: Customer, days: int, cfg: Dict[str, Any]) -> float:
    """0-100 score: value (50), loyalty (20), overdue vs usual interval (30)."""
    vip = max(cfg["vip_lifetime_value"], 1)
    value = min(c.lifetime_value / vip, 1.0) * 50
    loyalty = min(c.visits / 8.0, 1.0) * 20
    interval = c.service_interval_days or 365
    overdue = min(max(days - interval, 0) / interval, 1.0) * 30
    return round(value + loyalty + overdue, 1)


def build_plan(customers: List[Customer], cfg: Dict[str, Any], today: date) -> Plan:
    """Build today's reactivation plan. Pure function: no I/O, deterministic."""
    from crp_templates import render_message  # local import avoids cycle

    plan = Plan(today=today)
    candidates: List[PlanItem] = []
    for c in customers:
        if c.opted_out:
            plan.skipped.append(Skipped(c.name, "opted out"))
            continue
        if c.last_service_date is None:
            plan.skipped.append(Skipped(c.name, "no last_service_date"))
            continue
        days = (today - c.last_service_date).days
        if days < 0:
            plan.skipped.append(Skipped(c.name, "last service is in the future"))
            continue
        if c.lifetime_value < cfg["min_lifetime_value"]:
            plan.skipped.append(Skipped(c.name, "below min_lifetime_value"))
            continue
        tier = pick_tier(days, cfg["tiers"])
        if tier is None:
            plan.skipped.append(Skipped(c.name, f"not dormant yet ({days} days)"))
            continue
        if c.last_contacted and (today - c.last_contacted).days < cfg["cooldown_days"]:
            plan.skipped.append(Skipped(c.name, "contacted within cooldown"))
            continue
        if c.phone:
            channel, contact = "sms", c.phone
        elif c.email:
            channel, contact = "email", c.email
        else:
            plan.skipped.append(Skipped(c.name, "no phone or email"))
            continue
        item = PlanItem(
            name=c.name, channel=channel, contact=contact, tier=tier["name"],
            days_dormant=days, priority=priority_score(c, days, cfg),
            lifetime_value=c.lifetime_value,
            vip=c.lifetime_value >= cfg["vip_lifetime_value"],
        )
        item.subject, item.message = render_message(c, item, tier, cfg)
        candidates.append(item)
    candidates.sort(key=lambda i: (-i.priority, i.name))
    plan.items = candidates[: cfg["max_per_day"]]
    plan.deferred = max(len(candidates) - cfg["max_per_day"], 0)
    return plan


def plan_to_dict(plan: Plan) -> Dict[str, Any]:
    """JSON-serialisable view of a plan."""
    return {
        "date": plan.today.isoformat(),
        "revenue_at_stake_historical": plan.revenue_at_stake(),
        "deferred": plan.deferred,
        "items": [asdict(i) for i in plan.items],
        "skipped": [asdict(s) for s in plan.skipped],
    }
