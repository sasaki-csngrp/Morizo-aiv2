#!/usr/bin/env python3
"""
API層 - サブスクリプションサービス

プラン管理と利用回数制限のサービス
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional, Tuple
from supabase import Client
from config.loggers import GenericLogger

logger = GenericLogger("api", "subscription_service")


# プラン制限の定義
PLAN_LIMITS = {
    'free': {
        'menu_bulk': 1,      # 献立一括提案: 1回/日
        'menu_step': 3,      # 段階的提案: 3回/日
        'ocr': 1             # OCR読み取り: 1回/日
    },
    'pro': {
        'menu_bulk': 10,     # 献立一括提案: 10回/日
        'menu_step': 30,     # 段階的提案: 30回/日
        'ocr': 10            # OCR読み取り: 10回/日
    },
    'ultimate': {
        'menu_bulk': 100,    # 献立一括提案: 100回/日
        'menu_step': 300,    # 段階的提案: 300回/日
        'ocr': 100           # OCR読み取り: 100回/日
    }
}


def get_jst_date() -> str:
    """
    日本時間（JST）の現在日付を取得（YYYY-MM-DD形式）
    環境のタイムゾーン設定に依存しない
    
    Returns:
        str: YYYY-MM-DD形式の日付文字列
    """
    jst = ZoneInfo('Asia/Tokyo')
    now = datetime.now(jst)
    return now.strftime('%Y-%m-%d')


def get_jst_datetime() -> datetime:
    """
    日本時間（JST）の現在日時を取得
    環境のタイムゾーン設定に依存しない
    
    Returns:
        datetime: JSTの現在日時
    """
    jst = ZoneInfo('Asia/Tokyo')
    return datetime.now(jst)


def get_service_role_client() -> Client:
    """
    サービスロールキーを使用してSupabaseクライアントを取得
    
    Returns:
        Supabaseクライアント（サービスロール権限）
        
    Raises:
        ValueError: 必要な環境変数が設定されていない場合
    """
    from supabase import create_client
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        raise ValueError("SUPABASE_URL 環境変数が設定されていません")
    
    if not supabase_service_role_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY 環境変数が設定されていません")
    
    client = create_client(supabase_url, supabase_service_role_key)
    return client


class SubscriptionService:
    """サブスクリプション管理サービス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("api", "subscription_service")
    
    async def get_user_plan(self, user_id: str, client: Optional[Client] = None) -> Dict[str, Any]:
        """
        ユーザーのプラン情報を取得
        
        Args:
            user_id: ユーザーID
            client: Supabaseクライアント（オプション、指定しない場合はサービスロールを使用）
        
        Returns:
            {
                "success": bool,
                "plan_type": str,  # 'free', 'pro', 'ultimate'
                "subscription_status": str,  # 'active', 'expired', 'cancelled'
                "error": Optional[str]
            }
        """
        try:
            self.logger.debug(f"🔍 [Subscription] Getting plan for user: {user_id}")
            
            # クライアントの取得
            if client is None:
                client = get_service_role_client()
            
            # user_subscriptionsテーブルから取得
            result = client.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
            
            if not result.data:
                # レコードが存在しない場合はfreeプランとして扱う
                self.logger.debug(f"📋 [Subscription] No subscription record found, defaulting to 'free'")
                return {
                    "success": True,
                    "plan_type": "free",
                    "subscription_status": "active"
                }
            
            subscription = result.data[0]
            plan_type = subscription.get("plan_type", "free")
            subscription_status = subscription.get("subscription_status", "active")
            
            self.logger.debug(f"✅ [Subscription] Plan retrieved: {plan_type}, status: {subscription_status}")
            
            return {
                "success": True,
                "plan_type": plan_type,
                "subscription_status": subscription_status
            }
            
        except Exception as e:
            self.logger.error(f"❌ [Subscription] Failed to get user plan: {e}")
            return {
                "success": False,
                "plan_type": "free",
                "subscription_status": "active",
                "error": str(e)
            }
    
    async def get_usage_limits(self, user_id: str, date: Optional[str] = None, client: Optional[Client] = None) -> Dict[str, Any]:
        """
        指定日の利用回数を取得（指定しない場合は本日）
        
        Args:
            user_id: ユーザーID
            date: 日付（YYYY-MM-DD形式、指定しない場合は本日のJST日付）
            client: Supabaseクライアント（オプション、指定しない場合はサービスロールを使用）
        
        Returns:
            {
                "success": bool,
                "date": str,
                "menu_bulk_count": int,
                "menu_step_count": int,
                "ocr_count": int,
                "error": Optional[str]
            }
        """
        try:
            # 日付が指定されていない場合は本日のJST日付を使用
            if date is None:
                date = get_jst_date()
            
            self.logger.debug(f"🔍 [Subscription] Getting usage limits for user: {user_id}, date: {date}")
            
            # クライアントの取得
            if client is None:
                client = get_service_role_client()
            
            # usage_limitsテーブルから取得
            result = client.table("usage_limits").select("*").eq("user_id", user_id).eq("date", date).execute()
            
            if not result.data:
                # レコードが存在しない場合は0回として扱う
                self.logger.debug(f"📋 [Subscription] No usage record found, defaulting to 0")
                return {
                    "success": True,
                    "date": date,
                    "menu_bulk_count": 0,
                    "menu_step_count": 0,
                    "ocr_count": 0
                }
            
            usage = result.data[0]
            
            self.logger.debug(f"✅ [Subscription] Usage retrieved: menu_bulk={usage.get('menu_bulk_count', 0)}, menu_step={usage.get('menu_step_count', 0)}, ocr={usage.get('ocr_count', 0)}")
            
            return {
                "success": True,
                "date": date,
                "menu_bulk_count": usage.get("menu_bulk_count", 0),
                "menu_step_count": usage.get("menu_step_count", 0),
                "ocr_count": usage.get("ocr_count", 0)
            }
            
        except Exception as e:
            self.logger.error(f"❌ [Subscription] Failed to get usage limits: {e}")
            return {
                "success": False,
                "date": date or get_jst_date(),
                "menu_bulk_count": 0,
                "menu_step_count": 0,
                "ocr_count": 0,
                "error": str(e)
            }
    
    async def check_usage_limit(
        self,
        user_id: str,
        feature: str,  # 'menu_bulk', 'menu_step', 'ocr'
        client: Optional[Client] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        利用回数制限をチェック
        
        Args:
            user_id: ユーザーID
            feature: 機能タイプ（'menu_bulk', 'menu_step', 'ocr'）
            client: Supabaseクライアント（オプション、指定しない場合はサービスロールを使用）
        
        Returns:
            (is_allowed: bool, info: Dict[str, Any])
            infoには、制限超過時はエラー情報、許可時は現在の利用状況を含む
        """
        try:
            # プラン情報を取得
            plan_result = await self.get_user_plan(user_id, client)
            if not plan_result.get("success"):
                self.logger.warning(f"⚠️ [Subscription] Failed to get plan, defaulting to 'free'")
                plan_type = "free"
            else:
                plan_type = plan_result.get("plan_type", "free")
            
            # プランの制限値を取得
            plan_limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS['free'])
            limit = plan_limits.get(feature, 0)
            
            # 本日の利用回数を取得
            usage_result = await self.get_usage_limits(user_id, None, client)
            if not usage_result.get("success"):
                self.logger.warning(f"⚠️ [Subscription] Failed to get usage, defaulting to 0")
                current_count = 0
            else:
                if feature == "menu_bulk":
                    current_count = usage_result.get("menu_bulk_count", 0)
                elif feature == "menu_step":
                    current_count = usage_result.get("menu_step_count", 0)
                elif feature == "ocr":
                    current_count = usage_result.get("ocr_count", 0)
                else:
                    self.logger.error(f"❌ [Subscription] Unknown feature: {feature}")
                    return False, {
                        "error": f"Unknown feature: {feature}",
                        "error_code": "INVALID_FEATURE"
                    }
            
            # 制限チェック
            if current_count >= limit:
                # 制限超過
                jst_now = get_jst_datetime()
                # 次の日の0:00（JST）を計算
                next_day = jst_now.replace(hour=0, minute=0, second=0, microsecond=0)
                from datetime import timedelta
                next_day = next_day + timedelta(days=1)
                reset_at = next_day.isoformat()
                
                self.logger.warning(f"⚠️ [Subscription] Usage limit exceeded: user={user_id}, feature={feature}, current={current_count}, limit={limit}")
                
                return False, {
                    "error": "利用回数制限に達しました",
                    "error_code": "USAGE_LIMIT_EXCEEDED",
                    "feature": feature,
                    "current_count": current_count,
                    "limit": limit,
                    "plan": plan_type,
                    "reset_at": reset_at
                }
            
            # 許可
            self.logger.debug(f"✅ [Subscription] Usage limit check passed: user={user_id}, feature={feature}, current={current_count}, limit={limit}")
            
            return True, {
                "plan_type": plan_type,
                "feature": feature,
                "current_count": current_count,
                "limit": limit
            }
            
        except Exception as e:
            self.logger.error(f"❌ [Subscription] Failed to check usage limit: {e}")
            return False, {
                "error": str(e),
                "error_code": "CHECK_LIMIT_ERROR"
            }
    
    async def increment_usage(
        self,
        user_id: str,
        feature: str,  # 'menu_bulk', 'menu_step', 'ocr'
        client: Optional[Client] = None
    ) -> Dict[str, Any]:
        """
        利用回数をインクリメント
        
        Args:
            user_id: ユーザーID
            feature: 機能タイプ（'menu_bulk', 'menu_step', 'ocr'）
            client: Supabaseクライアント（オプション、指定しない場合はサービスロールを使用）
        
        Returns:
            {
                "success": bool,
                "error": Optional[str]
            }
        """
        try:
            # 本日のJST日付を取得
            date = get_jst_date()
            
            self.logger.debug(f"🔍 [Subscription] Incrementing usage: user={user_id}, feature={feature}, date={date}")
            
            # クライアントの取得
            if client is None:
                client = get_service_role_client()
            
            # カラム名のマッピング
            count_column = None
            if feature == "menu_bulk":
                count_column = "menu_bulk_count"
            elif feature == "menu_step":
                count_column = "menu_step_count"
            elif feature == "ocr":
                count_column = "ocr_count"
            else:
                return {
                    "success": False,
                    "error": f"Unknown feature: {feature}"
                }
            
            # 既存レコードを取得
            existing = client.table("usage_limits").select("*").eq("user_id", user_id).eq("date", date).execute()
            
            if existing.data:
                # 既存レコードがある場合は更新
                current_count = existing.data[0].get(count_column, 0)
                new_count = current_count + 1
                
                result = client.table("usage_limits").update({
                    count_column: new_count,
                    "updated_at": datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
                }).eq("user_id", user_id).eq("date", date).execute()
                
                self.logger.debug(f"✅ [Subscription] Usage incremented: {count_column}={new_count}")
            else:
                # レコードが存在しない場合は新規作成
                initial_data = {
                    "user_id": user_id,
                    "date": date,
                    "menu_bulk_count": 0,
                    "menu_step_count": 0,
                    "ocr_count": 0
                }
                initial_data[count_column] = 1
                
                result = client.table("usage_limits").insert(initial_data).execute()
                
                self.logger.debug(f"✅ [Subscription] Usage record created: {count_column}=1")
            
            return {
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"❌ [Subscription] Failed to increment usage: {e}")
            return {
                "success": False,
                "error": str(e)
            }

