"""
Enhanced logging system for DRADIS
Provides structured, verbose logging for development and debugging
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

class DradisLogger:
    """Custom logger for DRADIS with development mode support"""
    
    def __init__(self, name: str = "DRADIS", dev_mode: bool = False) -> None:
        self.name = name
        self.dev_mode = dev_mode
        self.logger = logging.getLogger(name)
        
        # Create logs directory
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging handlers and formatters"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set base level
        self.logger.setLevel(logging.DEBUG if self.dev_mode else logging.INFO)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(module)-15s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        ) if not self.dev_mode else file_formatter
        
        # File handler - daily rotating
        log_file = self.log_dir / f"dradis-{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if self.dev_mode else logging.INFO)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Development mode file - verbose debug log
        if self.dev_mode:
            debug_file = self.log_dir / "debug.log"
            debug_handler = logging.FileHandler(debug_file, mode='a', encoding='utf-8')
            debug_handler.setLevel(logging.DEBUG)
            debug_formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(pathname)s:%(lineno)d | '
                '%(module)s.%(funcName)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            debug_handler.setFormatter(debug_formatter)
            self.logger.addHandler(debug_handler)
    
    def set_dev_mode(self, enabled: bool) -> None:
        """Toggle development mode"""
        self.dev_mode = enabled
        self._setup_logging()
        self.logger.info(f"Development mode: {'ENABLED' if enabled else 'DISABLED'}")
    
    # Convenience methods
    def debug(self, msg: str, **kwargs) -> None:
        """Log debug message"""
        extra_info = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self.logger.debug(msg + extra_info)
    
    def info(self, msg: str, **kwargs) -> None:
        """Log info message"""
        extra_info = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self.logger.info(msg + extra_info)
    
    def warning(self, msg: str, **kwargs) -> None:
        """Log warning message"""
        extra_info = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self.logger.warning(msg + extra_info)
    
    def error(self, msg: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message"""
        extra_info = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self.logger.error(msg + extra_info, exc_info=exc_info)
    
    def critical(self, msg: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical message"""
        extra_info = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self.logger.critical(msg + extra_info, exc_info=exc_info)
    
    def operation_start(self, operation: str, **details) -> None:
        """Log start of an operation"""
        self.info(f"[START] {operation}", **details)
    
    def operation_end(self, operation: str, success: bool = True, **details) -> None:
        """Log end of an operation"""
        status = "SUCCESS" if success else "FAILED"
        level = self.info if success else self.error
        level(f"[{status}] {operation}", **details)
    
    def progress(self, operation: str, current: int, total: int, **details) -> None:
        """Log progress of an operation"""
        percentage = (current / total * 100) if total > 0 else 0
        self.info(f"[PROGRESS] {operation}: {current}/{total} ({percentage:.1f}%)", **details)


# Global logger instance
_logger: Optional[DradisLogger] = None

def get_logger(dev_mode: bool = False) -> DradisLogger:
    """Get or create the global logger instance"""
    global _logger
    if _logger is None:
        _logger = DradisLogger(dev_mode=dev_mode)
    elif dev_mode and not _logger.dev_mode:
        _logger.set_dev_mode(True)
    return _logger

def set_dev_mode(enabled: bool) -> None:
    """Enable or disable development mode globally"""
    logger = get_logger()
    logger.set_dev_mode(enabled)