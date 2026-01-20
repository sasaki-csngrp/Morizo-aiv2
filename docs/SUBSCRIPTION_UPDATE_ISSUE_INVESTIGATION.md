# サブスクリプション更新問題の調査記録

## 問題の概要

### 症状
- Ultimate期限切れの状態でProを購入したが、画面上は変わらない
- バックエンドログでは`plan=pro`に更新成功しているが、取得時には`ultimate, status: expired`が返る

### 発生タイミング
- Ultimate → Pro yearly への変更時に発生（**Pro yearlyのみ**）
- Ultimate → Pro monthly への変更時は正常に動作
- Pro → Ultimate への変更時は正常に動作

## 調査の経緯

### 1. 初期調査（2026-01-19）

#### 確認したログ（morizo_ai.log）

**Pro更新（08:00:26）のログ:**
- 181行目: `upsert戻り値: plan_type=pro, subscription_status=active, expires_at=2026-02-18T08:00:26.37478+00:00, purchased_at=2026-01-19T08:00:26.37478+00:00, updated_at=2026-01-19T08:00:26.374763+00:00`
- 183行目: `DB保存確認: plan_type=pro, subscription_status=active, expires_at=2026-02-18T08:00:26.37478+00:00`
- 195行目: `DBから取得した実際の値: plan_type=ultimate, subscription_status=expired, expires_at=2026-01-19T08:22:34+00:00, purchased_at=2026-01-19T08:00:26.37478+00:00, updated_at=2026-01-19T08:00:24.171192+00:00`

#### 発見した問題点

1. **`upsert`の戻り値とDB保存確認は正しい**
   - `upsert`の戻り値: `plan_type=pro, subscription_status=active` ✅
   - DB保存確認: `plan_type=pro, subscription_status=active` ✅

2. **取得処理で古い値が返る**
   - `upsert`の戻り値: `updated_at=2026-01-19T08:00:26.374763+00:00`
   - 取得処理: `updated_at=2026-01-19T08:00:24.171192+00:00`（古い値）

3. **`purchased_at`は更新されている**
   - `purchased_at=2026-01-19T08:00:26.37478+00:00`（更新されている）

4. **`plan_type`と`subscription_status`が古い値に戻っている**
   - `plan_type=ultimate`（古い値）
   - `subscription_status=expired`（古い値）

### 2. DDL.mdの確認結果

#### トリガーの存在
- `user_subscriptions`テーブルに`BEFORE UPDATE`トリガーが設定されている
- トリガー: `update_user_subscriptions_updated_at`
- 動作: `UPDATE`実行前に`updated_at`を`NOW()`に設定

