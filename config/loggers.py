"""
Morizo AI v2 - Generic Logger

This module provides a simple, generic logger for all layers of the application.
Each layer is responsible for formatting their own log messages.
"""

import logging
import time
import os
from functools import wraps

from .logging import get_logger


class GenericLogger:
    """Simple generic logger for all application layers"""
    
    def __init__(self, layer: str, component: str = "", initialize_logging: bool = False):
        """
        Initialize generic logger
        
        Args:
            layer: Layer name (api, service, mcp, core)
            component: Component name (optional)
            initialize_logging: Whether to initialize logging system (default: False for MCP servers)
        """
        self.layer = layer
        self.component = component
        
        # Initialize logging system only if requested
        if initialize_logging:
            from .logging import setup_logging
            setup_logging(initialize=True)
        
        self.logger = get_logger(f'{layer}.{component}' if component else layer)
    
    def info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message"""
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log critical message"""
        self.logger.critical(message)


def log_execution_time(func):
    """Decorator to log function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger = get_logger('performance')
            logger.info(f"⏱️ [PERF] {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger = get_logger('performance')
            logger.error(f"⏱️ [PERF] {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


def log_execution_time_async(func):
    """Decorator to log async function execution time"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger = get_logger('performance')
            logger.info(f"⏱️ [PERF] {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger = get_logger('performance')
            logger.error(f"⏱️ [PERF] {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


def log_prompt_with_tokens(prompt: str, max_tokens: int = 4000, logger_name: str = "llm", show_full_prompt: bool = False):
    """プロンプトとトークン数情報をログに記録"""
    logger = get_logger(logger_name)
    
    estimated_tokens = len(prompt) // 4
    token_usage_ratio = estimated_tokens / max_tokens
    
    logger.debug(f"🔤 [PROMPT] 予想トークン数: {estimated_tokens}/{max_tokens} ({token_usage_ratio:.1%})")
    
    # トークン数超過警告
    if token_usage_ratio > 0.8:
        logger.warning(f"⚠️ [PROMPT] トークン数が80%を超過: {token_usage_ratio:.1%}")
    elif token_usage_ratio > 1.0:
        logger.error(f"❌ [PROMPT] トークン数が上限を超過: {token_usage_ratio:.1%}")
    
    # プロンプト内容の表示制御
    if show_full_prompt:
        # 全文表示
        logger.debug(f"🔤 [PROMPT] プロンプト内容（全文）:\n{prompt}")
    else:
        # 5行で省略（現状通り）
        prompt_lines = prompt.split('\n')
        if len(prompt_lines) > 5:
            displayed_prompt = '\n'.join(prompt_lines[:5]) + f"\n... (省略: 残り{len(prompt_lines)-5}行)"
        else:
            displayed_prompt = prompt
        
        logger.debug(f"🔤 [PROMPT] プロンプト内容:\n{displayed_prompt}")


if __name__ == "__main__":
    # Quick verification
    print("✅ 汎用ロガーが利用可能です")