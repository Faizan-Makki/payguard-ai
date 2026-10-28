"""Session-safe orchestration and storage for the fixed-amount Sandbox checkout demo."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid

import pandas as pd

from payguard.paypal_client import ORDER_ID_PATTERN
from payguard.risk_engine import assess_transactions


SANDBOX_TEST_AMOUNT = "1.00"
SANDBOX_TEST_CURRENCY = "USD"
CHECKOUT_TTL_SECONDS = 30 * 60


class CheckoutError(RuntimeError):
    """Safe checkout workflow validation error."""


def _state_hash(state: str) -> str:
    if not isinstance(state, str) or not 32 <= len(state) <= 128:
        raise CheckoutError("Sandbox checkout state is invalid")
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def callback_url(base_url: str, event: str, state: str) -> str:
    if event not in {"return", "cancel"}:
        raise ValueError("Unsupported PayPal callback event")
    parsed = urlsplit(base_url)
    local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    if not (parsed.scheme == "https" or local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("PayPal callback URL must be HTTPS (or localhost HTTP) without credentials or fragments")
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key in {"pg_checkout", "pg_state", "token", "PayerID"} for key, _ in existing):
        raise ValueError("PayPal callback base URL contains reserved checkout parameters")
    query = existing + [("pg_checkout", event), ("pg_state", state)]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(query), ""))


class PayPalCheckoutStore:
    """Stores short-lived order state in SQLite so a PayPal return can resume in a new tab."""

    def __init__(self, path="payguard.db"):
        self.path = str(path)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS paypal_sandbox_checkouts (
                    state_hash TEXT PRIMARY KEY,
                    order_id TEXT UNIQUE,
                    create_request_id TEXT NOT NULL,
                    capture_request_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approval_url TEXT,
                    transaction_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )

    def _connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create_attempt(self, state: str) -> dict:
        state_hash = _state_hash(state)
        now = time.time()
        values = (
            state_hash,
            f"pg-create-{uuid.uuid4().hex}",
            f"pg-capture-{uuid.uuid4().hex}",
            SANDBOX_TEST_AMOUNT,
            SANDBOX_TEST_CURRENCY,
            "CREATING",
            now,
            now,
        )
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO paypal_sandbox_checkouts(state_hash,create_request_id,capture_request_id,amount,currency,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    values,
                )
        except sqlite3.IntegrityError as exc:
            raise CheckoutError("Sandbox checkout state already exists") from exc
        return self.get_attempt(state)

    def get_attempt(self, state: str) -> dict | None:
        state_hash = _state_hash(state)
        with self._connect() as db:
            row = db.execute("SELECT * FROM paypal_sandbox_checkouts WHERE state_hash=?", (state_hash,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        raw_transaction = result.pop("transaction_json")
        result["transaction"] = json.loads(raw_transaction) if raw_transaction else None
        return result

    def save_created_order(self, state: str, order_id: str, approval_url: str) -> dict:
        if not isinstance(order_id, str) or not ORDER_ID_PATTERN.fullmatch(order_id):
            raise CheckoutError("PayPal returned an invalid order ID")
        with self._connect() as db:
            db.execute(
                "UPDATE paypal_sandbox_checkouts SET order_id=?,approval_url=?,status='AWAITING_APPROVAL',updated_at=? WHERE state_hash=? AND status IN ('CREATING','CREATE_FAILED')",
                (order_id, approval_url, time.time(), _state_hash(state)),
            )
        attempt = self.get_attempt(state)
        if not attempt or attempt["order_id"] != order_id:
            raise CheckoutError("PayPal order could not be linked to this checkout state")
        return attempt

    def mark_create_failed(self, state: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE paypal_sandbox_checkouts SET status='CREATE_FAILED',updated_at=? WHERE state_hash=? AND status='CREATING'",
                (time.time(), _state_hash(state)),
            )

    def claim_capture(self, state: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE paypal_sandbox_checkouts SET status='CAPTURING',updated_at=? WHERE state_hash=? AND status='AWAITING_APPROVAL'",
                (time.time(), _state_hash(state)),
            )
            return cursor.rowcount == 1

    def reset_capture_for_retry(self, state: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE paypal_sandbox_checkouts SET status='AWAITING_APPROVAL',updated_at=? WHERE state_hash=? AND status='CAPTURING'",
                (time.time(), _state_hash(state)),
            )

    def mark_paid(self, state: str, transaction: dict) -> dict:
        serialized = json.dumps(transaction, ensure_ascii=True, allow_nan=False)
        with self._connect() as db:
            db.execute(
                "UPDATE paypal_sandbox_checkouts SET status='PAID',transaction_json=?,updated_at=? WHERE state_hash=? AND status!='CANCELLED'",
                (serialized, time.time(), _state_hash(state)),
            )
        attempt = self.get_attempt(state)
        if not attempt or attempt["status"] != "PAID":
            raise CheckoutError("Verified Sandbox capture could not be stored")
        return attempt

    def mark_cancelled(self, state: str) -> dict:
        with self._connect() as db:
            db.execute(
                "UPDATE paypal_sandbox_checkouts SET status='CANCELLED',updated_at=? WHERE state_hash=? AND status IN ('AWAITING_APPROVAL','CREATE_FAILED')",
                (time.time(), _state_hash(state)),
            )
        return self.get_attempt(state)


def create_sandbox_order(client, store: PayPalCheckoutStore, state: str, return_url: str, cancel_url: str) -> dict:
    """Persist idempotency/state first, then create or safely retry the same order."""
    attempt = store.get_attempt(state)
    if attempt is None:
        raise CheckoutError("No Sandbox checkout was created for this browser state")
    if attempt["created_at"] + CHECKOUT_TTL_SECONDS < time.time():
        raise CheckoutError("Sandbox checkout attempt expired; start a new test checkout")
    if attempt["order_id"]:
        return attempt
    if attempt["status"] not in {"CREATING", "CREATE_FAILED"}:
        raise CheckoutError("Sandbox checkout is not in a creatable state")
    try:
        created = client.create_order(
            attempt["amount"],
            attempt["currency"],
            callback_url(return_url, "return", state),
            callback_url(cancel_url, "cancel", state),
            attempt["create_request_id"],
        )
        return store.save_created_order(state, created["id"], created["approval_url"])
    except Exception:
        store.mark_create_failed(state)
        raise


def _validate_callback(store: PayPalCheckoutStore, order_id: str, state: str) -> dict:
    attempt = store.get_attempt(state)
    if not attempt or attempt["created_at"] + CHECKOUT_TTL_SECONDS < time.time():
        raise CheckoutError("Sandbox checkout callback is unknown or expired")
    expected_order = attempt.get("order_id")
    if not isinstance(order_id, str) or not expected_order or not ORDER_ID_PATTERN.fullmatch(order_id) or not secrets.compare_digest(order_id, expected_order):
        raise CheckoutError("PayPal callback order ID does not match the order created for this checkout")
    return attempt


def _transaction_from_completed_order(order: dict, attempt: dict) -> dict:
    if not isinstance(order, dict) or order.get("id") != attempt["order_id"] or order.get("status") != "COMPLETED":
        raise CheckoutError("PayPal has not confirmed a completed order")
    purchase_units = order.get("purchase_units")
    if not isinstance(purchase_units, list):
        raise CheckoutError("PayPal completed order has no capture details")
    captures = []
    for unit in purchase_units:
        payments = unit.get("payments") if isinstance(unit, dict) else None
        listed = payments.get("captures") if isinstance(payments, dict) else None
        if isinstance(listed, list):
            captures.extend(capture for capture in listed if isinstance(capture, dict))
    completed = [capture for capture in captures if capture.get("status") == "COMPLETED"]
    if len(completed) != 1:
        raise CheckoutError("PayPal did not return exactly one completed Sandbox capture")
    capture = completed[0]
    capture_id = capture.get("id")
    amount = capture.get("amount")
    if not isinstance(capture_id, str) or not ORDER_ID_PATTERN.fullmatch(capture_id) or not isinstance(amount, dict):
        raise CheckoutError("PayPal completed capture details are incomplete")
    try:
        actual_amount = Decimal(str(amount.get("value")))
        expected_amount = Decimal(attempt["amount"])
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CheckoutError("PayPal completed capture amount is invalid") from exc
    currency = amount.get("currency_code")
    if not actual_amount.is_finite() or actual_amount != expected_amount or currency != attempt["currency"]:
        raise CheckoutError("PayPal completed capture amount or currency does not match this Sandbox order")
    timestamp = capture.get("create_time")
    if isinstance(timestamp, str):
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                timestamp = None
        except ValueError:
            timestamp = None
    else:
        timestamp = None
    return {
        "transaction_id": capture_id,
        "transaction_key": f"paypal-sandbox:{capture_id}",
        "timestamp": timestamp,
        "amount": float(actual_amount),
        "currency": currency,
        "status": "COMPLETED",
        "event_code": None,
        "updated_at": None,
        "customer_ref": None,
        "order_ref": attempt["order_id"],
        "source": "PayPal Sandbox",
        "is_demo": False,
        "refund_amount": None,
    }


def _record_verified_paid_order(store: PayPalCheckoutStore, state: str, order: dict, attempt: dict) -> dict:
    transaction = _transaction_from_completed_order(order, attempt)
    return store.mark_paid(state, transaction)


def verify_and_capture(client, store: PayPalCheckoutStore, order_id: str, state: str) -> dict:
    """Verify the PayPal order server-side, capture only APPROVED orders, and persist only COMPLETED captures."""
    attempt = _validate_callback(store, order_id, state)
    if attempt["status"] == "PAID" and attempt.get("transaction"):
        return attempt
    if attempt["status"] == "CANCELLED":
        raise CheckoutError("This Sandbox checkout was cancelled")
    if attempt["status"] == "CAPTURING":
        raise CheckoutError("Capture is already being processed; refresh and check its status")

    order = client.get_order(order_id)
    if order.get("id") != order_id:
        raise CheckoutError("PayPal returned a different order than the one created for this checkout")
    if order.get("status") == "COMPLETED":
        return _record_verified_paid_order(store, state, order, attempt)
    if order.get("status") != "APPROVED":
        return attempt
    if not store.claim_capture(state):
        latest = store.get_attempt(state)
        if latest and latest["status"] == "PAID":
            return latest
        raise CheckoutError("Another request is already processing this Sandbox capture")
    try:
        captured = client.capture_order(order_id, attempt["capture_request_id"])
        transaction = _transaction_from_completed_order(captured, attempt)
        return store.mark_paid(state, transaction)
    except Exception:
        store.reset_capture_for_retry(state)
        raise


def process_cancellation(client, store: PayPalCheckoutStore, order_id: str, state: str) -> dict:
    """Record cancellation without capturing; still reconcile if PayPal already completed the order."""
    attempt = _validate_callback(store, order_id, state)
    if attempt["status"] == "PAID" and attempt.get("transaction"):
        return attempt
    if attempt["status"] == "CAPTURING":
        raise CheckoutError("Capture is already being processed; cancellation cannot override its result")
    order = client.get_order(order_id)
    if order.get("id") != order_id:
        raise CheckoutError("PayPal returned a different order than the one created for this checkout")
    if order.get("status") == "COMPLETED":
        return _record_verified_paid_order(store, state, order, attempt)
    return store.mark_cancelled(state)


def assess_sandbox_capture(transaction: dict) -> pd.DataFrame:
    """Run the existing deterministic rules on this one Sandbox capture only."""
    if transaction.get("source") != "PayPal Sandbox" or transaction.get("is_demo") is not False:
        raise ValueError("Only verified PayPal Sandbox captures can be passed to this assessment")
    return assess_transactions(pd.DataFrame([transaction]))
