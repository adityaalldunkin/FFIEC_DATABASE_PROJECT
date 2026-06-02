"""
FFIEC CDR Public Web Service (REST) client.

Spec: CDR-PDD-SIS-611 v1.10
Base URL: https://ffieccdr.azure-api.us/public/
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Callable

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ffiec_cdr.config import DEFAULT_REQUEST_DELAY_SEC

logger = logging.getLogger(__name__)

BASE_URL = "https://ffieccdr.azure-api.us/public"


class FFIECClientError(Exception):
    """API or response parsing error."""


class FFIECClient:
    """Wrapper around all seven PWS retrieval endpoints with rate limiting and retries."""

    def __init__(
        self,
        user_id: str,
        token: str,
        *,
        timeout: float = 120.0,
        request_delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    ) -> None:
        if not user_id or not token:
            raise ValueError("user_id and token are required")
        self.user_id = user_id.strip()
        raw = token.strip()
        self.token = raw.removeprefix("Bearer ").strip()
        self.timeout = timeout
        self.request_delay_sec = request_delay_sec
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "FFIEC-CDR-Client/1.0"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_delay_sec:
            time.sleep(self.request_delay_sec - elapsed)
        self._last_request_at = time.monotonic()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "UserID": self.user_id,
            "Authentication": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    @retry(
        retry=retry_if_exception_type((FFIECClientError, requests.RequestException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _get(self, path: str, extra_headers: dict[str, str] | None = None) -> Any:
        self._throttle()
        url = f"{BASE_URL}/{path}"
        logger.debug("GET %s", path)
        try:
            response = self._session.get(
                url, headers=self._headers(extra_headers), timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise FFIECClientError(f"{path} network error: {exc}") from exc

        if response.status_code == 401:
            raise FFIECClientError(
                "401 Unauthorized — check UserID, token, and renewal (every 90 days)."
            )
        if response.status_code == 429:
            raise FFIECClientError("429 Too Many Requests — hourly download limit may be hit.")
        if not response.ok:
            raise FFIECClientError(
                f"{path} failed: HTTP {response.status_code}: {response.text[:500]}"
            )
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def _decode_file_payload(payload: Any, *, key: str | None = None) -> bytes:
        if payload is None:
            raise FFIECClientError("Empty file payload in API response")

        if isinstance(payload, dict):
            for field in (key, "FacsimileFile", "XBRLFile", "facsimileFile", "xbrlFile"):
                if field and field in payload:
                    return FFIECClient._decode_file_payload(payload[field])
            raise FFIECClientError(f"Unknown response shape: {list(payload.keys())}")

        if isinstance(payload, list):
            if not payload:
                raise FFIECClientError("Empty byte array in response")
            if isinstance(payload[0], int):
                return bytes(payload)
            if len(payload) == 1:
                return FFIECClient._decode_file_payload(payload[0])
            raise FFIECClientError("Unexpected list payload for file content")

        if isinstance(payload, str):
            try:
                return base64.b64decode(payload, validate=True)
            except Exception:
                return payload.encode("utf-8")

        raise FFIECClientError(f"Unsupported payload type: {type(payload)}")

    def retrieve_reporting_periods(self, *, data_series: str = "Call") -> list[str]:
        data = self._get("RetrieveReportingPeriods", {"dataSeries": data_series})
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "ReportingPeriods" in data:
            return data["ReportingPeriods"]
        raise FFIECClientError(f"Unexpected reporting periods response: {data!r}")

    def retrieve_panel_of_reporters(
        self, reporting_period_end_date: str, *, data_series: str = "Call"
    ) -> list[dict[str, Any]]:
        data = self._get(
            "RetrievePanelOfReporters",
            {
                "dataSeries": data_series,
                "reportingPeriodEndDate": reporting_period_end_date,
            },
        )
        if isinstance(data, list):
            return data
        raise FFIECClientError(f"Unexpected panel response: {type(data)}")

    def retrieve_filers_since_date(
        self,
        reporting_period_end_date: str,
        last_update_datetime: str,
        *,
        data_series: str = "Call",
    ) -> list[int]:
        data = self._get(
            "RetrieveFilersSinceDate",
            {
                "dataSeries": data_series,
                "reportingPeriodEndDate": reporting_period_end_date,
                "lastUpdateDateTime": last_update_datetime,
            },
        )
        if isinstance(data, dict) and "ID_RSSDs" in data:
            return data["ID_RSSDs"]
        if isinstance(data, list):
            return data
        raise FFIECClientError(f"Unexpected filers-since-date response: {data!r}")

    def retrieve_filers_submission_datetime(
        self,
        reporting_period_end_date: str,
        last_update_datetime: str,
        *,
        data_series: str = "Call",
    ) -> list[dict[str, Any]]:
        data = self._get(
            "RetrieveFilersSubmissionDateTime",
            {
                "dataSeries": data_series,
                "reportingPeriodEndDate": reporting_period_end_date,
                "lastUpdateDateTime": last_update_datetime,
            },
        )
        if isinstance(data, list):
            return data
        raise FFIECClientError(f"Unexpected filers-submission response: {data!r}")

    def retrieve_facsimile(
        self,
        reporting_period_end_date: str,
        fi_id: str | int,
        *,
        fi_id_type: str = "ID_RSSD",
        facsimile_format: str = "XBRL",
        data_series: str = "Call",
    ) -> bytes:
        data = self._get(
            "RetrieveFacsimile",
            {
                "dataSeries": data_series,
                "reportingPeriodEndDate": reporting_period_end_date,
                "fiIdType": fi_id_type,
                "fiId": str(fi_id),
                "facsimileFormat": facsimile_format,
            },
        )
        return self._decode_file_payload(data)

    def retrieve_ubpr_reporting_periods(self) -> list[str]:
        data = self._get("RetrieveUBPRReportingPeriods")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "ReportingPeriods" in data:
            return data["ReportingPeriods"]
        raise FFIECClientError(f"Unexpected UBPR periods response: {data!r}")

    def retrieve_ubpr_xbrl_facsimile(
        self,
        reporting_period_end_date: str,
        fi_id: str | int,
        *,
        fi_id_type: str = "ID_RSSD",
    ) -> bytes:
        data = self._get(
            "RetrieveUBPRXBRLFacsimile",
            {
                "reportingPeriodEndDate": reporting_period_end_date,
                "fiIdType": fi_id_type,
                "fiId": str(fi_id),
            },
        )
        return self._decode_file_payload(data, key="XBRLFile")


def client_from_env(load_dotenv_fn: Callable[..., bool] | None = None) -> FFIECClient:
    import os

    if load_dotenv_fn:
        from pathlib import Path

        load_dotenv_fn(Path(__file__).resolve().parents[2] / ".env")

    user_id = os.environ.get("FFIEC_USER_ID", "").strip()
    token = os.environ.get("FFIEC_TOKEN", "").strip()
    if not user_id or not token:
        raise ValueError("Set FFIEC_USER_ID and FFIEC_TOKEN in .env")
    return FFIECClient(user_id, token)
