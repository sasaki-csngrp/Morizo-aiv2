#!/usr/bin/env python3
"""
API層 - サブスクリプションルート

サブスクリプション管理のエンドポイント
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
from config.loggers import GenericLogger
from ..utils.inventory_auth import get_authenticated_user_and_client
from ..utils.subscription_service import SubscriptionService, get_service_role_client, PRODUCT_ID_TO_PLAN
from ..models.responses import UsageLimitExceededResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = GenericLogger("api", "subscription")
subscription_service = SubscriptionService()


class SubscriptionUpdateRequest(BaseModel):
    """サブスクリプション更新リクエスト"""
    plan_type: Optional[str] = Field(None, description="プランタイプ（free, pro, ultimate）。product_idが指定されている場合は省略可能")
    product_id: Optional[str] = Field(None, description="商品ID（morizo_pro_monthly等）。plan_typeが指定されていない場合は必須")
    purchase_token: Optional[str] = Field(None, description="購入トークン（Android用）")
    receipt_data: Optional[str] = Field(None, description="レシートデータ（iOS用）")
    package_name: Optional[str] = Field(None, description="パッケージ名（Android用）")
    subscription_id: Optional[str] = Field(None, description="ストアのサブスクリプションID")
    platform: Optional[str] = Field(None, description="プラットフォーム（ios, android）")
    subscription_status: str = Field(default="active", description="サブスクリプション状態（active, expired, cancelled）")


@router.get("/subscription/plan")
async def get_plan(http_request: Request) -> Dict[str, Any]:
    """
    現在のプラン情報を取得
    
    Returns:
        {
            "success": bool,
            "plan_type": str,  # 'free', 'pro', 'ultimate'
            "subscription_status": str,  # 'active', 'expired', 'cancelled'
            "error": Optional[str]
        }
    """
    try:
        logger.info("🔍 [API] プラン取得リクエストを受信しました")
        
        # 認証処理（user_id取得のため）
        user_id, _ = await get_authenticated_user_and_client(http_request)
        
        # プラン情報を取得（サービスロールクライアントを使用してRLSの影響を排除）
        service_client = get_service_role_client()
        result = await subscription_service.get_user_plan(user_id, service_client)
        
        if not result.get("success"):
            logger.error(f"❌ [API] プラン情報の取得に失敗しました: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "プラン情報の取得に失敗しました")
            )
        
        logger.info(f"✅ [API] Plan retrieved: {result.get('plan_type')}")
        
        return {
            "success": True,
            "plan_type": result.get("plan_type", "free"),
            "subscription_status": result.get("subscription_status", "active")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] プラン情報取得処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="プラン情報の取得でエラーが発生しました")


@router.post("/subscription/update")
async def update_subscription(
    request: SubscriptionUpdateRequest,
    http_request: Request
) -> Dict[str, Any]:
    """
    プラン情報を更新（モバイルアプリから呼び出し）
    
    Args:
        request: サブスクリプション更新リクエスト
    
    Returns:
        {
            "success": bool,
            "message": str,
            "error": Optional[str]
        }
    """
    try:
        logger.info("🔍 [API] サブスクリプション更新リクエストを受信しました")
        logger.debug(f"🔍 [API] Plan type: {request.plan_type}, Product ID: {request.product_id}, Platform: {request.platform}, Subscription status: {request.subscription_status}")
        
        # 認証処理とクライアント作成
        user_id, _ = await get_authenticated_user_and_client(http_request)
        
        # プランタイプの決定（product_idから導出、または直接指定）
        plan_type = request.plan_type
        if not plan_type:
            # plan_typeが指定されていない場合は、product_idから導出
            if not request.product_id:
                raise HTTPException(
                    status_code=400,
                    detail="plan_typeまたはproduct_idのいずれかが必須です"
                )
            
            plan_type = PRODUCT_ID_TO_PLAN.get(request.product_id)
            if not plan_type:
                raise HTTPException(
                    status_code=400,
                    detail=f"無効な商品IDです: {request.product_id}"
                )
            logger.debug(f"🔍 [API] Plan type derived from product_id: {plan_type}")
        
        # プランタイプのバリデーション
        valid_plan_types = ['free', 'pro', 'ultimate']
        if plan_type not in valid_plan_types:
            raise HTTPException(
                status_code=400,
                detail=f"無効なプランタイプです。有効な値: {', '.join(valid_plan_types)}"
            )
        
        # プラットフォームのバリデーション
        if request.platform and request.platform not in ['ios', 'android']:
            raise HTTPException(
                status_code=400,
                detail="無効なプラットフォームです。有効な値: ios, android"
            )
        
        # サービスロールクライアントを取得
        client = get_service_role_client()
        
        # user_subscriptionsテーブルを更新（upsert）
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        update_data = {
            "user_id": user_id,
            "plan_type": plan_type,
            "subscription_status": request.subscription_status,
            "updated_at": datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
        }
        
        if request.subscription_id:
            update_data["subscription_id"] = request.subscription_id
        
        if request.platform:
            update_data["platform"] = request.platform
        
        if request.subscription_status == "active":
            # アクティブな場合は購入日時と有効期限を設定
            jst_now = datetime.now(ZoneInfo('Asia/Tokyo'))
            update_data["purchased_at"] = jst_now.isoformat()
            # 有効期限は1ヶ月後（月額サブスクリプションの場合）
            from datetime import timedelta
            update_data["expires_at"] = (jst_now + timedelta(days=30)).isoformat()
        
        # 更新データのログ出力（原因特定のため）
        logger.debug(f"🔍 [API] 更新データ: plan_type={plan_type}, subscription_status={update_data.get('subscription_status')}, expires_at={update_data.get('expires_at')}, purchased_at={update_data.get('purchased_at')}")
        
        # 既存レコードの存在確認
        existing_result = client.table("user_subscriptions").select("user_id").eq("user_id", user_id).execute()
        is_existing = existing_result.data and len(existing_result.data) > 0
        
        # 既存レコードがある場合はupdate、ない場合はinsertを使用
        if is_existing:
            logger.debug(f"🔍 [API] 既存レコードを更新します: user_id={user_id}")
            result = client.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
            operation = "update"
        else:
            logger.debug(f"🔍 [API] 新規レコードを挿入します: user_id={user_id}")
            result = client.table("user_subscriptions").insert(update_data).execute()
            operation = "insert"
        
        # 操作結果のログ出力（原因特定のため）
        if result.data and len(result.data) > 0:
            result_data = result.data[0]
            logger.debug(f"🔍 [API] {operation}戻り値: plan_type={result_data.get('plan_type')}, subscription_status={result_data.get('subscription_status')}, expires_at={result_data.get('expires_at')}, purchased_at={result_data.get('purchased_at')}, updated_at={result_data.get('updated_at')}")
        else:
            logger.warning(f"⚠️ [API] {operation}の戻り値が空です")
        
        # 更新成功時のログ（原因特定のため）
        logger.info(f"✅ [API] Subscription {operation}d: user={user_id}, plan={plan_type}, status={update_data.get('subscription_status')}, expires_at={update_data.get('expires_at')}")
        
        # 更新後のDBから取得して確認（原因特定のため）
        try:
            verify_result = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
            if verify_result.data and len(verify_result.data) > 0:
                saved_data = verify_result.data[0]
                logger.debug(f"🔍 [API] DB保存確認: plan_type={saved_data.get('plan_type')}, subscription_status={saved_data.get('subscription_status')}, expires_at={saved_data.get('expires_at')}")
        except Exception as e:
            logger.warning(f"⚠️ [API] DB保存確認中にエラー: {e}")
        
        return {
            "success": True,
            "message": "プラン情報を更新しました"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # 一意制約違反エラーの場合、より詳細なエラーメッセージを記録
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            logger.error(f"❌ [API] update_subscription で重複キーエラーが発生しました: {e}")
            logger.debug(f"🔍 [API] Attempting to update existing subscription for user: {user_id}")
            # 既存レコードを更新する処理にフォールバック
            try:
                result = client.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
                logger.info(f"✅ [API] Subscription updated via fallback: user={user_id}, plan={plan_type}")
                return {
                    "success": True,
                    "message": "プラン情報を更新しました"
                }
            except Exception as fallback_error:
                logger.error(f"❌ [API] Fallback update also failed: {fallback_error}")
                raise HTTPException(status_code=500, detail="プラン情報の更新でエラーが発生しました")
        else:
            logger.error(f"❌ [API] サブスクリプション更新処理で予期しないエラーが発生しました: {e}")
            raise HTTPException(status_code=500, detail="プラン情報の更新でエラーが発生しました")


@router.get("/subscription/usage")
async def get_usage(http_request: Request) -> Dict[str, Any]:
    """
    本日の利用回数を取得
    
    Returns:
        {
            "success": bool,
            "date": str,  # YYYY-MM-DD形式
            "menu_bulk_count": int,
            "menu_step_count": int,
            "ocr_count": int,
            "plan_type": str,
            "limits": {
                "menu_bulk": int,
                "menu_step": int,
                "ocr": int
            },
            "error": Optional[str]
        }
    """
    try:
        logger.info("🔍 [API] 利用状況取得リクエストを受信しました")
        
        # 認証処理（user_id取得のため）
        user_id, _ = await get_authenticated_user_and_client(http_request)
        
        # サービスロールクライアントを取得（RLSの影響を排除）
        service_client = get_service_role_client()
        
        # プラン情報を取得（サービスロールクライアントを使用）
        plan_result = await subscription_service.get_user_plan(user_id, service_client)
        plan_type = plan_result.get("plan_type", "free")
        
        # 利用回数を取得（サービスロールクライアントを使用）
        usage_result = await subscription_service.get_usage_limits(user_id, None, service_client)
        
        if not usage_result.get("success"):
            logger.error(f"❌ [API] 利用回数の取得に失敗しました: {usage_result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=usage_result.get("error", "利用回数の取得に失敗しました")
            )
        
        # プランの制限値を取得
        from ..utils.subscription_service import PLAN_LIMITS
        plan_limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS['free'])
        
        # 返却する利用回数の値を取得
        menu_bulk_count = usage_result.get("menu_bulk_count", 0)
        menu_step_count = usage_result.get("menu_step_count", 0)
        ocr_count = usage_result.get("ocr_count", 0)
        
        logger.info(f"✅ [API] Usage retrieved: date={usage_result.get('date')}, menu_bulk_count={menu_bulk_count}, menu_step_count={menu_step_count}, ocr_count={ocr_count}, plan_type={plan_type}")
        
        return {
            "success": True,
            "date": usage_result.get("date"),
            "menu_bulk_count": menu_bulk_count,
            "menu_step_count": menu_step_count,
            "ocr_count": ocr_count,
            "plan_type": plan_type,
            "limits": {
                "menu_bulk": plan_limits.get("menu_bulk", 0),
                "menu_step": plan_limits.get("menu_step", 0),
                "ocr": plan_limits.get("ocr", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 利用回数取得処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="利用回数の取得でエラーが発生しました")

