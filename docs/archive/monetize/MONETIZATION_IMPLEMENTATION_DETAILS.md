# 収益化機能実装 - 詳細注意事項

## 概要

このドキュメントは、収益化機能実装における重要な注意事項を詳細に記述したものです。実装前に必ず確認し、各項目について適切に対応してください。

**関連ドキュメント**: [収益化機能実装プラン](./MONETIZATION_IMPLEMENTATION_PLAN.md)

---

## 1. ストア設定

### 1.1 Google Play Console

#### 1.1.1 サブスクリプション商品の登録

**手順**:

1. **Google Play Console**にログイン
2. **収益化** → **定期購入** → **定期購入商品を作成**を選択
3. 以下の商品を作成：

| 商品ID | プラン名 | 説明 | 価格 |
|--------|----------|------|------|
| `morizo_pro_monthly` | Morizo PRO | 月額サブスクリプション | 設定値 |
| `morizo_ultimate_monthly` | Morizo ULTIMATE | 月額サブスクリプション | 設定値 |

**商品IDの命名規則**:
- 小文字とアンダースコアのみ使用
- プランタイプ（pro, ultimate）を含める
- 期間（monthly, yearly）を含める
- 例: `morizo_pro_monthly`, `morizo_ultimate_yearly`

#### 1.1.2 商品設定の詳細

**必須設定項目**:

- **商品ID**: 上記の命名規則に従う
- **名前**: ユーザーに表示される商品名
- **説明**: 商品の詳細説明
- **価格**: 各ストアの通貨で設定
- **無料トライアル期間**: 必要に応じて設定（例: 7日間）
- **プロモーション期間**: 必要に応じて設定

**重要**: 商品IDは、バックエンドとモバイルアプリの両方で使用するため、変更が困難です。慎重に決定してください。

#### 1.1.3 テストアカウントの設定

1. **Google Play Console** → **設定** → **ライセンステスト**
2. テスト用のGoogleアカウントを追加
3. テストアカウントで購入した場合、実際の課金は発生しません

**注意**: テストアカウントは最大20アカウントまで登録可能です。

---

### 1.2 App Store Connect

#### 1.2.1 サブスクリプション商品の登録

**手順**:

1. **App Store Connect**にログイン
2. **マイApp** → 対象アプリを選択
3. **収益化** → **定期購入** → **+** をクリック
4. 以下の商品を作成：

| 商品ID | プラン名 | 説明 | 価格 |
|--------|----------|------|------|
| `morizo_pro_monthly` | Morizo PRO | 月額サブスクリプション | 設定値 |
| `morizo_ultimate_monthly` | Morizo ULTIMATE | 月額サブスクリプション | 設定値 |

**商品IDの命名規則**:
- Google Play Consoleと同じIDを使用することを推奨（プラットフォーム間の一貫性）
- 小文字とアンダースコアのみ使用
- プランタイプ（pro, ultimate）を含める
- 期間（monthly, yearly）を含める

#### 1.2.2 サブスクリプショングループの作成

1. **サブスクリプショングループ**を作成（例: "Morizo Plans"）
2. 作成した商品をグループに追加
3. グループ内の商品は、ユーザーが切り替え可能

**重要**: サブスクリプショングループは、ユーザーがプランを変更する際に使用されます。

#### 1.2.3 サンドボックステストアカウントの設定

1. **ユーザーとアクセス** → **サンドボックステスター**
2. テスト用のApple IDを追加
3. サンドボックス環境で購入テストを実行

**注意**: サンドボックス環境では、実際の課金は発生しません。

---

### 1.3 商品IDのマッピング

バックエンドとモバイルアプリで使用する商品IDのマッピングを定義します。

**バックエンド設定例** (`api/utils/subscription_service.py`):

```python
# 商品IDからプランタイプへのマッピング
PRODUCT_ID_TO_PLAN = {
    'morizo_pro_monthly': 'pro',
    'morizo_pro_yearly': 'pro',
    'morizo_ultimate_monthly': 'ultimate',
    'morizo_ultimate_yearly': 'ultimate'
}

# プランタイプから商品IDへのマッピング（デフォルトは月額）
PLAN_TO_PRODUCT_ID = {
    'pro': 'morizo_pro_monthly',
    'ultimate': 'morizo_ultimate_monthly'
}
```

**モバイルアプリ設定例** (`/app/Morizo-mobile/config/subscription.ts`):

