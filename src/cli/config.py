import os
from dotenv import load_dotenv
from enum import Enum

load_dotenv()


CONFIG_FILE = "lifecycle_config.yaml"

PLATFORM_SERVICES = [
    {
        "name": "Audit Log",
        "role_id": "bb20eed3-0ebc-41ac-8fd6-adf092259ca1",
        "role_name": "WRITER",
    },
    {
        "name": "Email Service",
        "role_id": "4ec66ab4-7b54-469a-b7a1-177aa2e9681b",
        "role_name": "EMAILSENDER",
    },
]

BACKEND_BASE_URL = f"{os.getenv('BACKEND_BASE_URL', 'https://dev.cxp.cisco.com')}/lifecycle/api/v1/backend"
ENV = os.getenv("ENV", "dev")


class Environment(str, Enum):
    SANDBOX = "sandbox"
    DEV = "dev"
    NPRD = "nprd"
    PROD = "prod"


IAM_BASE_URL = {
    Environment.SANDBOX.value: "https://sbx.cxp.cisco.com",
    Environment.DEV.value: "https://dev.cxp.cisco.com",
    Environment.NPRD.value: "https://nprd.cxp.cisco.com",
    Environment.PROD.value: "https://prod.cxp.cisco.com",
}

ENVIRONMENTS = [env.value for env in Environment]


DEPLOYMENT_BASE_URL = f"{os.getenv('DEPLOYMENT_BASE_URL', 'https://dev.cxp.cisco.com')}/lifecycle/api/v1/deployment"