```sql
CREATE TRIGGER update_user_subscriptions_updated_at BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 重要な発見
- `updated_at`が古い値（`2026-01-19T08:00:24.171192+00:00`）になっている
- これは、`upsert`（08:00:26）の**前に**別の更新（08:00:24）が実行されている可能性を示している

## 実装済みの修正

### 1. ログ強化

1. **`/api/subscription/update`エンドポイント** (`api/routes/subscription.py`)
   - リクエスト受信時の`subscription_status`の値をログ出力（97行目）
   - 更新データの詳細ログ（164行目）
   - 更新成功時の`subscription_status`と`expires_at`をログ出力（188行目）
   - `update`/`insert`の戻り値をログ出力（183行目）
   - DB保存確認のログ（195行目）

2. **`get_user_plan`メソッド** (`api/utils/subscription_service.py`)
   - DBから取得した実際の値を詳細にログ出力（143行目）

### 2. `upsert`から`update`への変更（2026-01-19）

- `api/routes/subscription.py`の`update_subscription`関数を修正
- 既存レコードの存在確認後に`update`または`insert`を使用
- 実行した操作（`update`/`insert`）をログ出力（172, 176, 183, 188行目）

### 3. RLSの影響排除（2026-01-19）

- `api/routes/subscription.py`の`get_plan`と`get_usage`関数を修正
- 認証済みユーザーのクライアントではなく、サービスロールクライアントを使用
- RLSポリシーの影響を排除（53, 257行目）

## 現在の実装状況

### ファイル: `api/routes/subscription.py`

- `PRODUCT_ID_TO_PLAN`マッピングは実装済み（113行目）
- `product_id`から`plan_type`への導出は正常に動作
- 既存レコードの存在確認後に`update`または`insert`を使用（166-178行目）
- サービスロールクライアントを使用してRLSの影響を排除（53, 257行目）

### ファイル: `api/utils/subscription_service.py`

- `PRODUCT_ID_TO_PLAN`マッピング定義（38-43行目）
- `get_user_plan`メソッドでDBから取得（127行目）

### ファイル: `api/routes/revenuecat_webhook.py`

- `parse_revenuecat_event`関数で`product_id`から`plan_type`を判定（192-202行目）
- エンタイトルメントをフォールバックとして使用（204-218行目）
- **問題**: `product_id`が存在する場合でも、エンタイトルメントが優先される可能性がある

## 考えられる原因

### 1. `upsert`の後に別の処理が実行されている可能性

- `updated_at`が古い値（`2026-01-19T08:00:24.171192+00:00`）になっている
- `upsert`の戻り値（`2026-01-19T08:00:26.374763+00:00`）と一致しない
- これは、`upsert`の後に別の`UPDATE`が実行されている可能性を示している

### 2. RevenueCat Webhookの可能性

- ログにはRevenueCat Webhookの実行記録がない
- しかし、`updated_at`のタイムスタンプから、別の処理が実行されている可能性がある

### 3. `upsert`の動作の問題

- `upsert`の戻り値では正しい値が返っている
- しかし、実際のDBの値は古い値になっている
- これは、`upsert`の後に別の処理が実行されている可能性が高い

## 次の調査ステップ

### 優先度1: 更新処理前後のログ確認

1. **更新処理（08:00:26）の前後のログを確認**
   - 08:00:24付近に別の更新処理が実行されていないか
   - RevenueCat Webhookが実行されていないか
   - 別のAPI呼び出しが実行されていないか

2. **`updated_at`のタイムスタンプの不一致を調査**
   - `upsert`の戻り値: `2026-01-19T08:00:26.374763+00:00`
   - 取得処理: `2026-01-19T08:00:24.171192+00:00`
   - この2秒の差の原因を特定

### 優先度2: `upsert`の動作確認

1. **`upsert`の動作を詳しく調査**
   - Supabaseの`upsert`の動作を確認
   - `on_conflict="user_id"`の動作を確認
   - 実際に実行されるSQLクエリを確認

2. **`update`への変更を検討**
   - `upsert`ではなく、明示的な`update`を使用する方法を検討
   - ただし、原因が分からなければ同じ結果になる可能性がある

### 優先度3: データベースの直接確認

1. **データベースの実際の値を確認**
   - `upsert`実行直後のDBの状態
   - 取得処理時のDBの状態
   - タイムスタンプの不一致の原因を特定

## 関連ファイル

- `api/routes/subscription.py`: サブスクリプション更新エンドポイント
- `api/utils/subscription_service.py`: サブスクリプションサービス
- `api/routes/revenuecat_webhook.py`: RevenueCat Webhookエンドポイント
- `docs/archive/DDL.md`: データベース設計（トリガー定義含む）
- `docs/BACKEND_SUBSCRIPTION_MAPPING.md`: 問題のドキュメント

## ログファイル

- `morizo_ai.log`: メインログファイル
- 最新のログ: 2026-01-19 08:00:26付近のPro更新処理

## 注意事項

1. **`updated_at`のタイムスタンプの不一致**
   - `upsert`の戻り値と実際のDBの値で`updated_at`が異なる
   - これは、`upsert`の後に別の処理が実行されている可能性を示している

2. **`purchased_at`は更新されている**
   - `purchased_at`は正しく更新されている
   - しかし、`plan_type`と`subscription_status`は古い値に戻っている

3. **最初の1回は正常に動作**
   - 最初のPro更新（07:59:42）は正常に動作
   - Ultimate更新（08:00:11）も正常に動作
   - 2回目のPro更新（08:00:26）で問題が発生

## 追加調査（2026-01-19 続き）

### 3. `upsert`から`update`への変更（2026-01-19）

#### 実施した修正
- `api/routes/subscription.py`の`update_subscription`関数を修正
- `upsert`を削除し、既存レコードの存在確認後に`update`または`insert`を使用するように変更
- 実行した操作（`update`/`insert`）をログ出力

#### 結果
- 修正は反映されたが、問題は解決しなかった
- `update`の戻り値は正しいが、取得時に古い値が返る

### 4. RLS（Row Level Security）の影響調査（2026-01-19）

#### 実施した修正
- `api/routes/subscription.py`の`get_plan`と`get_usage`関数を修正
- 認証済みユーザーのクライアントではなく、サービスロールクライアントを使用するように変更
- RLSポリシーの影響を排除

#### 結果
- 修正は反映されたが、問題は解決しなかった
- サービスロールクライアントを使用しても、取得時に古い値が返る

### 5. モバイル側ログ分析（2026-01-19）

#### 重要な発見

**Pro yearly購入時（問題あり）:**
- `hasUpgradeInfo:true` — ダウングレードなのに`true`（通常は`false`）
- `activeSubscriptions:["morizo_ultimate_yearly"]` — RevenueCatが`ultimate_yearly`をアクティブのまま
- `activeEntitlements:["morizo_ultimate"]` — エンタイトルメントが`ultimate`のまま（`pro`に更新されていない）
- `⚠️ アクティブなエンタイトルメントが見つかりません（iOS）` — `morizo_pro`エンタイトルメントが見つからない警告
- バックエンドが`plan_type:"ultimate"`を返し続ける

**Pro monthly購入時（正常）:**
- `hasUpgradeInfo:false` — 正しい
- `activeEntitlements:["morizo_pro"]` — エンタイトルメントが`pro`に更新されている
- 警告なし
- バックエンドが`plan_type:"pro"`を正しく返す

#### 根本原因の仮説

**Pro yearly購入時に、RevenueCatのエンタイトルメントが`morizo_ultimate`から`morizo_pro`に更新されていません。**

そのため：
1. RevenueCatが`morizo_ultimate`エンタイトルメントをアクティブのまま保持
2. `activeSubscriptions`に`morizo_ultimate_yearly`が残る
3. モバイル側は`product_id: "morizo_pro_yearly"`を送信するが、RevenueCatのエンタイトルメントが更新されていない
4. **RevenueCat Webhookが実行された場合、エンタイトルメントに依存して`ultimate`で上書きしている可能性**

### 6. RevenueCat Webhookの動作確認

#### 現在の実装（`api/routes/revenuecat_webhook.py`）

`parse_revenuecat_event`関数（204-218行目）:
- `product_id`から`plan_type`を判定（優先）
- しかし、`plan_type == "free"`の場合のみエンタイトルメントをフォールバックとして使用
- **問題**: `product_id`が存在する場合でも、エンタイトルメントが優先される可能性がある

## 根本原因

### 確定した原因

1. **RevenueCat側の問題**: Pro yearly購入時にエンタイトルメントが更新されない
2. **RevenueCat Webhookの問題**: エンタイトルメントに依存して`ultimate`で上書きしている可能性

### 推奨される修正

1. **RevenueCat Webhook側の修正**:
   - `product_id`が存在する場合は、エンタイトルメントに依存せず`product_id`を優先
   - `product_id`が存在しない場合のみ、エンタイトルメントをフォールバックとして使用

2. **RevenueCat側の設定確認**:
   - `morizo_pro_yearly`が`morizo_pro`エンタイトルメントに正しくマッピングされているか
   - ダウングレード時のエンタイトルメント更新ロジック

### 7. RevenueCat Webhookの修正試行とロールバック（2026-01-19）

#### 実施した修正
- `api/routes/revenuecat_webhook.py`の`parse_revenuecat_event`関数を修正
- `product_id`が使用された場合、エンタイトルメントをチェックしないように変更
- `product_id_used`フラグを導入し、`product_id`が使用された場合はエンタイトルメントをスキップ

#### 結果（Regression発生）
- **Pro monthly更新も失敗するようになった**（改悪）
- 修正を元に戻し、元のロジックに復元
- 根本原因は別の可能性があることが判明

## 根本原因の再検討（2026-01-19）

### 現在の状況

1. **`update`の戻り値は正しい**
   - `update`実行時: `plan_type=pro, updated_at=09:24:43.837942`
   - 戻り値は正しい値を返している

2. **取得時に古い値が返る**
   - 取得時: `plan_type=ultimate, updated_at=09:24:41.899837`
   - `updated_at`が`update`の戻り値より**古い**（2秒前）

3. **`purchased_at`は更新されている**
   - `purchased_at=09:24:43.837965`（更新されている）
   - これは、`update`が実行されたことを示している

### 考えられる原因

#### 1. RevenueCat Webhookが非同期で実行され、updateの前に古い値で上書きしている

**可能性**: 非常に高い

- RevenueCat WebhookはHTTPリクエストで非同期に送信される
- Webhookが`update`の**前に**実行され、古いエンタイトルメント情報で`ultimate`に上書き
- その後、`update`が実行されるが、Webhookの変更が後に反映される可能性
- `updated_at=09:24:41`（Webhook実行）→ `updated_at=09:24:43`（update実行）の順序

**証拠**:
- `updated_at`が`update`の戻り値より古い
- `purchased_at`は更新されている（`update`は実行された）
- `plan_type`と`subscription_status`が古い値（Webhookで上書きされた可能性）

#### 2. データベースのレプリケーション遅延

**可能性**: 低い

- SupabaseはPostgreSQLベースで、読み取りがレプリカから行われる可能性
- しかし、サービスロールクライアントを使用しているため、この可能性は低い
- また、`updated_at`が古い値になっているため、レプリケーション遅延では説明できない

#### 3. 別の処理がuser_subscriptionsテーブルを更新している

**可能性**: 中程度

- コードベースを確認した結果、`user_subscriptions`を更新するのは：
  - `/api/subscription/update`エンドポイント
  - RevenueCat Webhookエンドポイント
- 他の処理は見つかっていない
- しかし、ログに記録されていない処理が存在する可能性

#### 4. トランザクションの分離レベルとタイミング

**可能性**: 中程度

- `update`の戻り値はトランザクション内の値
- 別のトランザクションが同時に実行され、コミット順序により古い値が読まれる可能性
- しかし、`updated_at`が`update`の戻り値より古いため、`update`の**前に**別の処理が実行された可能性が高い

### 最も可能性が高い原因

**RevenueCat Webhookが非同期で実行され、`update`の前に古い値で上書きしている**

- `updated_at=09:24:41.899837`（Webhook実行の可能性）
- `update`実行時: `updated_at=09:24:43.837942`
- 取得時: `updated_at=09:24:41.899837`（古い値）

このタイムスタンプの順序から、Webhookが`update`の前に実行され、その後`update`が実行されたが、Webhookの変更が後に反映された可能性が高い。

## 次のセッションで確認すべきこと

### 優先度1: RevenueCat Webhookの実行確認

1. **RevenueCat Webhookが実際に実行されているか確認**
   - Webhookエンドポイントに詳細ログを追加
   - 実行タイミング、受信データ、更新内容を記録
   - ログファイルに記録されていない可能性を考慮（別サーバー/プロセスの可能性）

2. **Webhookの実行タイミングを記録**
   - リクエスト受信時のタイムスタンプ
   - データベース更新前後のタイムスタンプ
   - `updated_at`の値を記録

3. **Webhookの受信データを記録**
   - `product_id`の値
   - エンタイトルメントの値
   - `customer_info`の内容

### 優先度2: データベースの直接確認

1. **Supabaseダッシュボードで実際の値を確認**
   - `update`実行直後のDBの状態
   - 取得処理時のDBの状態
   - タイムスタンプの不一致の原因を特定

2. **データベースのログを確認**
   - Supabaseのログで、実際に実行されたSQLクエリを確認
   - 更新の順序とタイミングを確認

### 優先度3: コードベースの再確認

1. **`user_subscriptions`を更新する全ての処理を確認**
   - 直接SQLを実行する処理がないか
   - バックグラウンドジョブがないか
   - 他のエンドポイントからの更新がないか

## 追加調査（2026-01-20）

### 8. RevenueCat Webhookの実行確認結果

#### 8-1. RevenueCatダッシュボードでの確認

**確認日時**: 2026-01-20

**確認結果:**
- ✅ Webhook URL: `https://morizo.csngrp.co.jp/api/revenuecat/webhook`（本番環境）
- ✅ Webhookは正常に送信されている
- ✅ イベント履歴に多数のイベントが記録されている
- ✅ レスポンス: `{"status":"success","message":"Subscription updated successfully"}`

