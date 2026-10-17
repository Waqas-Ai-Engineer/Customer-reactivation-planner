"""Command line interface for customer-reactivation-planner."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from typing import List, Optional

from crp_core import build_plan, load_config, load_customers, parse_date, plan_to_dict, Plan

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_TODAY = date(2026, 10, 17)


def format_plan(plan: Plan, show_messages: bool = False) -> str:
    """Human-readable plan table (plus optional rendered messages)."""
    lines = [f"Reactivation plan for {plan.today.isoformat()}", ""]
    lines.append(f"{'#':>2}  {'Customer':<18}{'Ch':<6}{'Tier':<10}{'Days':>5}{'Score':>7}{'LTV':>9}  VIP")
    lines.append("-" * 62)
    for n, i in enumerate(plan.items, 1):
        lines.append(f"{n:>2}  {i.name:<18}{i.channel:<6}{i.tier:<10}{i.days_dormant:>5}{i.priority:>7.1f}{i.lifetime_value:>9.0f}  {'*' if i.vip else ''}")
    lines += ["", f"Contacts today: {len(plan.items)}   Deferred (daily cap): {plan.deferred}   Skipped: {len(plan.skipped)}",
              f"Historical lifetime value of these customers: ${plan.revenue_at_stake():,.0f} (past spend, not a forecast)"]
    if plan.skipped:
        lines += ["", "Skipped:"] + [f"  - {s.name}: {s.reason}" for s in plan.skipped]
    if show_messages:
        lines += ["", "Messages:"]
        for i in plan.items:
            head = f"[{i.channel.upper()} -> {i.contact}]" + (f" Subject: {i.subject}" if i.subject else "")
            lines += ["", head, i.message]
    return "\n".join(lines)


def export_csv(plan: Plan, path: str) -> None:
    """Write the plan to a CSV ready for a mail-merge or n8n/Zapier import."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "channel", "contact", "tier", "days_dormant", "priority", "subject", "message"])
        for i in plan.items:
            w.writerow([i.name, i.channel, i.contact, i.tier, i.days_dormant, i.priority, i.subject, i.message])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crp", description="Customer reactivation planner: dormant-customer CSV -> win-back plan.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="run on bundled sample data (offline)")
    pl = sub.add_parser("plan", help="build a plan from your CSV")
    pl.add_argument("--csv", required=True, help="customers CSV (see example_customers.csv)")
    pl.add_argument("--config", help="JSON config (see example_config.json)")
    pl.add_argument("--today", help="override today's date, YYYY-MM-DD")
    pl.add_argument("--messages", action="store_true", help="print rendered messages")
    pl.add_argument("--json", action="store_true", help="print JSON instead of a table")
    pl.add_argument("--export", help="also write plan CSV to this path")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "demo":
            csv_path, cfg_path, today, msgs, as_json, export = (
                os.path.join(HERE, "example_customers.csv"), os.path.join(HERE, "example_config.json"),
                DEMO_TODAY, True, False, None)
            print("SAMPLE DATA - all customers below are fictional.\n")
        else:
            csv_path, cfg_path = args.csv, args.config
            today = parse_date(args.today) if args.today else date.today()
            msgs, as_json, export = args.messages, args.json, args.export
        plan = build_plan(load_customers(csv_path), load_config(cfg_path), today)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if export:
        export_csv(plan, export)
    print(json.dumps(plan_to_dict(plan), indent=2) if as_json else format_plan(plan, msgs))
    return 0
