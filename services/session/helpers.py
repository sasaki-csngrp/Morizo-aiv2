#!/usr/bin/env python3
"""
SessionService ヘルパー関数

セッションメソッド呼び出しの共通処理を提供
"""

from typing import Any, Optional, Callable


async def call_session_method(
    session_service,
    sse_session_id: str,
    method_name: str,
    session_method: Callable,
    default_return: Any,
    log_success_message: Optional[str] = None
) -> Any:
    """セッションメソッドを呼び出す共通ヘルパー（戻り値あり）
    
    Args:
        session_service: SessionServiceインスタンスへの参照
        sse_session_id: SSEセッションID
        method_name: メソッド名（ログ用）
        session_method: 呼び出すSessionオブジェクトのメソッド（callable）
        default_return: セッションが存在しない場合のデフォルト戻り値
        log_success_message: 成功ログメッセージ（Noneの場合は自動生成）
    
    Returns:
        Any: メソッドの戻り値またはデフォルト値
    """
    try:
        session = await session_service.get_session(sse_session_id, user_id=None)
        if session:
            result = session_method(session)
            if log_success_message:
                session_service.logger.debug(log_success_message)
            else:
                session_service.logger.debug(f"✅ [SessionService] {method_name} completed successfully")
            return result
        return default_return
    except Exception as e:
        session_service.logger.error(f"❌ [SessionService] Error in {method_name}: {e}")
        return default_return


async def call_session_void_method(
    session_service,
    sse_session_id: str,
    method_name: str,
    session_method: Callable,
    log_success_message: Optional[str] = None
) -> None:
    """セッションメソッドを呼び出す共通ヘルパー（戻り値なし）
    
    Args:
        session_service: SessionServiceインスタンスへの参照
        sse_session_id: SSEセッションID
        method_name: メソッド名（ログ用）
        session_method: 呼び出すSessionオブジェクトのメソッド（callable）
        log_success_message: 成功ログメッセージ（Noneの場合は自動生成）
    """
    try:
        session = await session_service.get_session(sse_session_id, user_id=None)
        if session:
            session_method(session)
            if log_success_message:
                session_service.logger.debug(log_success_message)
            else:
                session_service.logger.debug(f"✅ [SessionService] {method_name} completed successfully")
    except Exception as e:
        session_service.logger.error(f"❌ [SessionService] Error in {method_name}: {e}")

