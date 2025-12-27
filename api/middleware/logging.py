#!/usr/bin/env python3
"""
API層 - ログミドルウェア

リクエスト・レスポンスログと処理時間の測定
"""

import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from config.loggers import GenericLogger


class LoggingMiddleware(BaseHTTPMiddleware):
    """ログミドルウェア"""
    
    def __init__(self, app):
        """初期化"""
        super().__init__(app)
        self.logger = GenericLogger("api", "logging_middleware")
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        start_time = time.time()
        
        try:
            # リクエストログ
            self._log_request(request)
            
            # 次のミドルウェアまたはルートハンドラーを実行
            response = await call_next(request)
            
            # レスポンスログ
            process_time = time.time() - start_time
            self._log_response(request, response, process_time)
            
            return response
            
        except Exception as e:
            # エラーログ
            process_time = time.time() - start_time
            self._log_error(request, e, process_time)
            raise
    
    def _log_request(self, request: Request):
        """リクエストログ"""
        try:
            # ユーザー情報の取得
            user_id = "anonymous"
            if hasattr(request.state, 'user_info'):
                user_id = request.state.user_info.get('user_id', 'unknown')
            
            # リクエスト情報のログ
            self.logger.info(
                f"🔍 [API] {request.method} {request.url.path} "
                f"ユーザー: {user_id} "
                f"IP: {request.client.host if request.client else 'unknown'}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ [API] Request logging failed: {e}")
    
    def _log_response(self, request: Request, response, process_time: float):
        """レスポンスログ"""
        try:
            # ユーザー情報の取得
            user_id = "anonymous"
            if hasattr(request.state, 'user_info'):
                user_id = request.state.user_info.get('user_id', 'unknown')
            
            # レスポンス情報のログ
            status_emoji = "✅" if response.status_code < 400 else "❌"
            self.logger.info(
                f"{status_emoji} [API] {request.method} {request.url.path} "
                f"ステータス: {response.status_code} "
                f"処理時間: {process_time:.3f}s "
                f"ユーザー: {user_id}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ [API] Response logging failed: {e}")
    
    def _log_error(self, request: Request, error: Exception, process_time: float):
        """エラーログ"""
        try:
            # ユーザー情報の取得
            user_id = "anonymous"
            if hasattr(request.state, 'user_info'):
                user_id = request.state.user_info.get('user_id', 'unknown')
            
            # エラー情報のログ
            self.logger.error(
                f"💥 [API] {request.method} {request.url.path} "
                f"Error: {str(error)} "
                f"Time: {process_time:.3f}s "
                f"User: {user_id}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ [API] Error logging failed: {e}")
