#!/usr/bin/env python3
"""
API層 - RevenueCat Webhookルート

RevenueCatから送信されるイベントを受信して、user_subscriptionsテーブルを更新します。
"""

import os
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header, status
from config.loggers import GenericLogger
from ..utils.subscription_service import get_service_role_client

# ロガーの設定
logger = GenericLogger("api", "revenuecat_webhook")

# ルーターの作成
router = APIRouter(prefix="/api/revenuecat", tags=["revenuecat"])

# Webhook認証トークン
WEBHOOK_AUTH_TOKEN = os.getenv("REVENUECAT_WEBHOOK_AUTH_TOKEN", "")


def verify_webhook_auth(authorization: Optional[str] = None) -> bool:
    """
    Webhookリクエストの認証を検証
    
    Args:
        authorization: Authorizationヘッダーの値
        
    Returns:
        bool: 認証が成功した場合True
    """
    if not WEBHOOK_AUTH_TOKEN:
        logger.warning("REVENUECAT_WEBHOOK_AUTH_TOKENが設定されていません")
        return False
    
    if not authorization:
        logger.warning("Authorizationヘッダーが存在しません")
        return False
    
    # Bearerトークンの検証
    expected_token = WEBHOOK_AUTH_TOKEN
    if authorization != expected_token:
        logger.warning(f"認証トークンが一致しません: {authorization[:20]}...")
        return False
    
    return True


def get_user_id_from_app_user_id(app_user_id: str) -> Optional[str]:
    """
    RevenueCatのapp_user_idからSupabaseのuser_idを取得
    
    Args:
        app_user_id: RevenueCatのapp_user_id（Supabaseのuser_idと同じ、UUID形式）
        
    Returns:
        Optional[str]: user_id（見つからない場合None）
    """
    try:
        # UUID形式のバリデーション
        try:
            uuid.UUID(app_user_id)
        except ValueError:
            logger.error(f"app_user_idがUUID形式ではありません: {app_user_id}")
            return None
        
        # app_user_idはSupabaseのuser_idと同じと仮定
        # 必要に応じて、マッピングテーブルを参照する実装に変更可能
        return app_user_id
    except Exception as e:
        logger.error(f"user_idの取得に失敗: {e}")
        return None


def update_subscription_status(
    user_id: str,
    plan_type: str,
    subscription_status: str,
    expires_at: Optional[datetime] = None,
    subscription_id: Optional[str] = None,
    client = None
) -> bool:
    """
    user_subscriptionsテーブルを更新
    
    Args:
        user_id: Supabaseのuser_id
        plan_type: プランタイプ（'free', 'pro', 'ultimate'）
        subscription_status: サブスクリプションステータス（'active', 'expired', 'cancelled'）
        expires_at: 有効期限（オプション）
        subscription_id: ストアのサブスクリプションID（オプション）
        client: Supabaseクライアント（オプション、指定しない場合は新規作成）
        
    Returns:
        bool: 更新が成功した場合True
    """
    try:
        # Supabaseクライアントの取得
        if client is None:
            client = get_service_role_client()
        
        # 既存のレコードを確認
        existing = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
        
        jst = ZoneInfo('Asia/Tokyo')
        update_data = {
            "user_id": user_id,
            "plan_type": plan_type,
            "subscription_status": subscription_status,
            "updated_at": datetime.now(jst).isoformat()
        }
        
        if expires_at:
            update_data["expires_at"] = expires_at.isoformat()
        
        if subscription_id:
            update_data["subscription_id"] = subscription_id
        
        if existing.data and len(existing.data) > 0:
            # 既存レコードを更新
            result = client.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
            logger.info(f"user_subscriptionsを更新: user_id={user_id}, status={subscription_status}")
        else:
            # 新規レコードを作成
            update_data["purchased_at"] = datetime.now(jst).isoformat()
            result = client.table("user_subscriptions").insert(update_data).execute()
            logger.info(f"user_subscriptionsを新規作成: user_id={user_id}, status={subscription_status}")
        
        return True
    except Exception as e:
        logger.error(f"user_subscriptionsの更新に失敗: {e}")
        return False