```typescript
export const SUBSCRIPTION_PRODUCTS = {
  PRO_MONTHLY: 'morizo_pro_monthly',
  PRO_YEARLY: 'morizo_pro_yearly',
  ULTIMATE_MONTHLY: 'morizo_ultimate_monthly',
  ULTIMATE_YEARLY: 'morizo_ultimate_yearly',
} as const;
```

---

## 2. テスト環境

### 2.1 サンドボックス環境

#### 2.1.1 Google Play サンドボックス環境

**設定方法**:

1. **Google Play Console**でテストアカウントを登録（セクション1.1.3参照）
2. テストデバイスにテストアカウントでログイン
3. アプリ内で購入を実行

**注意事項**:
- サンドボックス環境では、実際の課金は発生しません
- テストアカウントで購入した商品は、24時間後に自動的にキャンセルされます
- 本番環境とサンドボックス環境では、商品IDが異なる場合があります（通常は同じ）

#### 2.1.2 App Store サンドボックス環境

**設定方法**:

1. **App Store Connect**でサンドボックステスターを登録（セクション1.2.3参照）
2. テストデバイスでサンドボックステスターのApple IDでログイン
3. アプリ内で購入を実行

**注意事項**:
- サンドボックス環境では、実際の課金は発生しません
- サンドボックステスターのアカウントは、本番環境のApp Storeでは使用できません
- サンドボックス環境と本番環境では、商品IDは同じです

#### 2.1.3 テストフロー

**推奨テストフロー**:

1. **サンドボックス環境でのテスト**
   - 購入フローのテスト
   - レシート検証のテスト
   - プラン更新のテスト
   - エラーハンドリングのテスト

2. **本番環境でのテスト**（リリース前）
   - 実際の購入（小額）でのテスト
   - レシート検証の確認
   - プラン更新の確認

---

### 2.2 レシート検証

#### 2.2.1 レシート検証の重要性

**セキュリティ上の理由**:
- モバイルアプリからの購入情報は、改ざんされる可能性があります
- バックエンドでレシートを検証することで、不正な購入を防ぎます
- ストアが発行するレシートは、改ざんが困難です

#### 2.2.2 Google Play レシート検証

**検証方法**:

1. **モバイルアプリ**: Google Play Billing Libraryから購入トークンを取得
2. **バックエンド**: Google Play Developer APIを使用してトークンを検証

**実装例** (`api/utils/receipt_verification.py`):

```python
import httpx
from typing import Dict, Any

async def verify_google_play_receipt(
    purchase_token: str,
    product_id: str,
    package_name: str
) -> Dict[str, Any]:
    """
    Google Play レシート検証
    
    Args:
        purchase_token: 購入トークン
        product_id: 商品ID
        package_name: アプリのパッケージ名
    
    Returns:
        検証結果（購入情報を含む）
    """
    # Google Play Developer APIを使用してトークンを検証
    # 実装詳細は省略
    pass
```

**必要な設定**:
- Google Play Consoleで**APIアクセス**を有効化
- サービスアカウントの作成と認証情報の取得
- バックエンドに認証情報を設定（環境変数）

#### 2.2.3 App Store レシート検証

**検証方法**:

1. **モバイルアプリ**: StoreKitからレシートデータを取得
2. **バックエンド**: App Store Server APIまたはApp Store Receipt Validation APIを使用してレシートを検証

**実装例** (`api/utils/receipt_verification.py`):

```python
import httpx
from typing import Dict, Any

async def verify_app_store_receipt(
    receipt_data: str,
    password: str  # App Store Connectの共有シークレット
) -> Dict[str, Any]:
    """
    App Store レシート検証
    
    Args:
        receipt_data: レシートデータ（Base64エンコード）
        password: App Store Connectの共有シークレット
    
    Returns:
        検証結果（購入情報を含む）
    """
    # App Store Receipt Validation APIを使用してレシートを検証
    # 実装詳細は省略
    pass
```

**必要な設定**:
- App Store Connectで**共有シークレット**を生成
- バックエンドに共有シークレットを設定（環境変数）

#### 2.2.4 レシート検証のエラーハンドリング

**エラーケース**:
- レシートが無効（改ざんされている）
- レシートが期限切れ
- ネットワークエラー
- ストアAPIのエラー

**対応**:
- エラーログを記録
- ユーザーに適切なエラーメッセージを表示
- 購入処理をロールバック（必要に応じて）

---

## 3. セキュリティ

### 3.1 レシート検証の実装

#### 3.1.1 バックエンドでの検証

**重要**: レシート検証は、**必ずバックエンドで実行**してください。モバイルアプリでの検証は、改ざんされる可能性があるため、信頼できません。