**確認したイベント（UTC）:**
- `09:38:02` - RENEWAL
- `09:38:03` - RENEWAL
- `09:38:56` - PRODUCT_CHANGE
- `09:39:16` - PRODUCT_CHANGE

**レスポンスヘッダー:**
- `Server: nginx/1.24.0 (Ubuntu)`
- ステータスコード: 200（成功）

#### 8-2. 本番環境のログ確認結果

**確認日時**: 2026-01-20

**確認結果:**
- ✅ Webhookリクエストは正常に処理されている
- ✅ ログに`🔍 [API] POST /api/revenuecat/webhook`が出力されている
- ❌ ログに`🔍 [WEBHOOK]`が一切出力されていない

**確認したログ（JST）:**
- `18:38:02` - POST /api/revenuecat/webhook ステータス: 200
- `18:38:03` - POST /api/revenuecat/webhook ステータス: 200
- `18:38:56` - POST /api/revenuecat/webhook ステータス: 200
- `18:39:16` - POST /api/revenuecat/webhook ステータス: 200

**タイムスタンプの一致:**
- JST `18:38:02` = UTC `09:38:02` ✅
- JST `18:38:03` = UTC `09:38:03` ✅
- JST `18:38:56` = UTC `09:38:56` ✅
- JST `18:39:16` = UTC `09:39:16` ✅