def parse_revenuecat_event(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    RevenueCatイベントを解析して、必要な情報を抽出
    
    Args:
        event_data: RevenueCatイベントのデータ
        
    Returns:
        Optional[Dict[str, Any]]: 解析結果（失敗時None）
    """
    try:
        event_type = event_data.get("type")
        app_user_id = event_data.get("app_user_id")
        customer_info = event_data.get("customer_info", {})
        
        if not app_user_id:
            logger.warning("app_user_idが存在しません")
            return None
        
        # エンタイトルメントからプランタイプを判定
        entitlements = customer_info.get("entitlements", {})
        plan_type = "free"
        
        # proエンタイトルメントを確認
        if "pro" in entitlements:
            pro_entitlement = entitlements["pro"]
            if pro_entitlement.get("is_active", False):
                plan_type = "pro"
        
        # ultimateエンタイトルメントを確認（proより優先）
        if "ultimate" in entitlements:
            ultimate_entitlement = entitlements["ultimate"]
            if ultimate_entitlement.get("is_active", False):
                plan_type = "ultimate"
        
        # サブスクリプション情報を取得
        subscriptions = customer_info.get("subscriptions", {})
        subscription_status = "expired"
        expires_at = None
        subscription_id = None
        
        # アクティブなサブスクリプションを探す
        for sub_key, sub_data in subscriptions.items():
            if sub_data.get("is_active", False):
                subscription_status = "active"
                expires_at_str = sub_data.get("expires_date")
                if expires_at_str:
                    try:
                        # ISO形式の日時文字列をdatetimeに変換
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    except Exception as e:
                        logger.warning(f"有効期限の解析に失敗: {expires_at_str}, error: {e}")
                subscription_id = sub_key
                break
        
        # イベントタイプに応じてステータスを調整
        if event_type == "CANCELLATION":
            # 解約された場合、現在の有効期限までactive、その後expired
            # ただし、即座にcancelledに設定する方が安全
            subscription_status = "cancelled"
        elif event_type == "EXPIRATION":
            subscription_status = "expired"
        elif event_type == "RENEWAL":
            subscription_status = "active"
        elif event_type == "INITIAL_PURCHASE":
            subscription_status = "active"
        
        return {
            "app_user_id": app_user_id,
            "plan_type": plan_type,
            "subscription_status": subscription_status,
            "expires_at": expires_at,
            "subscription_id": subscription_id,
            "event_type": event_type
        }
    except Exception as e:
        logger.error(f"イベントの解析に失敗: {e}")
        return None


@router.post("/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    RevenueCat Webhookエンドポイント
    
    RevenueCatから送信されるイベントを受信して、user_subscriptionsテーブルを更新します。
    
    Args:
        request: FastAPIリクエストオブジェクト
        authorization: Authorizationヘッダー（オプション）
        
    Returns:
        dict: 処理結果
    """
    try:
        # 認証の検証
        if not verify_webhook_auth(authorization):
            logger.warning("Webhook認証に失敗しました")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        
        # リクエストボディを取得
        event_data = await request.json()
        logger.info(f"RevenueCat Webhookイベントを受信: {event_data.get('type', 'UNKNOWN')}")
        
        # イベントを解析
        parsed_event = parse_revenuecat_event(event_data)
        if not parsed_event:
            logger.warning("イベントの解析に失敗しました")
            return {"status": "error", "message": "Failed to parse event"}
        
        # user_idを取得
        user_id = get_user_id_from_app_user_id(parsed_event["app_user_id"])
        if not user_id:
            logger.warning(f"user_idが見つかりません: app_user_id={parsed_event['app_user_id']}")
            return {"status": "error", "message": "User not found"}
        
        # user_subscriptionsテーブルを更新
        success = update_subscription_status(
            user_id=user_id,
            plan_type=parsed_event["plan_type"],
            subscription_status=parsed_event["subscription_status"],
            expires_at=parsed_event["expires_at"],
            subscription_id=parsed_event["subscription_id"]
        )
        
        if success:
            logger.info(f"Webhook処理が成功しました: user_id={user_id}, event_type={parsed_event['event_type']}")
            return {
                "status": "success",
                "message": "Subscription updated successfully",
                "user_id": user_id,
                "event_type": parsed_event["event_type"]
            }
        else:
            logger.error(f"Webhook処理が失敗しました: user_id={user_id}")
            return {"status": "error", "message": "Failed to update subscription"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook処理中にエラーが発生しました: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

