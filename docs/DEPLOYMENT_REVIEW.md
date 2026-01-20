# デプロイ前レビュー：Webhook修正

## 変更概要

最終コミット以降の変更内容を確認し、破壊的変更の可能性を評価します。

## 変更ファイル

1. `api/routes/revenuecat_webhook.py` - 114行追加
2. `api/routes/subscription.py` - 66行追加
3. `api/utils/subscription_service.py` - 2行追加

## 変更内容の詳細

### 1. `api/routes/revenuecat_webhook.py`

#### 1-1. 認証処理の改善（破壊的変更の可能性：**低**）

**変更前:**
```python
expected_token = WEBHOOK_AUTH_TOKEN
if authorization != expected_token:
    logger.warning(f"認証トークンが一致しません: {authorization[:20]}...")
    return False
```

**変更後:**
```python
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
```

**評価:**
- ✅ **改善**: 環境変数に`Bearer `が含まれていても動作する
- ✅ **後方互換性**: 以前の動作も維持される
- ⚠️ **注意**: 環境変数に`Bearer `が含まれている場合、以前は認証失敗していたが、今は成功する可能性がある

**リスク: 低** - 認証の改善であり、既存の動作を壊す可能性は低い

---

#### 1-2. エンタイトルメント判定の条件変更（破壊的変更の可能性：**中**）

**変更前:**
```python
# customer_infoからエンタイトルメントを判定（フォールバック）
if customer_info and plan_type == "free":
    entitlements = customer_info.get("entitlements", {})
    # ...
```

**変更後:**
```python
# customer_infoからエンタイトルメントを判定（フォールバック）
# product_idが存在しない場合のみ、エンタイトルメントをチェック
# これにより、RevenueCatのエンタイトルメント更新遅延の影響を受けない
if customer_info and plan_type == "free" and not product_id:
    entitlements = customer_info.get("entitlements", {})
    # ...
```

**評価:**
- ⚠️ **動作変更**: `product_id`が存在する場合、エンタイトルメントをチェックしない
- ✅ **意図的な修正**: 調査記録で推奨されていた修正
- ⚠️ **注意**: 以前は`product_id`が存在してもエンタイトルメントをチェックしていた可能性がある

**リスク: 中** - 動作が変更されるが、これは意図的な修正

**影響範囲:**
- `product_id`が存在する場合、エンタイトルメントに依存しない
- これにより、RevenueCatのエンタイトルメント更新遅延の影響を受けない

---

#### 1-3. ログ出力の追加（破壊的変更の可能性：**なし**）

**追加されたログ:**
- リクエスト受信タイムスタンプ
- 受信product_id
- アクティブなエンタイトルメント
- プランタイプ判定結果
- 更新処理前後の値

**評価:**
- ✅ **安全**: ログ出力のみで、処理ロジックに影響なし

---

#### 1-4. `update_subscription_status`関数の変更（破壊的変更の可能性：**低**）

**変更内容:**
- ログ出力の追加
- `client`パラメータを明示的に渡すように変更

**評価:**
- ✅ **安全**: ログ出力のみで、処理ロジックに影響なし
- ✅ **改善**: `client`を明示的に渡すことで、処理が明確になる

---

### 2. `api/routes/subscription.py`

#### 2-1. `upsert`から`update`/`insert`への変更（破壊的変更の可能性：**低**）

**変更前:**
```python
result = client.table("user_subscriptions").upsert(
    update_data,
    on_conflict="user_id"
).execute()
```

**変更後:**
```python
# 既存レコードの存在確認
existing_result = client.table("user_subscriptions").select("user_id").eq("user_id", user_id).execute()
is_existing = existing_result.data and len(existing_result.data) > 0

# 既存レコードがある場合はupdate、ない場合はinsertを使用
if is_existing:
    result = client.table("user_subscriptions").update(update_data).eq("user_id", user_id).execute()
    operation = "update"
else:
    result = client.table("user_subscriptions").insert(update_data).execute()
    operation = "insert"
```

