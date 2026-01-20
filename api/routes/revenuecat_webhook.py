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
from ..utils.subscription_service import get_service_role_client, PRODUCT_ID_TO_PLAN

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
        logger.warning("⚠️ [WEBHOOK] REVENUECAT_WEBHOOK_AUTH_TOKENが設定されていません")
        return False
    
    if not authorization:
        logger.warning("⚠️ [WEBHOOK] Authorizationヘッダーが存在しません")
        return False
    
    # Bearerトークンの検証
    # 環境変数からBearerプレフィックスを除去（あれば）
    expected_token = WEBHOOK_AUTH_TOKEN.strip()
    if expected_token.startswith("Bearer "):
        expected_token = expected_token[7:]  # "Bearer "を除去
    
    # AuthorizationヘッダーからBearerプレフィックスを除去（あれば）
    received_token = authorization.strip()
    if received_token.startswith("Bearer "):
        received_token = received_token[7:]  # "Bearer "を除去
    
    # トークンを比較
    if received_token != expected_token:
        logger.warning(f"⚠️ [WEBHOOK] 認証トークンが一致しません: 受信={received_token[:20]}..., 期待={expected_token[:20]}...")
        return False
    
    logger.debug(f"🔍 [WEBHOOK] 認証成功")
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
        
        # Supabaseのauth.usersテーブルでuser_idが存在するか確認
        client = get_service_role_client()
        try:
            # auth.usersテーブルにアクセス（サービスロールキーを使用）
            # 注意: SupabaseのPythonクライアントでは直接auth.usersにアクセスできないため、
            # RPC関数を使用するか、usersテーブル（public.users）を参照する必要がある
            # ここでは、app_user_idをそのままuser_idとして使用し、
            # データベース更新時に存在チェックを行う
            
            # まず、user_subscriptionsテーブルで既存のレコードを確認
            # （これにより、過去にこのuser_idでサブスクリプションが作成されたことがあるか確認）
            existing = client.table("user_subscriptions").select("user_id").eq("user_id", app_user_id).limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # 既存のレコードがある場合、app_user_idをそのままuser_idとして使用
                logger.debug(f"既存のuser_subscriptionsレコードが見つかりました: {app_user_id}")
                return app_user_id
            
            # 既存レコードがない場合でも、app_user_idをそのままuser_idとして使用
            # （アプリ側でRevenueCatのapp_user_idをSupabaseのuser_idに設定している前提）
            # 実際のユーザーが存在しない場合は、データベース更新時にエラーが発生する
            logger.debug(f"app_user_idをuser_idとして使用: {app_user_id}")
            return app_user_id
            
        except Exception as e:
            logger.warning(f"user_idの存在確認中にエラーが発生しました（続行します）: {e}")
            # エラーが発生しても、app_user_idをそのままuser_idとして使用
            # （データベース更新時に存在チェックが行われる）
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
        
        # 更新前の既存レコードの値をログ出力（実行確認のため）
        if existing.data and len(existing.data) > 0:
            existing_data = existing.data[0]
            logger.info(f"🔍 [WEBHOOK] 更新前の既存レコード: user_id={user_id}, plan_type={existing_data.get('plan_type')}, subscription_status={existing_data.get('subscription_status')}, updated_at={existing_data.get('updated_at')}, expires_at={existing_data.get('expires_at')}")
        else:
            logger.info(f"🔍 [WEBHOOK] 既存レコードなし（新規作成）: user_id={user_id}")
        
        jst = ZoneInfo('Asia/Tokyo')
        update_timestamp = datetime.now(jst)
        update_data = {
            "user_id": user_id,
            "plan_type": plan_type,
            "subscription_status": subscription_status,
            "updated_at": update_timestamp.isoformat()
        }
        
        if expires_at:
            update_data["expires_at"] = expires_at.isoformat()
        
        if subscription_id:
            update_data["subscription_id"] = subscription_id
        
        # 更新処理の実行タイムスタンプをログ出力
        logger.info(f"🔍 [WEBHOOK] 更新処理実行タイムスタンプ: {update_timestamp.isoformat()}")
        
        if existing.data and len(existing.data) > 0:
            # 既存レコードを更新
            result = client.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
            logger.info(f"user_subscriptionsを更新: user_id={user_id}, status={subscription_status}")
            
            # 更新後の値をログ出力（実行確認のため）
            if result.data and len(result.data) > 0:
                result_data = result.data[0]
                logger.info(f"🔍 [WEBHOOK] 更新後の値: user_id={user_id}, plan_type={result_data.get('plan_type')}, subscription_status={result_data.get('subscription_status')}, updated_at={result_data.get('updated_at')}, expires_at={result_data.get('expires_at')}")
            else:
                logger.warning(f"⚠️ [WEBHOOK] 更新後の値が取得できませんでした: user_id={user_id}")
        else:
            # 新規レコードを作成
            update_data["purchased_at"] = update_timestamp.isoformat()
            result = client.table("user_subscriptions").insert(update_data).execute()
            logger.info(f"user_subscriptionsを新規作成: user_id={user_id}, status={subscription_status}")
            
            # 作成後の値をログ出力（実行確認のため）
            if result.data and len(result.data) > 0:
                result_data = result.data[0]
                logger.info(f"🔍 [WEBHOOK] 作成後の値: user_id={user_id}, plan_type={result_data.get('plan_type')}, subscription_status={result_data.get('subscription_status')}, updated_at={result_data.get('updated_at')}, expires_at={result_data.get('expires_at')}")
            else:
                logger.warning(f"⚠️ [WEBHOOK] 作成後の値が取得できませんでした: user_id={user_id}")
        
        return True
    except Exception as e:
        logger.error(f"user_subscriptionsの更新に失敗: {e}")
        return False


