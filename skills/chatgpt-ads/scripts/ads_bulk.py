"""Bulk mutation inputs and result pagination for ChatGPT Ads."""

from ads_api import AdsError, identifier


def validate_bulk(body):
    operations = body["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 1000:
        raise AdsError("A bulk job requires 1–1000 operations.")
    ids, keys, targets = set(), set(), set()
    for op in operations:
        if not isinstance(op, dict) or not isinstance(op.get("input"), dict) or not op["input"]:
            raise AdsError("Each bulk operation requires a nonempty input object.")
        kind, sep, verb = str(op.get("type", "")).partition(".")
        if not sep or kind not in ("campaign", "ad_group", "ad") or verb not in ("create", "update"):
            raise AdsError("Unknown bulk operation type.")
        operation_id = op.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id or operation_id in ids:
            raise AdsError("Each bulk operation requires a unique operation_id.")
        ids.add(operation_id)
        if verb == "create":
            key = op.get("idempotency_key")
            if not isinstance(key, str) or not key or key in keys:
                raise AdsError("Each bulk create requires a unique idempotency_key.")
            keys.add(key)
        else:
            target = (kind, identifier(op.get("target_resource_id")))
            if target in targets:
                raise AdsError("A bulk job can update a resource only once.")
            targets.add(target)


def bulk_results_cursor(page):
    if page.get("complete") is not True:
        raise AdsError("Bulk results are incomplete. Poll the job before requesting all pages.")
    if page.get("has_more") is True:
        rows = page.get("data") or []
        return rows[-1].get("operation_id") if rows else None
    return None
