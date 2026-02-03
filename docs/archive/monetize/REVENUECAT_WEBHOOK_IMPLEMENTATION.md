# RevenueCat Webhook実装ガイド

## 概要

このドキュメントは、RevenueCat Webhookを実装して、ストアでのサブスクリプション解約や更新をリアルタイムで`user_subscriptions`テーブルに反映するための実装ガイドです。

**対象**: フロントエンド（Morizo-web）とバックエンドサーバー（Morizo-aiv2）  
**最終更新**: 2025年12月7日  
**バージョン**: 1.1

---

## 目次

1. [実装の目的](#実装の目的)
2. [アーキテクチャ概要](#アーキテクチャ概要)
3. [実装手順](#実装手順)
4. [RevenueCatダッシュボードでの設定](#revenuecatダッシュボードでの設定)
5. [テスト方法](#テスト方法)
6. [トラブルシューティング](#トラブルシューティング)

---

## 実装の目的

### 問題点

現在、ストア（Google Play / App Store）でサブスクリプションを解約した場合、`user_subscriptions`テーブルの`subscription_status`が更新されず、`'active'`のまま残る問題があります。

### 解決方法

RevenueCat Webhookを実装することで、以下のイベントをリアルタイムで検知し、`user_subscriptions`テーブルを自動更新します：

- **CANCELLATION**: ユーザーがストアで解約した
- **EXPIRATION**: サブスクリプションが期限切れになった
- **RENEWAL**: サブスクリプションが更新された
- **INITIAL_PURCHASE**: 初回購入

---

## アーキテクチャ概要

### イベントフロー

```
[ストア（Google Play / App Store）]
         ↓ ユーザーが解約/更新
[RevenueCat]
         ↓ Webhookイベントを送信（HTTP POST）
[フロントエンド（Morizo-web）]
         ↓ /api/revenuecat/webhook エンドポイントで受信（Next.js API Route）
[バックエンドサーバー（Morizo-aiv2）]
         ↓ localhost:8000/api/revenuecat/webhook にリクエストを転送
[user_subscriptionsテーブルを更新]
```

**重要**: `morizo-aiv2`は`localhost:8000`でリッスンしているため、外部から直接アクセスできません。そのため、`morizo-web`（Next.js）を経由してWebhookイベントを受信し、内部で`morizo-aiv2`にリクエストを転送する構成になっています。

### 実装場所

- **フロントエンド（Morizo-web）**: Next.js API Route（`/app/api/revenuecat/webhook/route.ts`など、プロジェクト構成に応じて調整）
- **バックエンドサーバー（Morizo-aiv2）**: `/app/Morizo-aiv2/api/routes/revenuecat_webhook.py`（新規作成）
- **データベース**: Supabase `user_subscriptions`テーブル

---

## 実装手順

### ステップ1: 環境変数の設定

#### 1.1 バックエンドサーバー（Morizo-aiv2）の環境変数設定

バックエンドサーバーの`.env`ファイルに、Webhook認証用のトークンを追加します。

```bash
# RevenueCat Webhook認証トークン
REVENUECAT_WEBHOOK_AUTH_TOKEN=Bearer Xz3aHxYNQFcdgRvb
```

**注意**: トークンはランダムな文字列を生成してください。セキュリティのため、本番環境と開発環境で異なるトークンを使用することを推奨します。

#### 1.2 フロントエンド（Morizo-web）の環境変数設定（オプション）

`morizo-web`から`morizo-aiv2`へのリクエスト転送時に、内部認証が必要な場合は、`morizo-web`の`.env`ファイルにも設定を追加してください。

```bash
# Morizo-aiv2の内部エンドポイント
MORIZO_AIV2_URL=http://localhost:8000
```

### ステップ2: フロントエンド（Morizo-web）のWebhookエンドポイント実装

#### 2.1 ファイルの作成

`morizo-web`プロジェクトに、Next.js API Routeを作成します。プロジェクト構成に応じて、以下のいずれかのパスに配置してください：

- **App Routerの場合**: `/app/api/revenuecat/webhook/route.ts`
- **Pages Routerの場合**: `/pages/api/revenuecat/webhook.ts`

#### 2.2 実装コード（App Routerの場合）

```typescript
// app/api/revenuecat/webhook/route.ts
import { NextRequest, NextResponse } from 'next/server';

const MORIZO_AIV2_URL = process.env.MORIZO_AIV2_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    // RevenueCatからのリクエストをそのまま取得
    const body = await request.json();
    const authorization = request.headers.get('authorization');

    // morizo-aiv2にリクエストを転送
    const response = await fetch(`${MORIZO_AIV2_URL}/api/revenuecat/webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authorization || '',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    // morizo-aiv2からのレスポンスをそのまま返す
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Webhook転送エラー:', error);
    return NextResponse.json(
      { status: 'error', message: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

#### 2.3 実装コード（Pages Routerの場合）

```typescript
// pages/api/revenuecat/webhook.ts
import type { NextApiRequest, NextApiResponse } from 'next';

const MORIZO_AIV2_URL = process.env.MORIZO_AIV2_URL || 'http://localhost:8000';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ status: 'error', message: 'Method not allowed' });
  }

  try {
    // RevenueCatからのリクエストをそのまま取得
    const body = req.body;
    const authorization = req.headers.authorization;

    // morizo-aiv2にリクエストを転送
    const response = await fetch(`${MORIZO_AIV2_URL}/api/revenuecat/webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authorization || '',
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    // morizo-aiv2からのレスポンスをそのまま返す
    res.status(response.status).json(data);
  } catch (error) {
    console.error('Webhook転送エラー:', error);
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
}
```

### ステップ3: バックエンドサーバー（Morizo-aiv2）のWebhookエンドポイント実装

#### 3.1 ファイルの作成

`/app/Morizo-aiv2/api/routes/revenuecat_webhook.py`を新規作成します。

#### 3.2 実装コード

```python
"""
RevenueCat Webhookエンドポイント

RevenueCatから送信されるイベントを受信して、user_subscriptionsテーブルを更新します。
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header, status
from pydantic import BaseModel
from supabase import create_client, Client

# ロガーの設定
logger = logging.getLogger(__name__)

# ルーターの作成
router = APIRouter(prefix="/api/revenuecat", tags=["revenuecat"])

# Supabaseクライアントの初期化（サービスロールキーを使用）
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Webhook認証トークン
WEBHOOK_AUTH_TOKEN = os.getenv("REVENUECAT_WEBHOOK_AUTH_TOKEN", "")


# RevenueCat Webhookイベントのモデル
class RevenueCatEvent(BaseModel):
    """RevenueCat Webhookイベントの基本構造"""
    event: Dict[str, Any]
    api_version: Optional[str] = None


class RevenueCatCustomerInfo(BaseModel):
    """RevenueCat CustomerInfoの構造"""
    entitlements: Dict[str, Any]
    subscriptions: Dict[str, Any]
    first_seen: Optional[str] = None
    original_app_user_id: Optional[str] = None
    original_application_version: Optional[str] = None


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
        app_user_id: RevenueCatのapp_user_id（Supabaseのuser_idと同じ）
        
    Returns:
        Optional[str]: user_id（見つからない場合None）
    """
    try:
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
    subscription_id: Optional[str] = None
) -> bool:
    """
    user_subscriptionsテーブルを更新
    
    Args:
        user_id: Supabaseのuser_id
        plan_type: プランタイプ（'free', 'pro', 'ultimate'）
        subscription_status: サブスクリプションステータス（'active', 'expired', 'cancelled'）
        expires_at: 有効期限（オプション）
        subscription_id: ストアのサブスクリプションID（オプション）
        
    Returns:
        bool: 更新が成功した場合True
    """
    try:
        # 既存のレコードを確認
        existing = supabase.table("user_subscriptions").select("*").eq("user_id", user_id).execute()
        
        update_data = {
            "plan_type": plan_type,
            "subscription_status": subscription_status,
            "updated_at": datetime.now().isoformat()
        }
        
        if expires_at:
            update_data["expires_at"] = expires_at.isoformat()
        
        if subscription_id:
            update_data["subscription_id"] = subscription_id
        
        if existing.data and len(existing.data) > 0:
            # 既存レコードを更新
            result = supabase.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
            logger.info(f"user_subscriptionsを更新: user_id={user_id}, status={subscription_status}")
        else:
            # 新規レコードを作成
            update_data["user_id"] = user_id
            update_data["purchased_at"] = datetime.now().isoformat()
            result = supabase.table("user_subscriptions").insert(update_data).execute()
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
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    except:
                        pass
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
    authorization: Optional[str] = Header(None)
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
```

### ステップ4: ルーターの登録

`/app/Morizo-aiv2/api/main.py`にルーターを登録します。

```python
# main.pyに追加
from api.routes import revenuecat_webhook

app.include_router(revenuecat_webhook.router)
```

**注意**: `morizo-aiv2`のエンドポイントは`localhost:8000`でリッスンしているため、外部から直接アクセスできません。必ず`morizo-web`を経由してアクセスしてください。

### ステップ5: 依存関係の確認

以下のPythonパッケージがインストールされていることを確認してください：

```bash
# requirements.txtに追加（必要に応じて）
fastapi
supabase
python-dotenv
```

---

## RevenueCatダッシュボードでの設定

### ステップ1: Webhook設定画面を開く

1. [RevenueCatダッシュボード](https://app.revenuecat.com/)にログイン
2. プロジェクト「Morizo Mobile」を選択
3. 左メニューから「**Integrations**」を選択
4. 「**Webhooks Integration**」セクションを開く
5. 「**New Webhook**」ボタンをクリック

### ステップ2: Webhook情報を入力

#### 2.1 基本設定

- **Webhook name**: `Morizo Backend Webhook`（任意の名前）
- **Webhook URL**: `https://morizo.csngrp.co.jp/api/revenuecat/webhook`
  - 注意: 本番環境のURLを設定してください
  - 開発環境の場合は、開発サーバーのURLを設定
- **Authorization header value**: `.env`ファイルで設定した`REVENUECAT_WEBHOOK_AUTH_TOKEN`の値を入力
  - 例: `Bearer Xz3aHxYNQFcdgRvb`

#### 2.2 環境設定

- **Environment to send events for**: 
  - 開発中: 「**Sandbox**」または「**Both**」を選択
  - 本番環境: 「**Production**」を選択

#### 2.3 イベントフィルター

- **App**: 「**All apps**」を選択（または特定のアプリを選択）
- **Event type**: 「**All events**」を選択（または必要なイベントのみ選択）
  - 推奨イベント:
    - `CANCELLATION`（解約）
    - `EXPIRATION`（期限切れ）
    - `RENEWAL`（更新）
    - `INITIAL_PURCHASE`（初回購入）

### ステップ3: Webhookの保存

「**Save**」ボタンをクリックしてWebhookを保存します。

### ステップ4: Webhookのテスト

RevenueCatダッシュボードで、テストイベントを送信して動作確認を行います。

1. 作成したWebhookを選択
2. 「**Test Webhook**」ボタンをクリック
3. バックエンドサーバーのログを確認して、イベントが正常に受信されているか確認

---

## テスト方法

### テスト1: Webhookエンドポイントの動作確認

#### 1.1 認証テスト

```bash
# 正しい認証トークンでリクエスト
curl -X POST https://morizo.csngrp.co.jp/api/revenuecat/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer Xz3aHxYNQFcdgRvb" \
  -d '{
    "type": "TEST",
    "app_user_id": "test-user-id",
    "customer_info": {
      "entitlements": {},
      "subscriptions": {}
    }
  }'
```

**期待される結果**: HTTP 200 OK

#### 1.2 認証失敗テスト

```bash
# 間違った認証トークンでリクエスト
curl -X POST https://morizo.csngrp.co.jp/api/revenuecat/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wrong-token" \
  -d '{}'
```

**期待される結果**: HTTP 401 Unauthorized

### テスト2: 解約イベントのテスト

#### 2.1 テストデータの準備

実際のRevenueCatイベントの形式に合わせたテストデータを作成します。

```json
{
  "type": "CANCELLATION",
  "app_user_id": "actual-user-id-from-supabase",
  "customer_info": {
    "entitlements": {
      "pro": {
        "is_active": false
      }
    },
    "subscriptions": {
      "morizo_pro_monthly": {
        "is_active": false,
        "expires_date": "2025-12-31T23:59:59Z"
      }
    }
  }
}
```

#### 2.2 テスト実行

```bash
curl -X POST https://morizo.csngrp.co.jp/api/revenuecat/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer Xz3aHxYNQFcdgRvb" \
  -d @test_cancellation_event.json
```

#### 2.3 データベースの確認

Supabaseダッシュボードで、`user_subscriptions`テーブルを確認します。

```sql
SELECT * FROM user_subscriptions 
WHERE user_id = 'actual-user-id-from-supabase';
```

**期待される結果**: `subscription_status`が`'cancelled'`に更新されている

### テスト3: 実際のストアでの解約テスト

1. 開発ビルドでサブスクリプションを購入
2. ストア（Google Play / App Store）でサブスクリプションを解約
3. バックエンドサーバーのログを確認
4. `user_subscriptions`テーブルを確認

---

## トラブルシューティング

### 問題1: Webhookイベントが受信されない

#### 原因
- Webhook URLが正しく設定されていない
- `morizo-web`が起動していない
- `morizo-aiv2`が起動していない
- `morizo-web`から`morizo-aiv2`へのリクエスト転送が失敗している
- ファイアウォールやネットワーク設定の問題

#### 解決方法
1. RevenueCatダッシュボードでWebhook URLを確認（`https://morizo.csngrp.co.jp/api/revenuecat/webhook`）
2. `morizo-web`が起動しているか確認
3. `morizo-aiv2`が起動しているか確認（`localhost:8000`でリッスンしているか）
4. `morizo-web`のログを確認して、リクエスト転送が正常に行われているか確認
5. `morizo-aiv2`のログを確認してエラーがないか確認
6. RevenueCatダッシュボードの「Webhooks」セクションで、送信履歴を確認

### 問題2: 認証エラーが発生する

#### 原因
- `REVENUECAT_WEBHOOK_AUTH_TOKEN`が正しく設定されていない
- RevenueCatダッシュボードで設定した認証トークンと一致していない

#### 解決方法
1. `.env`ファイルで`REVENUECAT_WEBHOOK_AUTH_TOKEN`を確認
2. RevenueCatダッシュボードで設定した認証トークンと一致しているか確認
3. 環境変数が正しく読み込まれているか確認（サーバー再起動が必要な場合あり）

### 問題3: user_subscriptionsテーブルが更新されない

#### 原因
- `app_user_id`と`user_id`のマッピングが正しくない
- Supabaseのサービスロールキーが正しく設定されていない
- RLS（Row Level Security）ポリシーの問題

#### 解決方法
1. ログを確認して、`app_user_id`と`user_id`のマッピングが正しいか確認
2. Supabaseのサービスロールキーが正しく設定されているか確認
3. RLSポリシーでサービスロールが更新権限を持っているか確認

### 問題4: イベントタイプが正しく処理されない

#### 原因
- イベントデータの構造が想定と異なる
- イベントタイプの判定ロジックに問題がある

#### 解決方法
1. ログを確認して、実際のイベントデータの構造を確認
2. `parse_revenuecat_event`関数のロジックを調整
3. RevenueCatの公式ドキュメントでイベント構造を確認

---

## 参考資料

- [RevenueCat Webhooks Documentation](https://docs.revenuecat.com/docs/webhooks)
- [RevenueCat Webhook Events](https://www.revenuecat.com/docs/webhooks)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Python Client](https://github.com/supabase/supabase-py)

---

## 実装チェックリスト

### フロントエンド（Morizo-web）
- [ ] `morizo-web`の環境変数`MORIZO_AIV2_URL`を設定（オプション）
- [ ] Next.js API Route（`/app/api/revenuecat/webhook/route.ts`または`/pages/api/revenuecat/webhook.ts`）を作成
- [ ] `morizo-web`が起動していることを確認

### バックエンドサーバー（Morizo-aiv2）
- [ ] 環境変数`REVENUECAT_WEBHOOK_AUTH_TOKEN`を設定
- [ ] `/app/Morizo-aiv2/api/routes/revenuecat_webhook.py`を作成
- [ ] `main.py`にルーターを登録
- [ ] `morizo-aiv2`が`localhost:8000`で起動していることを確認

### RevenueCat設定
- [ ] RevenueCatダッシュボードでWebhookを設定（URL: `https://morizo.csngrp.co.jp/api/revenuecat/webhook`）

### テスト
- [ ] 認証テストを実行（`morizo-web`経由）
- [ ] 解約イベントのテストを実行（`morizo-web`経由）
- [ ] 実際のストアでの解約テストを実行
- [ ] `morizo-web`のログを確認して正常に動作しているか確認
- [ ] `morizo-aiv2`のログを確認して正常に動作しているか確認
- [ ] `user_subscriptions`テーブルが正しく更新されているか確認

---

**最終更新**: 2025年12月7日  
**バージョン**: 1.1（morizo-web経由の実装に対応）  
**作成者**: AIエージェント協働チーム

