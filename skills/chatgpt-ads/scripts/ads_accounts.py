"""Account administration, onboarding identity and spend-limit readbacks."""

from ads_api import (
    TRANSITION_STATUS,
    AdsError,
    account_info,
    identifier,
    native_matches,
)
from ads_operations import read_pages

ACCOUNT_CHANGES = {"update-ad-account", "activate-ad-account", "pause-ad-account"}


def account_identity(api, action):
    if action == "create-ad-account-creation-session":
        me = api.request("GET", "/me")
        return {"partner_user": identifier(me.get("id"))}
    return account_info(api)


def daily_rules(limits):
    """Read active/upcoming rules, including the older single-rule response."""
    rows = limits.get("daily_limits")
    if rows is None and "daily_limit" in limits:
        rows = [limits["daily_limit"]] if limits["daily_limit"] else []
    if rows is None:
        return None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise AdsError("Invalid daily spend-limit response.")
    return rows


def active_campaign_budgets(api):
    listing = {"action": "list-campaigns", "params": {}, "query": {"limit": 500}}
    campaigns = []
    seen = set()
    for page in read_pages(api, listing, {}, True):
        if not isinstance(page.get("data"), list) or type(page.get("has_more")) is not bool:
            raise AdsError("Incomplete campaign list. Cannot verify the scope of account activation.")
        for row in page["data"]:
            if not isinstance(row, dict) or row.get("status") not in ("active", "paused", "archived"):
                raise AdsError("Cannot verify campaign status for account activation.")
            campaign_id = identifier(row.get("id"))
            if campaign_id in seen:
                raise AdsError("Campaign appeared twice during pagination. Read the account again.")
            seen.add(campaign_id)
            if row["status"] != "active":
                continue
            budget = row.get("budget")
            limits = {
                k: budget[k]
                for k in ("daily_spend_limit_micros", "lifetime_spend_limit_micros")
                if isinstance(budget, dict) and budget.get(k) is not None
            }
            if not limits or not all(type(v) is int for v in limits.values()):
                raise AdsError(f"Cannot verify the budget for active campaign {campaign_id}.")
            campaigns.append({"id": campaign_id, "name": row["name"], "budget": limits})
    return sorted(campaigns, key=lambda campaign: campaign["id"])


def snapshot(api, action, body, approved=None):
    before = {}
    if action in ACCOUNT_CHANGES:
        obj = api.request("GET", "/ad_account")
        before["account_settings"] = {
            k: obj.get(k)
            for k in ("id", "name", "account_name", "brand_name", "status", "url", "favicon_file_id")
        }
    if action == "activate-ad-account":
        before["active_campaigns"] = active_campaign_budgets(api)
    if "spend-limit" in action:
        live = api.request("GET", "/ad_account/spend_limit_windows")
        before["revision"] = live.get("revision", 0)
        if "daily" in action and body.get("expected_revision") != before["revision"]:
            raise AdsError("The proposed expected_revision differs from the current spend-limit revision.")
        keys = ("window_id", "start_date", "end_date", "amount_micros", "name", "io_id", "status")
        windows = live.get("data", [])
        before["limits"] = [{k: w[k] for k in keys if k in w} for w in windows]
        daily = live.get("daily_limit") or {}
        before["daily_limit"] = {k: daily[k] for k in keys if k in daily}
        if "daily" in action:
            rules = daily_rules(live)
            if rules is not None:
                before["daily_limits"] = [
                    {k: rule[k] for k in keys if k in rule}
                    for rule in sorted(rules, key=lambda r: r.get("window_id") or "")
                ]
        if approved is not None and "daily_limits" not in approved:
            before.pop("daily_limits", None)  # Preserve the shape of older approved receipts.
    return before


def daily_change_matches(name, body, before, response, limits):
    live = daily_rules(limits)
    if live is None:
        return False
    previous = daily_rules(before)
    rid = body.get("window_id")
    if not rid and "window_id" not in body and previous and len(previous) == 1:
        rid = previous[0].get("window_id")  # Legacy singleton edit or deletion.
    if name.startswith("delete-"):
        if rid:
            return all(rule.get("window_id") and rule["window_id"] != rid for rule in live)
        return previous is not None and len(previous) <= 1 and not live
    wanted = {k: v for k, v in body.items() if k not in ("expected_revision", "window_id")}
    if not rid and "window_id" not in body and len(live) == 1 and not live[0].get("window_id"):
        return previous is not None and len(previous) <= 1 and native_matches(wanted, live[0])
    if not rid:
        # An explicit null requests a new rule. The POST returns the whole
        # post-mutation collection, even if another rule remains current.
        rid = response.get("window_id")
        if not rid:
            returned = daily_rules(response.get("spend_limits") or {})
            if returned is None or previous is None:
                return False
            if not all(rule.get("window_id") for rule in returned + previous):
                return False
            created = {rule["window_id"] for rule in returned} - {rule["window_id"] for rule in previous}
            if len(created) != 1:
                return False
            rid = next(iter(created))
    return any(rule.get("window_id") == rid and native_matches(wanted, rule) for rule in live)


def verify_response(api, plan, response):
    spec = plan["request"]
    name, body = spec["action"], spec["body"] or {}
    if name in ACCOUNT_CHANGES:
        live = api.request("GET", "/ad_account")
        wanted = TRANSITION_STATUS.get(name.partition("-")[0])
        if wanted and live.get("status") != wanted:
            raise AdsError("Account transition submitted; resume to verify its status.")
        different = [k for k, v in body.items() if not native_matches(v, live.get(k))]
        return {
            "state": "review_readback" if different else "read_back",
            "resource": live,
            "fields_to_review": different,
        }
    if "spend-limit" in name:
        limits = api.request("GET", "/ad_account/spend_limit_windows")
        if "daily" in name:
            matches = daily_change_matches(name, body, plan["before"], response, limits)
        else:
            rid = spec["params"].get("window_id") or response.get("window_id")
            observed = next((w for w in limits.get("data", []) if w.get("window_id") == rid), None)
            matches = observed is None if name.startswith("delete-") else native_matches(body, observed)
        return {
            "state": "read_back" if matches else "review_readback",
            "response": response,
            "spend_limits": limits,
        }
    return None