**検証フロー**:

1. **モバイルアプリ**: 購入完了後、レシート（トークン）をバックエンドに送信
2. **バックエンド**: ストアAPIを使用してレシートを検証
3. **バックエンド**: 検証成功後、データベースのプラン情報を更新
4. **バックエンド**: モバイルアプリに検証結果を返す

**実装例** (`api/routes/subscription.py`):

```python
@router.post("/subscription/update")
async def update_subscription(
    request: SubscriptionUpdateRequest,
    http_request: Request
):
    """
    サブスクリプション更新（レシート検証を含む）
    """
    user_id, client = await get_authenticated_user_and_client(http_request)
    
    # プラットフォーム判定
    platform = request.platform  # 'ios' or 'android'
    
    # レシート検証
    if platform == 'android':
        verification_result = await verify_google_play_receipt(
            purchase_token=request.purchase_token,
            product_id=request.product_id,
            package_name=request.package_name
        )
    elif platform == 'ios':
        verification_result = await verify_app_store_receipt(
            receipt_data=request.receipt_data,
            password=os.getenv('APP_STORE_SHARED_SECRET')
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    # 検証失敗時
    if not verification_result.get('valid'):
        raise HTTPException(
            status_code=400,
            detail="Receipt verification failed"
        )
    
    # プラン情報を更新
    # 実装詳細は省略
    pass
```

#### 3.1.2 レシート検証のタイミング

**検証タイミング**:
- **購入時**: 初回購入時の検証
- **更新時**: サブスクリプション更新時の検証
- **復元時**: ユーザーがアプリを再インストールした際の復元処理

**注意**: サブスクリプションの自動更新時も、ストアから通知が来るため、その際にも検証が必要です。

---

### 3.2 プラットフォーム判定

#### 3.2.1 iOS/Androidの判定方法

**モバイルアプリからの判定**:

```typescript
// React Nativeでの実装例
import { Platform } from 'react-native';

const platform = Platform.OS === 'ios' ? 'ios' : 'android';
```

**バックエンドでの判定**:

```python
# リクエストヘッダーから判定（推奨）
platform = request.headers.get('X-Platform')  # 'ios' or 'android'

# または、リクエストボディから判定
platform = request_body.get('platform')
```

#### 3.2.2 プラットフォーム別の処理

**レシート検証**:
- iOS: App Store Receipt Validation APIを使用
- Android: Google Play Developer APIを使用

**商品ID**:
- iOS/Androidで同じ商品IDを使用することを推奨（管理が容易）

**エラーハンドリング**:
- プラットフォームごとに異なるエラーメッセージを返す場合がある

---

### 3.3 サービスロールキーの使用

#### 3.3.1 サービスロールキーの重要性

**理由**:
- データベースの更新（プラン情報、利用回数）は、サービスロールキーを使用する必要があります
- 通常のユーザートークンでは、RLS（Row Level Security）の制約により、更新できない場合があります

#### 3.3.2 サービスロールキーの設定

**環境変数**:

```bash
# .envファイル
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

**注意**: サービスロールキーは、**絶対に公開しないでください**。バックエンドの環境変数にのみ保存してください。

#### 3.3.3 サービスロールキーの使用例

**実装例** (`api/utils/subscription_service.py`):

```python
import os
from supabase import create_client, Client

