# 収益化機能実装プラン

## 概要

モバイルアプリ（Android/iOS）のストア登録完了後、サブスクリプション（定期購入）をベースとした収益化機能を実装します。

**作成日**: 2025年1月29日  
**バージョン**: 1.0  
**対象**: Morizo-aiv2（バックエンド）、Morizo-mobile（モバイルアプリ）

---

## 1. 基本方針

### 1.1 収益化モデル

- **ベース**: 各ストア（Google Play / App Store）での定期購入（サブスクリプション）
- **プラン体系**: 3段階のプラン制
  - **free**: 無料プラン（基本機能のみ）
  - **PRO**: 有料プラン（中級機能）
  - **ULTIMATE**: 有料プラン（全機能）

### 1.2 機能制限の仕組み

プランごとに、**1日あたりの利用回数**で機能を制限します。

| 機能 | free | PRO | ULTIMATE |
|------|------|-----|----------|
| 献立一括提案 | 1回/日 | 10回/日 | 100回/日 |
| 段階的提案 | 3回/日 | 30回/日 | 300回/日 |
| OCR読み取り | 1回/日 | 10回/日 | 100回/日 |

### 1.3 日次リセット

- **リセット時刻**: 日本時間（JST）の0:00
- **リセット対象**: すべての利用回数カウンター

---

## 2. 実装可能性の評価

### 2.1 現状確認結果

#### ✅ 実装済み機能

- **認証システム**: Supabase Authによる認証が実装済み
- **献立一括提案機能**: `generate_menu_plan` が実装済み
- **段階的提案機能**: `generate_proposals` が実装済み
- **OCR読み取り機能**: `ocr_receipt` が実装済み

#### ❌ 未実装機能

- **サブスクリプション/プラン管理機能**: 未実装
- **利用回数制限機能**: 未実装
- **モバイルアプリのIAP連携**: 未実装

### 2.2 結論

**実装可能です**。既存の機能基盤が整っているため、プラン管理と利用回数制限機能を追加することで実現できます。

---

## 3. 実装フェーズ

### フェーズ1: データベーススキーマの拡張

#### 3.1.1 対象

Supabaseデータベース（新しいテーブル作成）

#### 3.1.2 実装内容

**1. `user_subscriptions`テーブルの作成**

```sql
CREATE TABLE user_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    plan_type VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (plan_type IN ('free', 'pro', 'ultimate')),
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (subscription_status IN ('active', 'expired', 'cancelled')),
    subscription_id VARCHAR(255), -- ストアのサブスクリプションID
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android')), -- 'ios' or 'android'
    purchased_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(subscription_status);

-- RLS設定
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own subscription" ON user_subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own subscription" ON user_subscriptions
    FOR UPDATE USING (auth.uid() = user_id);

-- サービスロール用ポリシー（バックエンドから更新可能にする）
CREATE POLICY "Service role can manage subscriptions" ON user_subscriptions
    FOR ALL USING (auth.role() = 'service_role');
```

**2. `usage_limits`テーブルの作成**

```sql
CREATE TABLE usage_limits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    date DATE NOT NULL, -- 日本時間の日付（YYYY-MM-DD形式）
    menu_bulk_count INTEGER NOT NULL DEFAULT 0, -- 献立一括提案の利用回数
    menu_step_count INTEGER NOT NULL DEFAULT 0, -- 段階的提案の利用回数
    ocr_count INTEGER NOT NULL DEFAULT 0, -- OCR読み取りの利用回数
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date) -- 1ユーザー1日1レコード
);

-- インデックス
CREATE INDEX idx_usage_limits_user_id ON usage_limits(user_id);
CREATE INDEX idx_usage_limits_date ON usage_limits(date);
CREATE INDEX idx_usage_limits_user_date ON usage_limits(user_id, date);

-- RLS設定
ALTER TABLE usage_limits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own usage" ON usage_limits
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own usage" ON usage_limits
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own usage" ON usage_limits
    FOR UPDATE USING (auth.uid() = user_id);

-- サービスロール用ポリシー
CREATE POLICY "Service role can manage usage" ON usage_limits
    FOR ALL USING (auth.role() = 'service_role');
```

