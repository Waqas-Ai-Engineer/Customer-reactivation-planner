"""Message templates for customer-reactivation-planner. Edit freely."""
from __future__ import annotations

from typing import Any, Dict, Tuple

SMS = {
    "check_in": "Hi {first}, it's {owner} at {biz}. It's been a while since your {service}. Want me to get you on the schedule? {link} Reply STOP to opt out.",
    "win_back": "Hi {first}, {owner} at {biz}. We miss you! Book this month and get {offer}: {link} Reply STOP to opt out.",
    "last_call": "Hi {first}, last note from {owner} at {biz}: {offer} is still yours if you book soon. {link} Reply STOP to opt out.",
}
EMAIL_SUBJECT = {
    "check_in": "Time for your next {service}?",
    "win_back": "We miss you at {biz} - {offer}",
    "last_call": "Last call: {offer} at {biz}",
}
EMAIL_BODY = (
    "Hi {first},\n\n{line}\n\nBook here: {link}\n\nThanks,\n{owner}\n{biz}\n\n"
    "(Reply STOP to stop receiving these messages.)"
)
EMAIL_LINE = {
    "check_in": "It has been a while since your last {service}. Happy to get you back on the schedule.",
    "win_back": "We would love to see you again. Book this month and enjoy {offer}.",
    "last_call": "This is our last reminder: {offer} is still available if you book soon.",
}


def render_message(customer, item, tier: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[str, str]:
    """Return (subject, body) for the plan item. Subject is empty for SMS."""
    name = tier["name"]
    vals = {
        "first": (customer.name.split() or ["there"])[0],
        "owner": cfg["owner_name"], "biz": cfg["business_name"],
        "link": cfg["booking_link"], "offer": cfg["offer_text"],
        "service": (customer.last_service or "service").lower(),
    }
    if item.channel == "sms":
        return "", SMS[name].format(**vals)
    vals["line"] = EMAIL_LINE[name].format(**vals)
    return EMAIL_SUBJECT[name].format(**vals), EMAIL_BODY.format(**vals)
