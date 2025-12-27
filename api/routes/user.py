#!/usr/bin/env python3
"""
API層 - ユーザールート

ユーザーアカウント管理のエンドポイント（アカウント削除）
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import os
from supabase import create_client, Client
from config.loggers import GenericLogger
from ..utils.inventory_auth import get_authenticated_user_and_client

router = APIRouter()
logger = GenericLogger("api", "user")


def get_service_role_client() -> Client:
    """
    サービスロールキーを使用してSupabaseクライアントを取得
    
    Returns:
        Supabaseクライアント（サービスロール権限）
        
    Raises:
        ValueError: 必要な環境変数が設定されていない場合
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        raise ValueError("SUPABASE_URL 環境変数が設定されていません")
    
    if not supabase_service_role_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY 環境変数が設定されていません")
    
    client = create_client(supabase_url, supabase_service_role_key)
    return client


@router.delete("/user/account")
async def delete_user_account(http_request: Request) -> Dict[str, Any]:
    """
    ユーザーアカウントを削除
    
    - 認証済みユーザーのみ実行可能
    - Supabase Admin APIでユーザー削除を実行
    - 関連データはCASCADE削除で自動削除される想定
      - 在庫データ（inventoryテーブル）
      - レシピ履歴（recipe_historysテーブル）
      - ユーザー設定（user_settingsテーブル）
      - OCRマッピング（ocr_item_mappingsテーブル）
    """
    try:
        logger.info("🔍 [API] ユーザーアカウント削除リクエストを受信しました")
        
        # 1. 認証処理とユーザー情報取得
        user_id, _ = await get_authenticated_user_and_client(http_request)
        logger.info(f"🔍 [API] Deleting account for user: {user_id}")
        
        # 2. Service Role Keyを使用してAdminクライアントを作成
        try:
            admin_client = get_service_role_client()
            logger.info("✅ [API] 管理者クライアントの作成に成功しました")
        except ValueError as e:
            logger.error(f"❌ [API] 管理者クライアントの作成に失敗しました: {e}")
            raise HTTPException(
                status_code=500, 
                detail="サーバー設定エラー: 管理者権限の取得に失敗しました"
            )
        
        # 3. Supabase Admin APIでユーザーを削除
        try:
            # Supabase Pythonクライアントでは、admin.auth.admin.delete_user()が提供されていないため、
            # REST APIを直接呼び出す方法を使用
            import httpx
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            # Supabase Admin APIのエンドポイント
            delete_url = f"{supabase_url}/auth/v1/admin/users/{user_id}"
            
            # Admin APIでユーザーを削除
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    delete_url,
                    headers={
                        "Authorization": f"Bearer {supabase_service_role_key}",
                        "apikey": supabase_service_role_key,
                        "Content-Type": "application/json"
                    }
                )
                
                # Supabase Admin APIは成功時に200または204を返す
                if response.status_code in [200, 204]:
                    logger.info(f"✅ [API] User account deleted successfully: {user_id}")
                elif response.status_code == 404:
                    logger.warning(f"⚠️ [API] User not found: {user_id}")
                    raise HTTPException(
                        status_code=404,
                        detail="ユーザーが見つかりませんでした"
                    )
                else:
                    error_msg = f"ユーザー削除に失敗しました: {response.status_code} - {response.text}"
                    logger.error(f"❌ [API] {error_msg}")
                    raise HTTPException(
                        status_code=500,
                        detail="アカウント削除処理でエラーが発生しました"
                    )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ [API] ユーザーアカウントの削除に失敗しました: {e}")
            raise HTTPException(
                status_code=500,
                detail="アカウント削除処理でエラーが発生しました"
            )
        
        # 4. 成功レスポンスを返却
        logger.info(f"✅ [API] Account deletion completed for user: {user_id}")
        return {
            "success": True,
            "message": "アカウントが正常に削除されました"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] アカウント削除処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(
            status_code=500,
            detail="アカウント削除処理でエラーが発生しました"
        )