#### 3.1.3 修正の理由

ユーザーのプラン情報と日次利用回数を管理するため

#### 3.1.4 修正の影響

- 新規テーブル追加のみで、既存機能への影響なし
- 既存のテーブル構造は変更しない

---

### フェーズ2: バックエンドAPIの実装

#### 3.2.1 対象ファイル

- `api/routes/subscription.py` (新規作成)
- `api/middleware/usage_limit.py` (新規作成)
- `api/utils/subscription_service.py` (新規作成)
- `api/routes/inventory.py` (OCRエンドポイントに制限チェック追加)
- `api/routes/chat.py` (献立提案エンドポイントに制限チェック追加)
- `main.py` (新しいルーターとミドルウェアの登録)

#### 3.2.2 実装内容

**1. プラン管理API** (`api/routes/subscription.py`)

```python
# エンドポイント例
GET /api/subscription/plan - 現在のプラン情報取得
POST /api/subscription/update - プラン更新（モバイルアプリから呼び出し）
GET /api/subscription/usage - 本日の利用回数取得
```

**2. 利用回数制限サービス** (`api/utils/subscription_service.py`)

- プラン情報の取得
- 利用回数制限のチェック
- 利用回数のインクリメント
- 日次リセット処理

**3. 利用回数制限ミドルウェア** (`api/middleware/usage_limit.py`)

- 各機能呼び出し前にプランと利用回数をチェック
- 制限超過時は403エラーを返す
- 機能タイプ（menu_bulk, menu_step, ocr）を判定

**4. 既存エンドポイントへの制限チェック追加**

- **OCRエンドポイント**: `POST /api/inventory/ocr-receipt`
  - 呼び出し前にOCR利用回数をチェック
  - 成功時に利用回数をインクリメント

- **献立一括提案**: チャットエンドポイント内で`generate_menu_plan`呼び出し時
  - 呼び出し前に献立一括提案利用回数をチェック
  - 成功時に利用回数をインクリメント

- **段階的提案**: チャットエンドポイント内で`generate_proposals`呼び出し時
  - 呼び出し前に段階的提案利用回数をチェック
  - 成功時に利用回数をインクリメント

#### 3.2.3 修正の理由

プランに応じた利用回数制限を実装するため

#### 3.2.4 修正の影響

- 既存エンドポイントに制限チェックが追加される
- 制限超過時はエラーレスポンス（403 Forbidden）が返る
- エラーレスポンスには、制限内容とリセット時刻を含める

---

### フェーズ3: モバイルアプリのIAP連携

#### 3.3.1 対象ファイル

- `/app/Morizo-mobile/package.json` (IAPライブラリ追加)
- `/app/Morizo-mobile/api/subscription-api.ts` (新規作成)
- `/app/Morizo-mobile/screens/SubscriptionScreen.tsx` (新規作成)
- `/app/Morizo-mobile/components/PlanCard.tsx` (新規作成)

#### 3.3.2 実装内容

**1. IAPライブラリの導入**

```json
{
  "dependencies": {
    "react-native-purchases": "^7.0.0" // または expo-in-app-purchases
  }
}
```

**2. サブスクリプション管理機能**

- プラン購入画面の実装
- 購入処理の実装（ストア連携）
- 購入状態のバックエンド同期（`POST /api/subscription/update`）

**3. プラン表示機能**

- 現在のプラン表示
- 利用回数の表示（`GET /api/subscription/usage`）
- プランアップグレード画面
- 制限超過時の警告表示

#### 3.3.3 修正の理由

ストアでのサブスクリプション購入を実装するため

#### 3.3.4 修正の影響

- 新規機能追加のみで、既存機能への影響なし
- ストア設定（Google Play Console / App Store Connect）での商品登録が必要

---

### フェーズ4: 日次リセット機能の実装

#### 3.4.1 対象ファイル

- `scripts/daily_reset.py` (新規作成)
- スケジューラー設定（cron等）

#### 3.4.2 実装内容

**1. 日次リセットスクリプト**

- 日本時間0:00に実行
- 前日の利用回数レコードをリセット（または新規作成）
- ログ出力

**2. スケジューラー設定**