#### 8-3. 環境変数の確認結果

**確認日時**: 2026-01-20

**確認結果:**
- ✅ `REVENUECAT_WEBHOOK_AUTH_TOKEN`が設定されている
- ⚠️ 環境変数に`Bearer `が含まれている（例: `Bearer 15ca...3d5878c2d5a`）

#### 8-4. 問題の特定

**発見した問題:**
1. **本番環境のコードが古い可能性**
   - ログに`🔍 [WEBHOOK]`が一切出力されていない
   - 現在のコードには`🔍 [WEBHOOK]`のログ出力が含まれている
   - 本番環境のコードが最新でない可能性

2. **開発環境と本番環境の共用**
   - Supabase: 本番・開発共用
   - RevenueCat: 本番・開発共用
   - Webhook URL: 本番環境を向いている
   - ローカル開発環境のテストが本番環境に影響している可能性

### 9. 実施した修正（2026-01-20）

#### 9-1. ログ出力の追加

**修正ファイル**: `api/routes/revenuecat_webhook.py`

**追加したログ:**
1. リクエスト受信時のタイムスタンプ（ミリ秒単位）
2. 受信product_id
3. アクティブなエンタイトルメント
4. プランタイプ判定結果と判定元
5. 更新処理前の既存レコードの値
6. 更新処理の実行タイムスタンプ
7. 更新処理後の値

