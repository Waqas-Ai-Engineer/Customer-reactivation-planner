import os
import tempfile
import unittest
from datetime import date

from crp_core import DEFAULT_CONFIG, Customer, build_plan, load_customers, parse_date, pick_tier, priority_score
import crp_cli

TODAY = date(2026, 10, 17)
CFG = dict(DEFAULT_CONFIG)


def cust(**kw):
    base = dict(name="A B", phone="+1555", last_service_date=date(2026, 3, 1), lifetime_value=500, visits=2)
    base.update(kw)
    return Customer(**base)


class TestCore(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(pick_tier(100, CFG["tiers"])["name"], "check_in")
        self.assertEqual(pick_tier(200, CFG["tiers"])["name"], "win_back")
        self.assertEqual(pick_tier(400, CFG["tiers"])["name"], "last_call")
        self.assertIsNone(pick_tier(30, CFG["tiers"]))

    def test_opt_out_skipped(self):
        plan = build_plan([cust(opted_out=True)], CFG, TODAY)
        self.assertEqual(plan.items, [])
        self.assertEqual(plan.skipped[0].reason, "opted out")

    def test_cooldown(self):
        plan = build_plan([cust(last_contacted=date(2026, 10, 10))], CFG, TODAY)
        self.assertEqual(plan.skipped[0].reason, "contacted within cooldown")

    def test_channel_fallback_email(self):
        plan = build_plan([cust(phone="", email="a@b.co")], CFG, TODAY)
        self.assertEqual(plan.items[0].channel, "email")
        self.assertTrue(plan.items[0].subject)

    def test_no_contact(self):
        plan = build_plan([cust(phone="")], CFG, TODAY)
        self.assertEqual(plan.skipped[0].reason, "no phone or email")

    def test_not_dormant(self):
        plan = build_plan([cust(last_service_date=date(2026, 10, 1))], CFG, TODAY)
        self.assertIn("not dormant", plan.skipped[0].reason)

    def test_priority_and_cap(self):
        cfg = dict(CFG, max_per_day=1)
        plan = build_plan([cust(name="Low", lifetime_value=10), cust(name="High", lifetime_value=2000, visits=8)], cfg, TODAY)
        self.assertEqual(plan.items[0].name, "High")
        self.assertEqual(plan.deferred, 1)

    def test_score_bounds(self):
        s = priority_score(cust(lifetime_value=10**6, visits=99, service_interval_days=10), 10000, CFG)
        self.assertLessEqual(s, 100)

    def test_sms_has_opt_out(self):
        plan = build_plan([cust()], CFG, TODAY)
        self.assertIn("STOP", plan.items[0].message)

    def test_bad_date(self):
        with self.assertRaises(ValueError):
            parse_date("10/17/2026")

    def test_csv_requires_name(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("phone\n123\n")
        try:
            with self.assertRaises(ValueError):
                load_customers(f.name)
        finally:
            os.unlink(f.name)


class TestCli(unittest.TestCase):
    def test_demo_runs(self):
        self.assertEqual(crp_cli.main(["demo"]), 0)

    def test_missing_file(self):
        self.assertEqual(crp_cli.main(["plan", "--csv", "nope.csv"]), 2)

    def test_demo_plan_content(self):
        here = os.path.dirname(os.path.abspath(__file__))
        plan = build_plan(load_customers(os.path.join(here, "example_customers.csv")), CFG, crp_cli.DEMO_TODAY)
        names = [i.name for i in plan.items]
        self.assertIn("Alicia Gomez", names)
        self.assertNotIn("Ben Carter", names)


if __name__ == "__main__":
    unittest.main()
