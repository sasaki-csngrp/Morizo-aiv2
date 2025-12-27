#!/usr/bin/env python3
"""
API層 - 認証処理

Supabase Auth連携とトークン検証
"""

import os
from typing import Optional, Dict, Any
from supabase import create_client, Client
from config.loggers import GenericLogger


class AuthHandler:
    """認証処理クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("api", "auth")
        
        # 環境変数のデバッグログ
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        self.logger.debug(f"🔍 [Auth] 環境変数の確認:")
        self.logger.debug(f"  SUPABASE_URL: {'SET' if self.supabase_url else 'NOT SET'}")
        self.logger.debug(f"  SUPABASE_KEY: {'SET' if self.supabase_key else 'NOT SET'}")
        
        if self.supabase_url:
            self.logger.debug(f"  SUPABASE_URL value: {self.supabase_url[:20]}..." if len(self.supabase_url) > 20 else f"  SUPABASE_URL value: {self.supabase_url}")
        if self.supabase_key:
            self.logger.debug(f"  SUPABASE_KEY value: {self.supabase_key[:20]}..." if len(self.supabase_key) > 20 else f"  SUPABASE_KEY value: {self.supabase_key}")
        
        # Supabaseクライアントの初期化
        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.logger.info("✅ [Auth] Supabaseクライアントを初期化しました")
        else:
            self.supabase = None
            self.logger.warning("⚠️ [Auth] Supabase認証情報が見つかりません")
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """トークンを検証してユーザー情報を取得"""
        try:
            if not self.supabase:
                self.logger.error("❌ [Auth] Supabaseクライアントが利用できません")
                return None
            
            # Supabaseでトークンを検証
            response = self.supabase.auth.get_user(token)
            
            if response.user:
                user_info = {
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "created_at": response.user.created_at,
                    "last_sign_in": response.user.last_sign_in_at
                }
                
                self.logger.info(f"✅ [Auth] トークン検証完了 ユーザー: {user_info['user_id']}")
                return user_info
            else:
                self.logger.warning("⚠️ [Auth] 無効なトークンです")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ [Auth] Token verification failed: {e}")
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """リフレッシュトークンで新しいアクセストークンを取得"""
        try:
            if not self.supabase:
                return None
            
            response = self.supabase.auth.refresh_session(refresh_token)
            
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at
                }
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"❌ [Auth] Token refresh failed: {e}")
            return None
    
    def extract_token_from_header(self, authorization_header: str) -> Optional[str]:
        """Authorizationヘッダーからトークンを抽出"""
        try:
            if not authorization_header:
                return None
            
            if authorization_header.startswith("Bearer "):
                return authorization_header[7:]
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"❌ [Auth] Token extraction failed: {e}")
            return None
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """ユーザープロフィールを取得"""
        try:
            if not self.supabase:
                return None
            
            # ユーザープロフィールテーブルから情報を取得
            response = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            
            if response.data:
                return response.data[0]
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"❌ [Auth] Profile fetch failed: {e}")
            return None


# グローバル認証ハンドラーインスタンス
_auth_handler: Optional[AuthHandler] = None


def get_auth_handler() -> AuthHandler:
    """認証ハンドラーのシングルトン取得"""
    global _auth_handler
    if _auth_handler is None:
        _auth_handler = AuthHandler()
    return _auth_handler