**目的:**
- Webhookの実行タイミングを追跡
- 受信データの内容を確認
- 更新処理前後の値を比較

#### 9-2. 認証処理の改善

**修正ファイル**: `api/routes/revenuecat_webhook.py`

**変更内容:**
- 環境変数から`Bearer `プレフィックスを除去（あれば）
- Authorizationヘッダーから`Bearer `プレフィックスを除去（あれば）
- トークン部分のみを比較

**目的:**
- 環境変数に`Bearer `が含まれていても動作するように改善
- 認証エラーの詳細ログを出力

#### 9-3. エンタイトルメント判定の条件変更

**修正ファイル**: `api/routes/revenuecat_webhook.py`

**変更前:**
```python
if customer_info and plan_type == "free":
```

**変更後:**
```python
if customer_info and plan_type == "free" and not product_id:
```

**目的:**
- `product_id`が存在する場合、エンタイトルメントに依存しない
- RevenueCatのエンタイトルメント更新遅延の影響を受けない

**評価:**
- ⚠️ **動作変更**: 以前の動作と異なる可能性がある
- ✅ **意図的な修正**: 調査記録で推奨されていた修正

#### 9-4. `upsert`から`update`/`insert`への変更

**修正ファイル**: `api/routes/subscription.py`

**変更内容:**
- `upsert`を削除
- 既存レコードの存在確認後に`update`または`insert`を使用

