import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.DEBUG: '\033[36m',
        logging.INFO: '\033[32m',
        logging.WARNING: '\033[33m',
        logging.ERROR: '\033[31m',
        logging.CRITICAL: '\033[35m',
    }
    RESET_CODE = '\033[0m'

    def format(self, record):
        original_levelname = record.levelname
        color_code = self.COLOR_CODES.get(record.levelno, self.RESET_CODE)
        record.levelname = f"{color_code}{record.levelname}{self.RESET_CODE}"
        result = super().format(record)
        record.levelname = original_levelname
        return result


LOG_DIR = Path(__file__).parent.parent.parent / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_loggers = {}
_setup_done = False


def setup_logging(
    log_level: int = logging.INFO,
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    global _setup_done
    
    if _setup_done:
        return logging.getLogger("app")
    
    if log_dir:
        global LOG_DIR
        LOG_DIR = Path(log_dir)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        colored_formatter = ColoredFormatter(log_format, datefmt=date_format)
        console_handler.setFormatter(colored_formatter)
        root_logger.addHandler(console_handler)
    
    if log_to_file:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"{today}.log"
        
        file_handler = logging.FileHandler(
            log_file,
            mode='a',
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    _setup_done = True
    
    return logging.getLogger("app")


def get_logger(name: str) -> logging.Logger:
    global _setup_done
    
    if not _setup_done:
        setup_logging()
    
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(f"app.{name}")
    _loggers[name] = logger
    
    return logger


class LoggerAdapter:
    def __init__(self, name: str):
        self._logger = get_logger(name)
    
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        self._logger.exception(msg, *args, **kwargs)


def create_logger(name: str) -> LoggerAdapter:
    return LoggerAdapter(name)


if __name__ == "__main__":
    logger = setup_logging(log_level=logging.DEBUG)
    logger.debug("Debug message - detailed diagnostic info")
    logger.info("Info message - normal operation")
    logger.warning("Warning message - something unusual")
    logger.error("Error message - something failed")
    logger.critical("Critical message - serious error")
    
    module_logger = get_logger("services.dinet")
    module_logger.info("Loading model...")
    
    adapter_logger = create_logger("utils.test")
    adapter_logger.info("Using logger adapter")
