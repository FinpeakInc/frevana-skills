"""Durable preview receipts and explicitly approved, resumable Ads API mutations."""

import fcntl
import hashlib
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from ads_api import AdsError, account_info, identifier
from ads_delivery import apply_delivery, inspect_launch, launch_result


def save_json(path, value, *, create):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as output:
        tmp = output.name
        try:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
            if create:
                os.link(tmp, path)  # Atomic create; an existing receipt must survive.
            else:
                os.replace(tmp, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def approval_id(state):
    frozen = [state["version"], state["operation_id"], state["proposal"]]
    return hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def new_preview(path, proposal):
    state = {
        "version": 1,
        "operation_id": uuid.uuid4().hex,
        "proposal": proposal,
        "steps": {},
        "result": None,
    }
    state["confirmation"] = approval_id(state)
    save_json(path, state, create=True)
    return state


def load_state(path):
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(state, dict)
        or state.get("version") != 1
        or not isinstance(state.get("steps"), dict)
        or "result" not in state
        or state["confirmation"] != approval_id(state)
    ):
        raise AdsError("Invalid or changed receipt. Inspect the original preview.")
    return state


@contextmanager
def exclusive(path):
    # A stable sidecar keeps the same lock inode across atomic receipt replacements.
    fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AdsError("Another execution is using this receipt.") from None
        yield
    finally:
        os.close(fd)


class Execution:
    def __init__(self, api, path, state, retry_uncertain):
        self.api, self.path, self.state = api, path, state
        self.plan, self.steps = state["proposal"], state["steps"]
        self.retry_uncertain = retry_uncertain

    def checkpoint(self, step, value):
        self.steps[step] = value
        save_json(self.path, self.state, create=False)


def reconcile_paused(api, path, confirmation):
    """Finish only local bookkeeping using GET readbacks of previously created IDs."""
    with exclusive(path):
        state = load_state(path)
        plan = state["proposal"]
        if confirmation != state["confirmation"] or plan["kind"] != "launch" or plan["final_status"] != "paused":
            raise AdsError("Select the approved paused creation receipt.")
        if state["result"] is not None:
            return state["result"]
        account = account_info(api)
        if any(account[k] != plan["account"][k] for k in ("id", "currency_code", "timezone")):
            raise AdsError("The advertiser account no longer matches the receipt.")
        steps = state["steps"]
        ids = {kind: steps.get("create_" + kind) for kind in ("campaign", "ad_group", "ad")}
        ids["file_id"] = plan["asset"].get("file_id") or steps.get("create_upload")
        if any(not value or value == "pending" for value in ids.values()):
            raise AdsError("Creation is incomplete; verification cannot create resources.")
        ids = {k: identifier(v) for k, v in ids.items()}
        current = inspect_launch(api, plan, ids)
        if any(obj["status"] != "paused" for obj in current.values()):
            raise AdsError("The existing resources are not all paused. Inspect Ads Manager.")
        result = launch_result(current, ids)
        state["result"] = result
        save_json(path, state, create=False)
        return result


def execute(api, path, confirmation, retry_uncertain=False):
    with exclusive(path):
        state = load_state(path)
        if confirmation != state["confirmation"]:
            raise AdsError("Confirmation does not match this proposal.")
        if state["result"] is not None:
            return state["result"]
        plan = state["proposal"]
        op = Execution(api, path, state, retry_uncertain)
        if plan["kind"] == "operation":
            from ads_changes import apply_operation

            result = apply_operation(op)
        else:
            result = apply_delivery(op)
        state["result"] = result
        save_json(path, state, create=False)
        return result