**評価:**
- ✅ **動作は同等**: `upsert`と`update`/`insert`の組み合わせは同等の動作
- ✅ **改善**: より明示的で、ログ出力が容易
- ⚠️ **注意**: レースコンディションの可能性（ただし、`upsert`でも同様）

**リスク: 低** - 動作は同等であり、既存の動作を壊す可能性は低い

---

#### 2-2. サービスロールクライアントの使用（破壊的変更の可能性：**低**）

**変更内容:**
- `get_plan`と`get_usage`関数で、サービスロールクライアントを使用

**評価:**
- ✅ **改善**: RLSの影響を排除
- ✅ **安全**: 既存の動作を壊す可能性は低い

---

#### 2-3. ログ出力の追加（破壊的変更の可能性：**なし**）

**追加されたログ:**
- 更新データの詳細
- 操作結果（update/insert）
- DB保存確認

**評価:**
- ✅ **安全**: ログ出力のみで、処理ロジックに影響なし

---

### 3. `api/utils/subscription_service.py`

#### 3-1. ログ出力の追加（破壊的変更の可能性：**なし**）

**追加されたログ:**
- DBから取得した実際の値

**評価:**
- ✅ **安全**: ログ出力のみで、処理ロジックに影響なし

---

## 破壊的変更の可能性まとめ

| 変更内容 | 破壊的変更の可能性 | リスク評価 |
|---------|------------------|-----------|
| 認証処理の改善 | 低 | ✅ 安全 |
| エンタイトルメント判定の条件変更 | 中 | ⚠️ 注意が必要 |
| ログ出力の追加 | なし | ✅ 安全 |
| `upsert`から`update`/`insert`への変更 | 低 | ✅ 安全 |
| サービスロールクライアントの使用 | 低 | ✅ 安全 |

## デプロイ前の確認事項

### ✅ 必須確認

1. **環境変数の確認**
   - `REVENUECAT_WEBHOOK_AUTH_TOKEN`が正しく設定されているか
   - `Bearer `が含まれている場合、動作確認が必要

2. **エンタイトルメント判定の動作確認**
   - `product_id`が存在する場合、エンタイトルメントをチェックしない動作が正しいか
   - これは意図的な修正であることを確認

3. **ログレベルの確認**
   - 本番環境のログレベルがINFO以上に設定されているか
   - `🔍 [WEBHOOK]`のログが出力されることを確認

### ⚠️ 注意事項

1. **エンタイトルメント判定の変更**
   - 以前の動作と異なる可能性がある
   - ただし、これは意図的な修正であり、問題解決のための変更

2. **`upsert`から`update`/`insert`への変更**
   - 動作は同等だが、レースコンディションの可能性がある
   - ただし、`upsert`でも同様の可能性がある

## デプロイ推奨

### ✅ デプロイ可能

**理由:**
1. 主な変更はログ出力の追加（安全）
2. 認証処理の改善（後方互換性あり）
3. エンタイトルメント判定の変更は意図的な修正
4. `upsert`から`update`/`insert`への変更は動作が同等

### ⚠️ デプロイ後の確認事項

1. **ログの確認**
   - `🔍 [WEBHOOK]`のログが出力されるか確認
   - 特に、リクエスト受信タイムスタンプ、product_id、プランタイプ判定結果

2. **動作確認**
   - Webhookが正常に処理されるか確認
   - エンタイトルメント判定が正しく動作するか確認

3. **エラーの監視**
   - デプロイ後、エラーログを監視
   - 認証エラーが発生していないか確認

## ロールバック計画

### ロールバックが必要な場合

1. **Gitで前のコミットに戻す**
   ```bash
   git revert HEAD
   ```

2. **または、特定のコミットに戻す**
   ```bash
   git reset --hard <commit-hash>
   ```

3. **本番環境に再デプロイ**

---

**作成日**: 2026-01-20  
**レビュー対象**: 最終コミット以降の変更