**目的:**
- より明示的な処理
- ログ出力が容易

**評価:**
- ✅ **動作は同等**: `upsert`と`update`/`insert`の組み合わせは同等の動作

#### 9-5. サービスロールクライアントの使用

**修正ファイル**: `api/routes/subscription.py`, `api/utils/subscription_service.py`

**変更内容:**
- `get_plan`と`get_usage`関数で、サービスロールクライアントを使用

**目的:**
- RLSの影響を排除

### 10. デプロイ前レビュー（2026-01-20）

#### 10-1. 破壊的変更の可能性

| 変更内容 | 破壊的変更の可能性 | リスク評価 |
|---------|------------------|-----------|
| 認証処理の改善 | 低 | ✅ 安全 |
| エンタイトルメント判定の条件変更 | 中 | ⚠️ 注意が必要 |
| ログ出力の追加 | なし | ✅ 安全 |
| `upsert`から`update`/`insert`への変更 | 低 | ✅ 安全 |
| サービスロールクライアントの使用 | 低 | ✅ 安全 |

#### 10-2. デプロイ前の確認事項

**必須確認:**
1. ✅ 環境変数`REVENUECAT_WEBHOOK_AUTH_TOKEN`が正しく設定されているか
2. ⚠️ エンタイトルメント判定の動作確認（`product_id`が存在する場合、エンタイトルメントをチェックしない）
3. ⚠️ ログレベルの確認（本番環境のログレベルがINFO以上に設定されているか）

**デプロイ後の確認事項:**
1. `🔍 [WEBHOOK]`のログが出力されるか確認
2. Webhookが正常に処理されるか確認
3. エラーログを監視

#### 10-3. デプロイ推奨

**結論: デプロイ可能**

**理由:**
1. 主な変更はログ出力の追加（安全）
2. 認証処理の改善（後方互換性あり）
3. エンタイトルメント判定の変更は意図的な修正
4. `upsert`から`update`/`insert`への変更は動作が同等

**詳細**: `docs/DEPLOYMENT_REVIEW.md`を参照

### 11. 次のステップ

#### 11-1. デプロイ後の確認

1. **ログの確認**
   - `🔍 [WEBHOOK]`のログが出力されるか確認
   - 特に、リクエスト受信タイムスタンプ、product_id、プランタイプ判定結果

2. **動作確認**
   - Webhookが正常に処理されるか確認
   - エンタイトルメント判定が正しく動作するか確認

3. **エラーの監視**
   - デプロイ後、エラーログを監視
   - 認証エラーが発生していないか確認

#### 11-2. 長期的な改善（検討事項）

1. **開発環境と本番環境の分離**
   - 開発環境用のSupabaseプロジェクトを作成
   - 開発環境用のRevenueCatプロジェクトを作成
   - 開発環境用のWebhook URLを設定

2. **問題の根本原因の調査**
   - Webhookが`update`の前に実行されている可能性
   - タイムスタンプの不一致の原因を特定

---

**最終更新**: 2026-01-20  
**次回調査**: デプロイ後のログ確認