def parse_revenuecat_event(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    RevenueCatイベントを解析して、必要な情報を抽出
    
    Args:
        event_data: RevenueCatイベントのデータ（eventオブジェクトまたは直接イベントデータ）
    
    Returns:
        Optional[Dict[str, Any]]: 解析結果（失敗時None）
    """
    try:
        event_type = event_data.get("type")
        app_user_id = event_data.get("app_user_id")
        
        if not app_user_id:
            logger.warning("⚠️ [WEBHOOK] app_user_idが存在しません")
            return None
        
        # customer_infoが存在する場合（後方互換性のため）
        customer_info = event_data.get("customer_info", {})
        
        # product_idの値をログ出力（実行確認のため）
        product_id = event_data.get("product_id")
        if product_id:
            logger.info(f"🔍 [WEBHOOK] 受信product_id: {product_id}")
        else:
            logger.info(f"🔍 [WEBHOOK] product_idが存在しません")
        
        # エンタイトルメントの値をログ出力（実行確認のため）
        if customer_info:
            entitlements = customer_info.get("entitlements", {})
            if entitlements:
                active_entitlements = []
                for ent_key, ent_data in entitlements.items():
                    if ent_data.get("is_active", False):
                        active_entitlements.append(ent_key)
                logger.info(f"🔍 [WEBHOOK] アクティブなエンタイトルメント: {active_entitlements if active_entitlements else 'なし'}")
            else:
                logger.info(f"🔍 [WEBHOOK] エンタイトルメント情報が存在しません")
        else:
            logger.info(f"🔍 [WEBHOOK] customer_infoが存在しません")
        
        # エンタイトルメントからプランタイプを判定
        plan_type = "free"
        plan_type_source = "default"  # 判定元を記録
        
        # product_idからプランタイプを判定（優先）
        if product_id:
            # コロン区切りの場合、先頭部分を取得（例: "morizo_pro_monthly:morizo-pro-monthly" -> "morizo_pro_monthly"）
            actual_product_id = product_id.split(":")[0] if ":" in product_id else product_id
            
            # PRODUCT_ID_TO_PLANマッピングからプランタイプを取得
            mapped_plan_type = PRODUCT_ID_TO_PLAN.get(actual_product_id)
            if mapped_plan_type:
                plan_type = mapped_plan_type
                plan_type_source = "product_id"
                logger.info(f"🔍 [WEBHOOK] product_idからプランタイプを判定: {actual_product_id} -> {plan_type}")
            else:
                logger.warning(f"⚠️ [WEBHOOK] product_idがマッピングに存在しません: {actual_product_id}")
        
        # customer_infoからエンタイトルメントを判定（フォールバック）
        # product_idが存在しない場合のみ、エンタイトルメントをチェック
        # これにより、RevenueCatのエンタイトルメント更新遅延の影響を受けない
        if customer_info and plan_type == "free" and not product_id:
            entitlements = customer_info.get("entitlements", {})
            
            # proエンタイトルメントを確認
            if "pro" in entitlements:
                pro_entitlement = entitlements["pro"]
                if pro_entitlement.get("is_active", False):
                    plan_type = "pro"
                    plan_type_source = "entitlement"
            
            # ultimateエンタイトルメントを確認（proより優先）
            if "ultimate" in entitlements:
                ultimate_entitlement = entitlements["ultimate"]
                if ultimate_entitlement.get("is_active", False):
                    plan_type = "ultimate"
                    plan_type_source = "entitlement"
        
        # 判定結果をログ出力（実行確認のため）
        logger.info(f"🔍 [WEBHOOK] プランタイプ判定結果: plan_type={plan_type}, 判定元={plan_type_source}")
        
        # サブスクリプション情報を取得
        subscription_status = "expired"
        expires_at = None
        subscription_id = None
        
        # product_idとapp_user_idからsubscription_idを生成（新しいWebhook形式）
        product_id = event_data.get("product_id")
        if product_id and app_user_id:
            # コロン区切りの場合、先頭部分を取得（例: "morizo_pro_monthly:morizo-pro-monthly" -> "morizo_pro_monthly"）
            actual_product_id = product_id.split(":")[0] if ":" in product_id else product_id
            subscription_id = f"{app_user_id}:{actual_product_id}"
        
        # customer_infoからsubscription_idを取得（フォールバック）
        if customer_info and not subscription_id:
            subscriptions = customer_info.get("subscriptions", {})
            for sub_key, sub_data in subscriptions.items():
                if sub_data.get("is_active", False):
                    subscription_id = sub_key
                    break
        
        # expiration_at_msから有効期限を取得（新しいWebhook形式）
        expiration_at_ms = event_data.get("expiration_at_ms")
        if expiration_at_ms:
            try:
                expires_at = datetime.fromtimestamp(expiration_at_ms / 1000, tz=ZoneInfo('UTC'))
            except Exception as e:
                logger.warning(f"有効期限の解析に失敗 (expiration_at_ms): {expiration_at_ms}, error: {e}")
        
        # customer_infoから有効期限を取得（フォールバック）
        if customer_info and not expires_at:
            subscriptions = customer_info.get("subscriptions", {})
            for sub_key, sub_data in subscriptions.items():
                if sub_data.get("is_active", False):
                    expires_at_str = sub_data.get("expires_date")
                    if expires_at_str:
                        try:
                            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                        except Exception as e:
                            logger.warning(f"有効期限の解析に失敗: {expires_at_str}, error: {e}")
                    break
        
        # イベントタイプに応じてステータスを調整
        if event_type == "CANCELLATION":
            subscription_status = "cancelled"
        elif event_type == "EXPIRATION":
            subscription_status = "expired"
        elif event_type == "RENEWAL":
            subscription_status = "active"
        elif event_type == "INITIAL_PURCHASE":
            subscription_status = "active"
        elif event_type == "TEST":
            # テストイベントの場合、デフォルトでfreeプラン、activeステータス
            plan_type = "free"
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
        logger.error(f"イベントの解析に失敗: {e}", exc_info=True)
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
        # リクエスト受信時のタイムスタンプを記録（ミリ秒単位、実行確認のため）
        request_received_at = datetime.now(ZoneInfo('Asia/Tokyo'))
        request_received_timestamp_ms = int(request_received_at.timestamp() * 1000)
        logger.info(f"🔍 [WEBHOOK] リクエスト受信タイムスタンプ: {request_received_at.isoformat()} ({request_received_timestamp_ms}ms)")
        
        # 認証の検証
        if not verify_webhook_auth(authorization):
            logger.warning("⚠️ [WEBHOOK] Webhook認証に失敗しました")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        
        # リクエストボディを取得
        request_data = await request.json()
        logger.debug(f"🔍 [WEBHOOK] RevenueCat Webhook受信データ: {request_data}")
        
        # RevenueCat Webhookの構造に対応
        # 構造1: { "api_version": "1.0", "event": { ... } }
        # 構造2: { "type": "...", "app_user_id": "...", "customer_info": { ... } } (後方互換性)
        if "event" in request_data:
            # 新しい構造: eventオブジェクトから情報を取得
            event_data = request_data["event"]
            logger.info(f"🔍 [WEBHOOK] RevenueCat Webhookイベントを受信しました (api_version={request_data.get('api_version', 'unknown')}): {event_data.get('type', 'UNKNOWN')}")
        else:
            # 古い構造: 直接イベントデータ
            event_data = request_data
            logger.info(f"🔍 [WEBHOOK] RevenueCat Webhookイベントを受信しました: {event_data.get('type', 'UNKNOWN')}")
        
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
        
        # 更新前の既存レコードの値を取得してログ出力（実行確認のため）
        client = get_service_role_client()
        try:
            existing_before = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
            if existing_before.data and len(existing_before.data) > 0:
                existing_before_data = existing_before.data[0]
                logger.info(f"🔍 [WEBHOOK] 更新処理前の既存レコード: user_id={user_id}, plan_type={existing_before_data.get('plan_type')}, subscription_status={existing_before_data.get('subscription_status')}, updated_at={existing_before_data.get('updated_at')}, expires_at={existing_before_data.get('expires_at')}")
            else:
                logger.info(f"🔍 [WEBHOOK] 更新処理前: 既存レコードなし（新規作成）: user_id={user_id}")
        except Exception as e:
            logger.warning(f"⚠️ [WEBHOOK] 更新処理前の既存レコード取得中にエラー: {e}")
        
        # user_subscriptionsテーブルを更新
        success = update_subscription_status(
            user_id=user_id,
            plan_type=parsed_event["plan_type"],
            subscription_status=parsed_event["subscription_status"],
            expires_at=parsed_event["expires_at"],
            subscription_id=parsed_event["subscription_id"],
            client=client
        )
        
        # 更新後の値を取得してログ出力（実行確認のため）
        try:
            existing_after = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
            if existing_after.data and len(existing_after.data) > 0:
                existing_after_data = existing_after.data[0]
                logger.info(f"🔍 [WEBHOOK] 更新処理後の値: user_id={user_id}, plan_type={existing_after_data.get('plan_type')}, subscription_status={existing_after_data.get('subscription_status')}, updated_at={existing_after_data.get('updated_at')}, expires_at={existing_after_data.get('expires_at')}")
            else:
                logger.warning(f"⚠️ [WEBHOOK] 更新処理後: レコードが見つかりません: user_id={user_id}")
        except Exception as e:
            logger.warning(f"⚠️ [WEBHOOK] 更新処理後の値取得中にエラー: {e}")
        
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

