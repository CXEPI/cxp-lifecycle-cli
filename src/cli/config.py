import os
from dotenv import load_dotenv
from enum import Enum

load_dotenv()


CONFIG_FILE = "lifecycle_config.yaml"


BACKEND_BASE_URL = f"{os.getenv('CXP_LIFECYCLE_BASE_URL', 'https://dev.cxp.cisco.com')}/lifecycle/api/v1/backend"
ENV = os.getenv("ENV", "dev")
ENABLE_ALL_ENVIRNMENTS = os.getenv("ENABLE_ALL_ENVIRNMENTS", "false").lower() == "true"


class Environment(str, Enum):
    SANDBOX = "sandbox"
    DEV = "dev"
    NPRD = "nprd"
    PROD = "prod"


BASE_URL_BY_ENV = {
    Environment.SANDBOX.value: "https://sbx.cxp.cisco.com",
    Environment.DEV.value: "https://dev.cxp.cisco.com",
    Environment.NPRD.value: "https://nprd.cxp.cisco.com",
    Environment.PROD.value: "https://prod.cxp.cisco.com",
}

ENVIRONMENTS = [env.value for env in Environment]


def get_deployment_base_url(env: str) -> str:
    """
    Get the deployment base URL based on the environment.
    """
    if env not in ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment: {env}. Valid environments are: {ENVIRONMENTS}"
        )

    return f"{BASE_URL_BY_ENV[env]}/lifecycle/api/v1/deployment"