- cronジョブまたはsystemd timerで定期実行
- 日本時間（JST）での実行を保証

#### 3.4.3 修正の理由

日次で利用回数をリセットするため

#### 3.4.4 修正の影響

- バックグラウンド処理のみで、既存機能への影響なし
- サーバーのタイムゾーン設定が必要（JST）

---

## 4. 実装の優先順位

1. **フェーズ1** → データベーススキーマ拡張（基盤）
2. **フェーズ2** → バックエンドAPI実装（制限機能）
3. **フェーズ3** → モバイルアプリIAP連携（購入機能）
4. **フェーズ4** → 日次リセット機能（運用機能）

---

## 5. 技術的な詳細

### 5.1 プラン制限の定義

```python
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
```

### 5.2 日付の扱い

- **データベース**: `usage_limits.date`はDATE型で、日本時間（JST）の日付を保存
- **日付取得**: バックエンドで日本時間の現在日付を取得して使用
- **リセット時刻**: 日本時間0:00（UTC+9）

### 5.3 エラーレスポンス形式

制限超過時のエラーレスポンス例：

```json
{
  "detail": "利用回数制限に達しました",
  "error_code": "USAGE_LIMIT_EXCEEDED",
  "feature": "ocr",
  "current_count": 1,
  "limit": 1,
  "plan": "free",
  "reset_at": "2025-01-30T00:00:00+09:00"
}
```

---

## 6. 注意事項

### 6.1 ストア設定

- **Google Play Console**: サブスクリプション商品の事前登録が必要
- **App Store Connect**: サブスクリプション商品の事前登録が必要
- **商品ID**: プランタイプ（pro, ultimate）に対応する商品IDを設定

### 6.2 テスト環境

- **サンドボックス環境**: ストアのサンドボックス環境でのテストが必要
- **レシート検証**: ストアからのレシート検証処理が必要（セキュリティのため）

### 6.3 セキュリティ

- **レシート検証**: モバイルアプリから送信される購入レシートをバックエンドで検証
- **プラットフォーム判定**: iOS/Androidのレシート検証方法が異なるため、適切に処理
- **サービスロールキー**: データベース更新にはサービスロールキーを使用

### 6.4 運用

- **タイムゾーン**: サーバーのタイムゾーンをJSTに設定
- **リセット処理**: 日次リセット処理の失敗時のリカバリ処理を検討
- **ログ**: 利用回数制限のログを適切に記録

---

## 7. 実装チェックリスト

### フェーズ1: データベース
- [ ] `user_subscriptions`テーブル作成
- [ ] `usage_limits`テーブル作成
- [ ] インデックス作成
- [ ] RLS設定
- [ ] マイグレーションスクリプト作成

### フェーズ2: バックエンド
- [ ] `subscription_service.py`実装
- [ ] `subscription.py`ルーター実装
- [ ] `usage_limit.py`ミドルウェア実装
- [ ] OCRエンドポイントに制限チェック追加
- [ ] チャットエンドポイントに制限チェック追加
- [ ] エラーレスポンス形式の統一
- [ ] 単体テスト作成

### フェーズ3: モバイルアプリ
- [ ] IAPライブラリ導入
- [ ] 購入画面実装
- [ ] プラン表示画面実装
- [ ] バックエンドAPI連携
- [ ] レシート検証処理
- [ ] エラーハンドリング

### フェーズ4: 運用
- [ ] 日次リセットスクリプト作成
- [ ] スケジューラー設定
- [ ] ログ設定
- [ ] 監視設定

---

## 8. 参考資料

- [Supabase Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)
- [Google Play Billing](https://developer.android.com/google/play/billing)
- [App Store In-App Purchase](https://developer.apple.com/in-app-purchase/)
- [React Native Purchases](https://www.revenuecat.com/docs/react-native)

---

## 9. 承認待ち

このプランに基づいて実装を進める場合は、以下の承認が必要です：

1. ⏳ **実装プランの承認**
2. ⏳ **データベーススキーマ変更の承認**
3. ⏳ **API仕様の承認**
4. ⏳ **モバイルアプリUI/UXの承認**

承認後、フェーズ1から順に実装を開始します。

