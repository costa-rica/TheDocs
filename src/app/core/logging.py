import os
import sys
from pathlib import Path

from loguru import logger

VALID_ENVIRONMENTS = {"development", "testing", "production"}


def _fatal_env(message: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level="ERROR", format="{time:HH:mm:ss.SSS} | {level} | {message}")
    logger.error(message)
    logger.complete()
    raise SystemExit(1)


def _validate_required_env() -> dict:
    name_app = os.getenv("NAME_APP")
    run_environment = os.getenv("RUN_ENVIRONMENT")
    if not name_app:
        _fatal_env("Missing required environment variable: NAME_APP")
    if not run_environment:
        _fatal_env("Missing required environment variable: RUN_ENVIRONMENT")
    if run_environment not in VALID_ENVIRONMENTS:
        _fatal_env("Invalid RUN_ENVIRONMENT value. Expected development, testing, or production.")

    path_to_logs = os.getenv("PATH_TO_LOGS")
    if run_environment in {"testing", "production"} and not path_to_logs:
        _fatal_env("Missing required environment variable: PATH_TO_LOGS")

    return {
        "name_app": name_app,
        "run_environment": run_environment,
        "path_to_logs": path_to_logs,
    }


def configure_logging() -> None:
    env = _validate_required_env()
    name_app = env["name_app"]
    run_environment = env["run_environment"]
    path_to_logs = env["path_to_logs"]

    logger.remove()
    dev_format = "{time:HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}"
    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}"

    if run_environment == "development":
        logger.add(
            sys.stderr,
            level="DEBUG",
            format=dev_format,
            backtrace=True,
            diagnose=True,
        )
        _install_exception_hook()
        return

    log_dir = Path(path_to_logs)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name_app}.log"
    log_max_size = os.getenv("LOG_MAX_SIZE", "5 MB")
    log_max_files_raw = os.getenv("LOG_MAX_FILES", "5")
    try:
        log_max_files = int(log_max_files_raw)
    except ValueError:
        log_max_files = log_max_files_raw

    if run_environment == "testing":
        logger.add(
            sys.stderr,
            level="INFO",
            format=dev_format,
            backtrace=True,
            diagnose=True,
        )

    logger.add(
        str(log_file),
        level="INFO",
        format=file_format,
        rotation=log_max_size,
        retention=log_max_files,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    _install_exception_hook()


def _install_exception_hook() -> None:
    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
            "Uncaught exception"
        )
        logger.complete()

    sys.excepthook = handle_exception
