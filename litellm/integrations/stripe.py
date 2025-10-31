# What is this?
## On Success events log usage and cost to Stripe - creating usage records for metered billing

import json
import os
import uuid
from typing import Literal, Optional

import httpx

import litellm
from litellm._logging import verbose_logger
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_httpx.http_handler import (
    HTTPHandler,
    get_async_httpx_client,
    httpxSpecialProvider,
)


def get_utc_datetime():
    import datetime as dt
    from datetime import datetime

    if hasattr(dt, "UTC"):
        return datetime.now(dt.UTC)  # type: ignore
    else:
        return datetime.utcnow()  # type: ignore


class StripeLogger(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self.validate_environment()
        self.async_http_handler = get_async_httpx_client(
            llm_provider=httpxSpecialProvider.LoggingCallback
        )
        self.sync_http_handler = HTTPHandler()

    def validate_environment(self):
        """
        Expects:
        - STRIPE_API_KEY (required)

        Billing Methods (at least one required):
        - STRIPE_PRICE_ID (for legacy subscription-based billing)
        - STRIPE_METER_EVENT_NAME (for new billing meters)

        Optional:
        - STRIPE_BILLING_METHOD: "meters", "subscriptions", or "both" (default: auto-detect)
        - STRIPE_CHARGE_BY: "end_user_id", "team_id", or "user_id"
        - STRIPE_API_BASE
        """
        missing_keys = []
        if os.getenv("STRIPE_API_KEY", None) is None:
            missing_keys.append("STRIPE_API_KEY")

        # At least one billing method must be configured
        has_subscription = os.getenv("STRIPE_PRICE_ID", None) is not None
        has_meters = os.getenv("STRIPE_METER_EVENT_NAME", None) is not None

        if not has_subscription and not has_meters:
            missing_keys.append("STRIPE_PRICE_ID or STRIPE_METER_EVENT_NAME")

        if len(missing_keys) > 0:
            raise Exception("Missing keys={} in environment.".format(missing_keys))

        # Store billing method configuration
        billing_method = os.getenv("STRIPE_BILLING_METHOD", "auto").lower()
        if billing_method == "auto":
            if has_meters and has_subscription:
                self.billing_method = "both"
            elif has_meters:
                self.billing_method = "meters"
            else:
                self.billing_method = "subscriptions"
        else:
            self.billing_method = billing_method

        verbose_logger.info(f"Stripe billing method: {self.billing_method}")

    def _common_logic(self, kwargs: dict, response_obj) -> dict:
        response_id = response_obj.get("id", kwargs.get("litellm_call_id"))
        timestamp = int(get_utc_datetime().timestamp())
        cost = kwargs.get("response_cost", None)
        model = kwargs.get("model")
        usage = {}

        if (
            isinstance(response_obj, litellm.ModelResponse)
            or isinstance(response_obj, litellm.EmbeddingResponse)
        ) and hasattr(response_obj, "usage"):
            usage = {
                "prompt_tokens": response_obj["usage"].get("prompt_tokens", 0),
                "completion_tokens": response_obj["usage"].get("completion_tokens", 0),
                "total_tokens": response_obj["usage"].get("total_tokens", 0),
            }

        litellm_params = kwargs.get("litellm_params", {}) or {}
        proxy_server_request = litellm_params.get("proxy_server_request") or {}
        end_user_id = proxy_server_request.get("body", {}).get("user", None)
        user_id = litellm_params["metadata"].get("user_api_key_user_id", None)
        team_id = litellm_params["metadata"].get("user_api_key_team_id", None)

        charge_by: Literal["end_user_id", "team_id", "user_id"] = "end_user_id"
        customer_id: Optional[str] = None

        if os.getenv("STRIPE_CHARGE_BY", None) is not None and isinstance(
            os.environ["STRIPE_CHARGE_BY"], str
        ):
            if os.environ["STRIPE_CHARGE_BY"] in [
                "end_user_id",
                "user_id", 
                "team_id",
            ]:
                charge_by = os.environ["STRIPE_CHARGE_BY"]  # type: ignore
            else:
                raise Exception("invalid STRIPE_CHARGE_BY set")

        if charge_by == "end_user_id":
            customer_id = end_user_id
        elif charge_by == "team_id":
            customer_id = team_id
        elif charge_by == "user_id":
            customer_id = user_id

        if customer_id is None:
            raise Exception(
                "Customer ID is not set. Charge_by={}. User_id={}. End_user_id={}. Team_id={}".format(
                    charge_by, user_id, end_user_id, team_id
                )
            )

        # Stripe usage record format
        returned_val = {
            "quantity": usage.get("total_tokens", 1),  # Use total tokens as quantity
            "timestamp": timestamp,
            "action": "increment",  # increment existing usage
            "idempotency_key": str(uuid.uuid4()),  # prevent duplicate charges
            "metadata": {
                "model": model,
                "response_cost": str(cost) if cost else "0",
                "prompt_tokens": str(usage.get("prompt_tokens", 0)),
                "completion_tokens": str(usage.get("completion_tokens", 0)),
                "litellm_call_id": response_id,
                "customer_id": customer_id,
                "charge_by": charge_by,
            }
        }

        verbose_logger.debug(
            "\033[91mLogged Stripe Usage Record:\n{}\033[0m\n".format(returned_val)
        )
        return returned_val

    def _send_meter_event(self, kwargs: dict, response_obj) -> dict:
        """Send usage to Stripe Billing Meters (new API)"""
        timestamp = int(get_utc_datetime().timestamp())
        usage = {}

        if (
            isinstance(response_obj, litellm.ModelResponse)
            or isinstance(response_obj, litellm.EmbeddingResponse)
        ) and hasattr(response_obj, "usage"):
            usage = {
                "prompt_tokens": response_obj["usage"].get("prompt_tokens", 0),
                "completion_tokens": response_obj["usage"].get("completion_tokens", 0),
                "total_tokens": response_obj["usage"].get("total_tokens", 0),
            }

        litellm_params = kwargs.get("litellm_params", {}) or {}
        proxy_server_request = litellm_params.get("proxy_server_request") or {}
        end_user_id = proxy_server_request.get("body", {}).get("user", None)
        user_id = litellm_params["metadata"].get("user_api_key_user_id", None)
        team_id = litellm_params["metadata"].get("user_api_key_team_id", None)

        charge_by: Literal["end_user_id", "team_id", "user_id"] = "end_user_id"
        customer_id: Optional[str] = None

        if os.getenv("STRIPE_CHARGE_BY", None) is not None:
            if os.environ["STRIPE_CHARGE_BY"] in ["end_user_id", "user_id", "team_id"]:
                charge_by = os.environ["STRIPE_CHARGE_BY"]  # type: ignore

        if charge_by == "end_user_id":
            customer_id = end_user_id
        elif charge_by == "team_id":
            customer_id = team_id
        elif charge_by == "user_id":
            customer_id = user_id

        if customer_id is None:
            raise Exception(
                f"Customer ID not set. Charge_by={charge_by}. User_id={user_id}. End_user_id={end_user_id}. Team_id={team_id}"
            )

        event_name = os.getenv("STRIPE_METER_EVENT_NAME", "tokens")

        # Stripe Meter Event format
        meter_event = {
            "event_name": event_name,
            "payload": {
                "stripe_customer_id": customer_id,
                "value": str(usage.get("total_tokens", 1)),
            },
            "timestamp": timestamp,
        }

        verbose_logger.debug(f"Stripe Meter Event: {meter_event}")
        return meter_event

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        api_key = os.getenv("STRIPE_API_KEY")
        _base_url = os.getenv("STRIPE_API_BASE", "https://api.stripe.com")
        _headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Send to Billing Meters if enabled
        if self.billing_method in ["meters", "both"]:
            try:
                meter_event = self._send_meter_event(kwargs=kwargs, response_obj=response_obj)
                meter_url = f"{_base_url.rstrip('/')}/v1/billing/meter_events"

                # Convert meter event to form data
                meter_form = {
                    "event_name": meter_event["event_name"],
                    f"payload[stripe_customer_id]": meter_event["payload"]["stripe_customer_id"],
                    f"payload[value]": meter_event["payload"]["value"],
                    "timestamp": meter_event["timestamp"],
                }

                response = self.sync_http_handler.post(
                    url=meter_url,
                    data=meter_form,
                    headers=_headers,
                )
                response.raise_for_status()
                verbose_logger.debug(f"Sent Stripe Meter Event: {response.text}")
            except Exception as e:
                error_response = getattr(e, "response", None)
                if error_response is not None and hasattr(error_response, "text"):
                    verbose_logger.error(f"Stripe Meter Error: {error_response.text}")
                if self.billing_method == "meters":
                    raise e
                verbose_logger.warning(f"Failed to send meter event, continuing: {e}")

        # Send to Subscription Items if enabled
        if self.billing_method in ["subscriptions", "both"]:
            try:
                price_id = os.getenv("STRIPE_PRICE_ID")
                subscription_url = f"{_base_url.rstrip('/')}/v1/subscription_items/{price_id}/usage_records"

                _data = self._common_logic(kwargs=kwargs, response_obj=response_obj)

                # Convert dict to form data for Stripe API
                form_data = {}
                for key, value in _data.items():
                    if key == "metadata":
                        for meta_key, meta_value in value.items():
                            form_data[f"metadata[{meta_key}]"] = meta_value
                    else:
                        form_data[key] = value

                response = self.sync_http_handler.post(
                    url=subscription_url,
                    data=form_data,
                    headers=_headers,
                )
                response.raise_for_status()
                verbose_logger.debug(f"Sent Stripe Subscription Usage: {response.text}")
            except Exception as e:
                error_response = getattr(e, "response", None)
                if error_response is not None and hasattr(error_response, "text"):
                    verbose_logger.error(f"Stripe Subscription Error: {error_response.text}")
                raise e

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        verbose_logger.debug("ENTERS STRIPE CALLBACK")
        api_key = os.getenv("STRIPE_API_KEY")
        _base_url = os.getenv("STRIPE_API_BASE", "https://api.stripe.com")
        _headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Send to Billing Meters if enabled
        if self.billing_method in ["meters", "both"]:
            response: Optional[httpx.Response] = None
            try:
                meter_event = self._send_meter_event(kwargs=kwargs, response_obj=response_obj)
                meter_url = f"{_base_url.rstrip('/')}/v1/billing/meter_events"

                # Convert meter event to form data
                meter_form = {
                    "event_name": meter_event["event_name"],
                    f"payload[stripe_customer_id]": meter_event["payload"]["stripe_customer_id"],
                    f"payload[value]": meter_event["payload"]["value"],
                    "timestamp": meter_event["timestamp"],
                }

                response = await self.async_http_handler.post(
                    url=meter_url,
                    data=meter_form,
                    headers=_headers,
                )
                response.raise_for_status()
                verbose_logger.debug(f"Sent Stripe Meter Event: {response.text}")
            except Exception as e:
                if response is not None and hasattr(response, "text"):
                    verbose_logger.error(f"Stripe Meter Error: {response.text}")
                if self.billing_method == "meters":
                    raise e
                verbose_logger.warning(f"Failed to send meter event, continuing: {e}")

        # Send to Subscription Items if enabled
        if self.billing_method in ["subscriptions", "both"]:
            response: Optional[httpx.Response] = None
            try:
                price_id = os.getenv("STRIPE_PRICE_ID")
                subscription_url = f"{_base_url.rstrip('/')}/v1/subscription_items/{price_id}/usage_records"

                _data = self._common_logic(kwargs=kwargs, response_obj=response_obj)

                # Convert dict to form data for Stripe API
                form_data = {}
                for key, value in _data.items():
                    if key == "metadata":
                        for meta_key, meta_value in value.items():
                            form_data[f"metadata[{meta_key}]"] = meta_value
                    else:
                        form_data[key] = value

                response = await self.async_http_handler.post(
                    url=subscription_url,
                    data=form_data,
                    headers=_headers,
                )
                response.raise_for_status()
                verbose_logger.debug(f"Sent Stripe Subscription Usage: {response.text}")
            except Exception as e:
                if response is not None and hasattr(response, "text"):
                    verbose_logger.error(f"Stripe Subscription Error: {response.text}")
                raise e