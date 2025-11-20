"""
Morizo AI v2 - MCP Decorators

This module provides decorators for common MCP tool operations:
- Authentication
- Logging
- Error handling
"""

from functools import wraps
from typing import Callable, Any, Dict
from supabase import Client
from mcp_servers.utils import get_authenticated_client
from config.loggers import GenericLogger

logger = GenericLogger("mcp", "recipe_decorators", initialize_logging=False)


def authenticated_tool(func: Callable) -> Callable:
    """
    認証処理を自動化するデコレータ
    
    関数の引数からuser_idとtokenを取得し、認証済みクライアントを取得して
    client引数として関数に渡す
    
    user_idが空文字列の場合は認証をスキップ（一部の関数でuser_idがオプショナルな場合があるため）
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # user_idとtokenを取得
        user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
        token = kwargs.get('token')
        
        # user_idが空文字列の場合は認証をスキップ
        if not user_id or user_id == "":
            logger.debug(f"🔐 [RECIPE] Skipping authentication for {func.__name__} (user_id is empty)")
            return await func(*args, **kwargs)
        
        try:
            logger.debug(f"🔐 [RECIPE] Getting authenticated client for user_id={user_id}")
            client = get_authenticated_client(user_id, token)
            logger.info(f"🔐 [RECIPE] Authenticated client created successfully for user: {user_id}")
            
            # clientをkwargsに追加（関数がclient引数を受け取る場合に備える）
            kwargs['client'] = client
            
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ [RECIPE] Authentication failed for {func.__name__}: {e}")
            return {"success": False, "error": f"Authentication failed: {str(e)}"}
    
    return wrapper


def logged_tool(func: Callable) -> Callable:
    """
    ログ出力を自動化するデコレータ
    
    関数の開始・終了・エラーを自動的にログ出力
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"🔧 [RECIPE] Starting {func_name}")
        
        # パラメータをログ出力（tokenはマスク）
        log_params = {}
        for key, value in kwargs.items():
            if key == "token" and value:
                log_params[key] = "***"
            else:
                log_params[key] = value
        
        # argsもログ出力（user_idなどがargsにある場合）
        if args:
            log_params['args'] = args[:2] if len(args) > 2 else args  # 最初の2つだけ
        
        logger.debug(f"🔍 [RECIPE] Parameters: {log_params}")
        
        try:
            result = await func(*args, **kwargs)
            
            if isinstance(result, dict):
                if result.get("success"):
                    logger.info(f"✅ [RECIPE] {func_name} completed successfully")
                else:
                    logger.error(f"❌ [RECIPE] {func_name} failed: {result.get('error')}")
            else:
                logger.info(f"✅ [RECIPE] {func_name} completed")
            
            return result
        except Exception as e:
            logger.error(f"❌ [RECIPE] {func_name} raised exception: {e}")
            raise
    
    return wrapper


def error_handled_tool(func: Callable) -> Callable:
    """
    エラーハンドリングを統一するデコレータ
    
    例外をキャッチして統一フォーマットで返す
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            func_name = func.__name__
            logger.error(f"❌ [RECIPE] Error in {func_name}: {e}")
            import traceback
            logger.error(f"❌ [RECIPE] Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
    
    return wrapper