def get_service_role_client() -> Client:
    """
    サービスロールキーを使用してSupabaseクライアントを取得
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_role_key:
        raise ValueError("Supabase credentials not set")
    
    return create_client(supabase_url, supabase_service_role_key)

async def update_user_plan(
    user_id: str,
    plan_type: str,
    subscription_id: str,
    platform: str
):
    """
    ユーザーのプラン情報を更新（サービスロールキーを使用）
    """
    client = get_service_role_client()
    
    # user_subscriptionsテーブルを更新
    result = client.table("user_subscriptions").upsert({
        "user_id": user_id,
        "plan_type": plan_type,
        "subscription_status": "active",
        "subscription_id": subscription_id,
        "platform": platform,
        "purchased_at": "now()",
        "expires_at": "now() + interval '1 month'"  # 月額の場合
    }).execute()
    
    return result
```

---

## 4. 運用

### 4.1 タイムゾーンの設定

#### 4.1.1 サーバーのタイムゾーン設定

**重要**: 利用回数の日次リセットは、日本時間（JST）の0:00に実行されます。サーバーのタイムゾーンをJSTに設定する必要があります。

**設定方法**:

```bash
# 現在のタイムゾーンを確認
timedatectl

# タイムゾーンを日本時間（JST）に変更
sudo timedatectl set-timezone Asia/Tokyo

# 変更後の確認
timedatectl
date
```

**確認**:
- `date`コマンドで、JST時刻が表示されることを確認
- ログファイルの時刻もJSTで表示されることを確認

#### 4.1.2 アプリケーションでのタイムゾーン処理

**バックエンド** (`api/utils/subscription_service.py`):

```python
from datetime import datetime
import pytz

def get_jst_date() -> str:
    """
    日本時間（JST）の現在日付を取得（YYYY-MM-DD形式）
    """
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    return now.strftime('%Y-%m-%d')

def get_jst_datetime() -> datetime:
    """
    日本時間（JST）の現在日時を取得
    """
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst)
```

**注意**: `pytz`ライブラリが必要です。`requirements.txt`に追加してください。

```bash
# requirements.txtに追加
pytz>=2024.1
```

#### 4.1.3 データベースでの日付保存

**usage_limitsテーブル**:

```sql
-- 日付はDATE型で保存（タイムゾーン情報なし）
-- バックエンドでJSTの日付を計算してから保存
INSERT INTO usage_limits (user_id, date, menu_bulk_count, menu_step_count, ocr_count)
VALUES (
    'user_id',
    '2025-01-30',  -- JSTの日付（YYYY-MM-DD形式）
    0,
    0,
    0
);
```

---

### 4.2 リセット処理のリカバリ

#### 4.2.1 リセット処理の失敗ケース

**失敗の原因**:
- データベース接続エラー
- サーバーのダウンタイム
- スクリプトの実行エラー
- タイムゾーンの設定ミス

#### 4.2.2 リカバリ処理の実装

**手動リセットスクリプト** (`scripts/reset_usage_manual.py`):

```python
#!/usr/bin/env python3
"""
手動で利用回数をリセットするスクリプト
日次リセット処理が失敗した場合に使用
"""

import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv
from supabase import create_client

# 環境変数の読み込み
load_dotenv()

def reset_usage_for_date(target_date: str = None):
    """
    指定日付の利用回数をリセット
    
    Args:
        target_date: リセット対象の日付（YYYY-MM-DD形式）
                     指定しない場合は今日の日付を使用
    """
    # JSTの日付を取得
    jst = pytz.timezone('Asia/Tokyo')
    if target_date:
        target = datetime.strptime(target_date, '%Y-%m-%d').date()
    else:
        target = datetime.now(jst).date()
    
    # Supabaseクライアントの作成
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    client = create_client(supabase_url, supabase_service_role_key)
    
    # すべてのユーザーの利用回数をリセット
    # 実装詳細は省略
    pass

if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    reset_usage_for_date(target_date)
```

**使用方法**:

```bash
# 今日の日付をリセット
python scripts/reset_usage_manual.py

# 指定日付をリセット
python scripts/reset_usage_manual.py 2025-01-30
```

#### 4.2.3 リセット処理の監視

**ログの確認**:

```bash
# 日次リセット処理のログを確認
tail -f /opt/morizo/Morizo-aiv2/logs/daily_reset.log

# エラーログの確認
grep ERROR /opt/morizo/Morizo-aiv2/logs/daily_reset.log
```

**アラート設定**:
- リセット処理が失敗した場合にアラートを送信
- メール通知やSlack通知を設定

---

### 4.3 ログの記録

#### 4.3.1 利用回数制限のログ

**ログに記録する情報**:
- ユーザーID
- 機能タイプ（menu_bulk, menu_step, ocr）
- 現在の利用回数
- 制限値
- プランタイプ
- 制限超過の有無

**実装例** (`api/middleware/usage_limit.py`):

```python
import logging
from typing import Dict, Any

logger = logging.getLogger("api.usage_limit")

async def check_usage_limit(
    user_id: str,
    feature_type: str,
    plan_type: str
) -> Dict[str, Any]:
    """
    利用回数制限をチェック
    
    Returns:
        {
            "allowed": bool,
            "current_count": int,
            "limit": int,
            "reset_at": str
        }
    """
    # 実装詳細は省略
    
    # ログ記録
    logger.info(
        f"Usage check - user_id: {user_id}, "
        f"feature: {feature_type}, "
        f"plan: {plan_type}, "
        f"current: {current_count}, "
        f"limit: {limit}, "
        f"allowed: {allowed}"
    )
    
    if not allowed:
        logger.warning(
            f"Usage limit exceeded - user_id: {user_id}, "
            f"feature: {feature_type}, "
            f"plan: {plan_type}, "
            f"current: {current_count}, "
            f"limit: {limit}"
        )
    
    return {
        "allowed": allowed,
        "current_count": current_count,
        "limit": limit,
        "reset_at": reset_at
    }
```

#### 4.3.2 購入・プラン更新のログ

**ログに記録する情報**:
- ユーザーID
- プランタイプ（変更前・変更後）
- プラットフォーム（ios, android）
- 商品ID
- レシート検証結果
- エラー情報（エラー発生時）

**実装例** (`api/routes/subscription.py`):

```python
import logging

logger = logging.getLogger("api.subscription")

@router.post("/subscription/update")
async def update_subscription(request: SubscriptionUpdateRequest, http_request: Request):
    """
    サブスクリプション更新
    """
    user_id, client = await get_authenticated_user_and_client(http_request)
    
    # 現在のプラン情報を取得
    current_plan = await get_user_plan(user_id)
    
    # プラン更新処理
    # 実装詳細は省略
    
    # ログ記録
    logger.info(
        f"Subscription updated - user_id: {user_id}, "
        f"old_plan: {current_plan}, "
        f"new_plan: {new_plan}, "
        f"platform: {platform}, "
        f"product_id: {product_id}"
    )
    
    return {"success": True, "plan": new_plan}
```

#### 4.3.3 ログファイルの管理

**ログファイルの場所**:
- `/opt/morizo/Morizo-aiv2/morizo_ai.log` - 通常ログ
- `/opt/morizo/Morizo-aiv2/morizo_ai_error.log` - エラーログ
- `/opt/morizo/Morizo-aiv2/logs/daily_reset.log` - 日次リセットログ

**ログローテーション**:
- `/etc/logrotate.d/morizo-aiv2` でログローテーションを設定
- ログファイルのサイズや保持期間を設定

**ログの確認**:

```bash
# 利用回数制限のログを確認
grep "Usage check" /opt/morizo/Morizo-aiv2/morizo_ai.log

# プラン更新のログを確認
grep "Subscription updated" /opt/morizo/Morizo-aiv2/morizo_ai.log

# エラーログを確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai_error.log
```

---

## 5. トラブルシューティング

### 5.1 よくある問題と解決方法

#### 5.1.1 レシート検証が失敗する

**原因**:
- レシートデータが不正
- ストアAPIの認証情報が間違っている
- ネットワークエラー

**解決方法**:
1. レシートデータの形式を確認
2. ストアAPIの認証情報を確認
3. ネットワーク接続を確認
4. エラーログを確認

#### 5.1.2 利用回数がリセットされない

**原因**:
- 日次リセットスクリプトが実行されていない
- タイムゾーンの設定が間違っている
- データベース接続エラー

**解決方法**:
1. cronジョブの設定を確認
2. タイムゾーンを確認（`timedatectl`）
3. 手動リセットスクリプトを実行
4. ログを確認

#### 5.1.3 プラン情報が更新されない

**原因**:
- サービスロールキーが設定されていない
- RLSポリシーの設定が間違っている
- データベース接続エラー

**解決方法**:
1. 環境変数を確認（`SUPABASE_SERVICE_ROLE_KEY`）
2. RLSポリシーを確認
3. データベース接続を確認
4. エラーログを確認

---

## 6. チェックリスト

実装前に以下の項目を確認してください：

### ストア設定
- [ ] Google Play Consoleで商品を登録
- [ ] App Store Connectで商品を登録
- [ ] 商品IDをバックエンドとモバイルアプリで統一
- [ ] テストアカウントを設定

### テスト環境
- [ ] サンドボックス環境でテスト
- [ ] レシート検証のテスト
- [ ] エラーハンドリングのテスト

### セキュリティ
- [ ] レシート検証をバックエンドで実装
- [ ] サービスロールキーを環境変数に設定
- [ ] プラットフォーム判定を実装

### 運用
- [ ] サーバーのタイムゾーンをJSTに設定
- [ ] 日次リセットスクリプトを実装
- [ ] リカバリ処理を実装
- [ ] ログ設定を確認

---

## 7. 参考資料

- [Google Play Billing Documentation](https://developer.android.com/google/play/billing)
- [App Store In-App Purchase Documentation](https://developer.apple.com/in-app-purchase/)
- [Supabase Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)
- [Python pytz Documentation](https://pythonhosted.org/pytz/)

---

**最終更新日**: 2025年1月29日

