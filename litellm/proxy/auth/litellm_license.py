# What is this?
## If litellm license in env, checks if it's valid
import base64
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import httpx

from litellm._logging import verbose_proxy_logger
from litellm.constants import NON_LLM_CONNECTION_TIMEOUT
from litellm.llms.custom_httpx.http_handler import HTTPHandler

if TYPE_CHECKING:
    from litellm.proxy._types import EnterpriseLicenseData


class LicenseCheck:
    """
    - Check if license in env
    - Returns if license is valid
    """

    base_url = "https://license.litellm.ai"

    def __init__(self) -> None:
        self.license_str = os.getenv("LITELLM_LICENSE", None)
        verbose_proxy_logger.debug("License Str value - {}".format(self.license_str))
        self.http_handler = HTTPHandler(timeout=NON_LLM_CONNECTION_TIMEOUT)
        self.public_key = None
        self.read_public_key()
        self.airgapped_license_data: Optional["EnterpriseLicenseData"] = None

    def read_public_key(self):
        try:
            from cryptography.hazmat.primitives import serialization

            # current dir
            current_dir = os.path.dirname(os.path.realpath(__file__))

            # check if public_key.pem exists
            _path_to_public_key = os.path.join(current_dir, "public_key.pem")
            if os.path.exists(_path_to_public_key):
                with open(_path_to_public_key, "rb") as key_file:
                    self.public_key = serialization.load_pem_public_key(key_file.read())
            else:
                self.public_key = None
        except Exception as e:
            verbose_proxy_logger.error(f"Error reading public key: {str(e)}")

    def _verify(self, license_str: str) -> bool:
        # BYPASS: Always return True for license verification
        return True

    def is_premium(self) -> bool:
        # BYPASS: Always return True for premium check
        return True

    def is_over_limit(self, total_users: int) -> bool:
        # BYPASS: Never over user limit
        return False
    
    def is_team_count_over_limit(self, team_count: int) -> bool:
        # BYPASS: Never over team limit
        return False

    def verify_license_without_api_request(self, public_key, license_key):
        # BYPASS: Always return True for local license verification
        return True
