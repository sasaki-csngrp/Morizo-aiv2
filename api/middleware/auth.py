#!/usr/bin/env python3
"""
API層 - 認証ミドルウェア

Bearer Token認証とユーザー情報の注入
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any
from config.loggers import GenericLogger
from ..utils.auth_handler import get_auth_handler


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """認証ミドルウェア"""
    
    def __init__(self, app):
        """初期化"""
        super().__init__(app)
        self.logger = GenericLogger("api", "auth_middleware")
        
        # 認証が不要なパス
        self.public_paths = {
            "/health",
            "/docs", 
            "/openapi.json",
            "/redoc",
            "/static",  # 静的ファイルは認証不要
            "/api/revenuecat/webhook"  # RevenueCat Webhookは独自の認証を使用
        }
        
        # AuthHandlerは遅延初期化（環境変数読み込み後）
        self._auth_handler = None
    
    @property
    def auth_handler(self):
        """AuthHandlerの遅延初期化"""
        if self._auth_handler is None:
            self._auth_handler = get_auth_handler()
        return self._auth_handler
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        try:
            self.logger.debug(f"🔍 [Auth] Processing request: {request.method} {request.url.path}")
            # 認証が必要なパスかチェック
            if self._requires_auth(request.url.path):
                self.logger.debug(f"🔍 [Auth] Authentication required for path: {request.url.path}")
                # トークンの取得と検証
                user_info = await self._authenticate_request(request)
                if not user_info:
                    self.logger.debug(f"🔍 [Auth] Authentication failed for path: {request.url.path}")
                    raise HTTPException(status_code=401, detail="認証が必要です")
                
                # リクエストにユーザー情報を追加
                request.state.user_info = user_info
                self.logger.info(f"🔐 [Auth] Authenticated user: {user_info['user_id']}")
            
            # 次のミドルウェアまたはルートハンドラーを実行
            response = await call_next(request)
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"❌ [Auth] Middleware error: {e}")
            raise HTTPException(status_code=500, detail="認証処理でエラーが発生しました")
    
    def _requires_auth(self, path: str) -> bool:
        """認証が必要なパスかどうかを判定"""
        # パスが公開パスに含まれているかチェック
        if path in self.public_paths:
            return False
        
        # パスが公開パスで始まっているかチェック
        for public_path in self.public_paths:
            if path.startswith(public_path):
                return False
        
        return True
    
    async def _authenticate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """リクエストを認証"""
        try:
            # Authorizationヘッダーからトークンを取得
            authorization = request.headers.get("Authorization")
            self.logger.debug(f"🔍 [Auth] Authorization header: {'Present' if authorization else 'Missing'}")
            if not authorization:
                self.logger.warning("⚠️ [Auth] No Authorization header")
                return None
            
            # Bearerトークンを抽出
            token = self.auth_handler.extract_token_from_header(authorization)
            if not token:
                self.logger.warning("⚠️ [Auth] Invalid Authorization header format")
                return None
            
            # トークンを検証
            user_info = await self.auth_handler.verify_token(token)
            if not user_info:
                self.logger.warning("⚠️ [Auth] Token verification failed")
                return None
            
            return user_info
            
        except Exception as e:
            self.logger.error(f"❌ [Auth] Authentication failed: {e}")
            return None
