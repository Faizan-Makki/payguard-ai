"""Read-only PayPal Transaction Search client. Never logs credentials or payloads."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import math
import re
import requests
from urllib.parse import urlsplit


API_PATH = "/v1/reporting/transactions"
TRANSACTION_SEARCH_SCOPE = "https://uri.paypal.com/services/reporting/search/read"
MAX_RANGE = timedelta(days=31)
# Keep demo processing bounded: current transparent rules compare local reference windows.
MAX_PAGES = 20
ORDERS_PATH = "/v2/checkout/orders"
ORDER_ID_PATTERN = re.compile(r"^[A-Z0-9]{1,36}$")


class PayPalAPIError(RuntimeError):
    """Sanitized PayPal integration error safe to surface in the UI."""


@dataclass
class TransactionFetch:
    transactions: list[dict]
    pages_read: int
    total_items_reported: int
    malformed_rows_skipped: int
    start: str
    end: str


class PayPalClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str = "https://api-m.sandbox.paypal.com", timeout: int = 20):
        if not client_id or not client_id.strip() or not client_secret or not client_secret.strip():
            raise ValueError("PayPal client ID and secret are required")
        parsed_base = urlsplit(base_url)
        if parsed_base.scheme != "https" or parsed_base.hostname != "api-m.sandbox.paypal.com" or parsed_base.path not in ("", "/") or parsed_base.username or parsed_base.password:
            raise ValueError("PayGuard accepts only the official PayPal Sandbox API host")
        self.client_id, self.client_secret = client_id.strip(), client_secret.strip()
        self.base_url, self.timeout = "https://api-m.sandbox.paypal.com", timeout
        self._oauth_scopes: set[str] = set()

    @property
    def transaction_search_scope_present(self) -> bool:
        return TRANSACTION_SEARCH_SCOPE in self._oauth_scopes

    @staticmethod
    def _format_time(value: datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("PayPal query datetimes must include a timezone")
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _date_range(self, start: datetime | None, end: datetime | None) -> tuple[str, str]:
        end = end or datetime.now(timezone.utc)
        start = start or end - timedelta(days=7)
        start_text, end_text = self._format_time(start), self._format_time(end)
        if end <= start:
            raise ValueError("PayPal query end must be after start")
        if end - start > MAX_RANGE:
            raise ValueError("PayPal Transaction Search supports a maximum 31-day date range")
        return start_text, end_text

    def _token(self) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                allow_redirects=False,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise PayPalAPIError("PayPal OAuth response was not a JSON object")
            scope = body.get("scope", "")
            self._oauth_scopes = set(scope.split()) if isinstance(scope, str) else set()
            token = body.get("access_token")
            if not isinstance(token, str) or not token:
                raise PayPalAPIError("PayPal OAuth response did not contain an access token")
            return token
        except requests.Timeout as exc:
            raise PayPalAPIError("PayPal OAuth request timed out") from exc
        except requests.RequestException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code == 403:
                raise PayPalAPIError("PayPal Transaction Search denied access (HTTP 403). Check the reporting/search/read scope and Sandbox account permissions.") from exc
            suffix = f" (HTTP {code})" if code else ""
            raise PayPalAPIError(f"PayPal OAuth request failed{suffix}") from exc
        except (ValueError, AttributeError) as exc:
            if isinstance(exc, PayPalAPIError):
                raise
            raise PayPalAPIError("PayPal returned an invalid OAuth response") from exc

    @staticmethod
    def _valid_request_id(request_id: str) -> str:
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 108 or not re.fullmatch(r"[A-Za-z0-9._:-]+", request_id):
            raise ValueError("PayPal-Request-Id must be 1–108 safe ASCII characters")
        return request_id

    @staticmethod
    def _validate_redirect_url(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("PayPal checkout redirect URLs must be HTTP(S) URLs")
        parsed = urlsplit(value)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if not (parsed.scheme == "https" or local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("PayPal checkout redirect URLs must be HTTPS (or localhost HTTP) without credentials or fragments")
        return value

    def _orders_request(self, method: str, path: str, token: str, *, body: dict | None = None, request_id: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json", "Prefer": "return=representation"}
        if request_id is not None:
            headers["PayPal-Request-Id"] = self._valid_request_id(request_id)
        try:
            if method == "POST":
                response = requests.post(f"{self.base_url}{path}", json=body or {}, headers=headers, timeout=self.timeout, allow_redirects=False)
            else:
                response = requests.get(f"{self.base_url}{path}", headers=headers, timeout=self.timeout, allow_redirects=False)
            response.raise_for_status()
            result = response.json()
        except requests.Timeout as exc:
            raise PayPalAPIError(f"PayPal Orders API {method} request timed out") from exc
        except requests.RequestException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {code})" if code else ""
            raise PayPalAPIError(f"PayPal Orders API {method} request failed{suffix}") from exc
        except ValueError as exc:
            raise PayPalAPIError("PayPal Orders API returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise PayPalAPIError("PayPal Orders API returned an invalid response")
        return result

    def create_order(self, amount: str, currency: str, return_url: str, cancel_url: str, request_id: str) -> dict:
        """Create a CAPTURE-intent Sandbox order and return only its ID/status/approval link."""
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("PayPal checkout amount must be a valid positive USD amount") from exc
        if not value.is_finite() or value <= 0 or value > Decimal("10.00"):
            raise ValueError("PayPal Sandbox test amount must be greater than zero and at most USD 10.00")
        if currency != "USD":
            raise ValueError("PayGuard Sandbox checkout currently supports USD only")
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if value <= 0 or value > Decimal("10.00"):
            raise ValueError("PayPal Sandbox test amount must be greater than zero and at most USD 10.00")
        return_url = self._validate_redirect_url(return_url)
        cancel_url = self._validate_redirect_url(cancel_url)
        request_id = self._valid_request_id(request_id)
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": currency, "value": f"{value:.2f}"}}],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "user_action": "PAY_NOW",
                    }
                }
            },
        }
        result = self._orders_request("POST", ORDERS_PATH, self._token(), body=body, request_id=request_id)
        order_id = result.get("id")
        status = result.get("status")
        links = result.get("links")
        if not isinstance(order_id, str) or not ORDER_ID_PATTERN.fullmatch(order_id) or not isinstance(status, str) or not isinstance(links, list):
            raise PayPalAPIError("PayPal Orders API returned incomplete order details")
        approval_url = None
        for link in links:
            if not isinstance(link, dict) or link.get("rel") not in {"approve", "payer-action"} or not isinstance(link.get("href"), str):
                continue
            parsed = urlsplit(link["href"])
            if parsed.scheme == "https" and parsed.hostname == "www.sandbox.paypal.com" and not parsed.username and not parsed.password:
                approval_url = link["href"]
                break
        if approval_url is None:
            raise PayPalAPIError("PayPal Orders API response did not contain a Sandbox approval link")
        return {"id": order_id, "status": status, "approval_url": approval_url}

    def get_order(self, order_id: str) -> dict:
        """Fetch a Sandbox order representation for server-side approval verification."""
        if not isinstance(order_id, str) or not ORDER_ID_PATTERN.fullmatch(order_id):
            raise ValueError("Invalid PayPal order ID")
        result = self._orders_request("GET", f"{ORDERS_PATH}/{order_id}", self._token())
        if result.get("id") != order_id or not isinstance(result.get("status"), str):
            raise PayPalAPIError("PayPal Orders API returned mismatched order details")
        return result

    def capture_order(self, order_id: str, request_id: str) -> dict:
        """Capture an already-approved Sandbox order with a stable idempotency key."""
        if not isinstance(order_id, str) or not ORDER_ID_PATTERN.fullmatch(order_id):
            raise ValueError("Invalid PayPal order ID")
        return self._orders_request("POST", f"{ORDERS_PATH}/{order_id}/capture", self._token(), body={}, request_id=request_id)

    def _search_page(self, token: str, start: str, end: str, page: int, page_size: int) -> dict:
        params = {
            "start_date": start,
            "end_date": end,
            "fields": "transaction_info",
            "balance_affecting_records_only": "N",
            "page_size": page_size,
            "page": page,
        }
        try:
            response = requests.get(
                f"{self.base_url}{API_PATH}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=params,
                timeout=self.timeout,
                allow_redirects=False,
            )
            response.raise_for_status()
            body = response.json()
        except requests.Timeout as exc:
            raise PayPalAPIError("PayPal Transaction Search timed out") from exc
        except requests.RequestException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {code})" if code else ""
            raise PayPalAPIError(f"PayPal Transaction Search failed{suffix}") from exc
        except ValueError as exc:
            raise PayPalAPIError("PayPal Transaction Search returned invalid JSON") from exc
        if not isinstance(body, dict) or not isinstance(body.get("transaction_details"), list):
            raise PayPalAPIError("PayPal Transaction Search response has an invalid transaction_details field")
        pages = body.get("total_pages")
        total = body.get("total_items", 0)
        if not isinstance(pages, int) or isinstance(pages, bool) or pages < 0:
            raise PayPalAPIError("PayPal Transaction Search response has an invalid total_pages field")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise PayPalAPIError("PayPal Transaction Search response has an invalid total_items field")
        if pages == 0 and (total != 0 or body["transaction_details"]):
            raise PayPalAPIError("PayPal Transaction Search returned inconsistent empty-result metadata")
        return body

    @staticmethod
    def _map_transaction(item: dict) -> dict | None:
        if not isinstance(item, dict):
            return None
        tx = item.get("transaction_info")
        if not isinstance(tx, dict):
            return None
        amount = tx.get("transaction_amount")
        if not isinstance(amount, dict):
            return None
        transaction_id = tx.get("transaction_id")
        timestamp = tx.get("transaction_initiation_date")
        value = amount.get("value")
        currency = amount.get("currency_code")
        status = tx.get("transaction_status")
        if not all(isinstance(value, str) and value.strip() for value in (transaction_id, timestamp, currency, status)):
            return None
        try:
            numeric_amount = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric_amount) or numeric_amount < 0:
            return None
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
            return None
        identity = {
            "transaction_id": transaction_id,
            "event_code": tx.get("transaction_event_code"),
            "initiated": timestamp,
            "updated": tx.get("transaction_updated_date"),
            "status": status,
            "amount": value,
            "currency": currency,
            "reference_id": tx.get("paypal_reference_id"),
        }
        signature = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
        return {
            "transaction_id": transaction_id,
            "transaction_key": f"{transaction_id}:{signature}",
            "timestamp": timestamp,
            "amount": numeric_amount,
            "currency": currency,
            "status": status,
            "event_code": tx.get("transaction_event_code"),
            "updated_at": tx.get("transaction_updated_date"),
            "customer_ref": None,
            "order_ref": tx.get("paypal_reference_id"),
            "source": "PayPal Sandbox",
            "is_demo": False,
            "refund_amount": None,
        }

    def test_connection(self) -> dict:
        """Validate OAuth and reporting API access without importing transaction rows."""
        end = datetime.now(timezone.utc)
        start_text, end_text = self._date_range(end - timedelta(hours=1), end)
        body = self._search_page(self._token(), start_text, end_text, page=1, page_size=1)
        return {
            "connected": True,
            "api": "PayPal Transaction Search",
            "transactions_in_probe": len(body["transaction_details"]),
            "total_items_reported": body["total_items"],
            "checked_range": f"{start_text} to {end_text}",
        }

    def fetch_transactions(self, start: datetime | None = None, end: datetime | None = None, page_size: int = 100) -> TransactionFetch:
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 500:
            raise ValueError("PayPal page_size must be between 1 and 500")
        start_text, end_text = self._date_range(start, end)
        token = self._token()
        first = self._search_page(token, start_text, end_text, page=1, page_size=page_size)
        total_pages = first["total_pages"]
        if total_pages > MAX_PAGES:
            raise PayPalAPIError(f"PayPal reported {total_pages} pages; safety limit is {MAX_PAGES} pages of {page_size}. Narrow the requested period.")
        transactions, skipped, key_occurrences = [], 0, {}
        for page in range(1, total_pages + 1):
            body = first if page == 1 else self._search_page(token, start_text, end_text, page, page_size)
            if body["total_pages"] != total_pages or body["total_items"] != first["total_items"]:
                raise PayPalAPIError("PayPal pagination changed during retrieval; retry the query")
            for item in body["transaction_details"]:
                mapped = self._map_transaction(item)
                if mapped is None:
                    skipped += 1
                else:
                    key_occurrences[mapped["transaction_key"]] = key_occurrences.get(mapped["transaction_key"], 0) + 1
                    if key_occurrences[mapped["transaction_key"]] > 1:
                        mapped["transaction_key"] += f":{key_occurrences[mapped['transaction_key']]}"
                    transactions.append(mapped)
        return TransactionFetch(transactions, total_pages, first["total_items"], skipped, start_text, end_text)

