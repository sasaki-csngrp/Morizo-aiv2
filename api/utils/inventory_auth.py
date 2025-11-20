#!/usr/bin/env python3
"""
API層 - 在庫認証ユーティリティ

在庫エンドポイント用の認証処理共通関数
"""

from fastapi import Request, HTTPException
from typing import Tuple
from supabase import Client
from config.loggers import GenericLogger
from mcp_servers.utils import get_authenticated_client

logger = GenericLogger("api", "inventory_auth")


async def get_authenticated_user_and_client(http_request: Request) -> Tuple[str, Client]:
    """
    認証済みユーザー情報とSupabaseクライアントを取得
    
    Args:
        http_request: FastAPIのRequestオブジェクト
    
    Returns:
        Tuple[str, Client]: (user_id, authenticated_client)
    
    Raises:
        HTTPException: 認証に失敗した場合（401エラー）
    """
    # 1. Authorizationヘッダーからトークンを抽出
    authorization = http_request.headers.get("Authorization")
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    
    # 2. リクエストステートからユーザー情報を取得
    user_info = getattr(http_request.state, 'user_info', None)
    if not user_info:
        logger.error("❌ [API] User info not found in request state")
        raise HTTPException(status_code=401, detail="認証が必要です")
    
    user_id = user_info['user_id']
    logger.debug(f"🔍 [API] User ID: {user_id}")
    
    # 3. 認証済みSupabaseクライアントの作成
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
    except Exception as e:
        logger.error(f"❌ [API] Failed to create authenticated client: {e}")
        raise HTTPException(status_code=401, detail="認証に失敗しました")
    
    return user_id, client

