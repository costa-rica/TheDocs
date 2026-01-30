import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    path_project_resources: str
    email_admin_user: str
    gmail_smtp_user: Optional[str]
    gmail_smtp_app_password: Optional[str]
    gmail_smtp_host: Optional[str]
    gmail_smtp_port: Optional[int]
    openai_api_key: Optional[str]
    secret_key: str
    name_app: str
    run_environment: str
    path_to_logs: Optional[str]


def load_config() -> AppConfig:
    gmail_port_raw = os.getenv("GMAIL_SMTP_PORT")
    gmail_port = int(gmail_port_raw) if gmail_port_raw else None
    return AppConfig(
        path_project_resources=os.getenv("PATH_PROJECT_RESOURCES", ""),
        email_admin_user=os.getenv("EMAIL_ADMIN_USER", ""),
        gmail_smtp_user=os.getenv("GMAIL_SMTP_USER"),
        gmail_smtp_app_password=os.getenv("GMAIL_SMTP_APP_PASSWORD"),
        gmail_smtp_host=os.getenv("GMAIL_SMTP_HOST"),
        gmail_smtp_port=gmail_port,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        secret_key=os.getenv("SECRET_KEY", ""),
        name_app=os.getenv("NAME_APP", ""),
        run_environment=os.getenv("RUN_ENVIRONMENT", ""),
        path_to_logs=os.getenv("PATH_TO_LOGS"),
    )
