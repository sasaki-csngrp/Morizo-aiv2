# ログレベル分類詳細修正プラン

## 概要

本ドキュメントは、`PRODUCTION_LOGGING_PLAN.md`の分類基準に基づいて、全ソースコードのログレベルをINFO/DEBUGに分類し直すための詳細な修正プランです。

## 分類基準（再掲）

### INFOレベル（本番環境でも出力）
- リクエスト受信・処理開始（詳細パラメータは含めない）
- 認証成功（user_idは含める）
- 処理完了・成功（IDや件数などの詳細は含めない）
- 重要な状態変化
- エラー発生時のエラーメッセージ

### DEBUGレベル（開発環境のみ出力）
- 詳細な変数の値（user_id、item_id、mapping_idなど、認証成功ログのuser_idを除く）
- ファイル名、パラメータの詳細値
- 中間処理の詳細
- データ構造の内容（JSON、リスト、辞書など）
- 条件分岐の詳細
- 件数・統計情報

---

## 修正対象ファイル一覧

### 優先度1: API層（既に1ファイル修正済み）

#### ✅ 完了: `api/routes/inventory.py`
- 修正済み（22箇所）

#### 📝 修正予定: `api/routes/recipe.py`
- **修正箇所数**: 約40箇所
- **主な修正内容**:
  - リクエスト受信ログから詳細パラメータをDEBUGに分離
  - user_idログをDEBUGに変更（認証成功ログを除く）
  - 件数ログをDEBUGに分離
  - レシピ詳細情報をDEBUGに分離
  - インベントリID、数量などの詳細をDEBUGに分離

#### 📝 修正予定: `api/routes/menu.py`
- **修正箇所数**: 約18箇所
- **主な修正内容**:
  - リクエスト受信ログから詳細パラメータをDEBUGに分離
  - user_idログをDEBUGに変更（認証成功ログを除く）
  - レシピ詳細情報をDEBUGに分離
  - 件数ログをDEBUGに分離

#### 📝 修正予定: `api/routes/chat.py`
- **修正箇所数**: 約43箇所
- **主な修正内容**:
  - リクエスト詳細情報をDEBUGに変更
  - ヘッダー、ボディの詳細をDEBUGに変更
  - パース結果の詳細をDEBUGに変更

#### 📝 修正予定: `api/routes/health.py`
- **修正箇所数**: 約4箇所
- **主な修正内容**:
  - 基本的なヘルスチェックログはINFOのまま
  - 詳細なサービス状態確認はDEBUGに変更

#### 📝 修正予定: `api/middleware/auth.py`
- **修正箇所数**: 約5箇所
- **主な修正内容**:
  - 既にDEBUGログを追加済み（変更なし）

#### 📝 修正予定: `api/middleware/logging.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - リクエスト処理時間の詳細をDEBUGに分離

#### 📝 修正予定: `api/utils/auth_handler.py`
- **修正箇所数**: 約7箇所
- **主な修正内容**:
  - 認証処理の詳細をDEBUGに変更

#### 📝 修正予定: `api/utils/sse_manager.py`
- **修正箇所数**: 約11箇所
- **主な修正内容**:
  - SSE接続の詳細をDEBUGに変更

---

### 優先度2: MCP層

#### 📝 修正予定: `mcp_servers/inventory_mcp.py`
- **修正箇所数**: 約25箇所
- **主な修正内容**:
  - 処理開始ログからuser_idをDEBUGに分離
  - 認証成功ログはuser_idを含めてINFOのまま
  - 処理結果の詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `mcp_servers/inventory_crud.py`
- **修正箇所数**: 約19箇所
- **主な修正内容**:
  - 処理開始ログから詳細パラメータをDEBUGに分離
  - 処理結果の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/inventory_advanced.py`
- **修正箇所数**: 約12箇所
- **主な修正内容**:
  - 高度な処理の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/recipe_mcp.py`
- **修正箇所数**: 約36箇所
- **主な修正内容**:
  - 処理開始ログからuser_idをDEBUGに分離
  - 認証成功ログはuser_idを含めてINFOのまま
  - 処理結果の詳細をDEBUGに変更（既に一部DEBUG）
  - 件数ログをDEBUGに分離

#### 📝 修正予定: `mcp_servers/recipe_llm.py`
- **修正箇所数**: 約15箇所
- **主な修正内容**:
  - LLM処理の詳細をDEBUGに変更
  - JSON解析の詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `mcp_servers/recipe_web.py`
- **修正箇所数**: 約4箇所
- **主な修正内容**:
  - 検索結果の詳細をDEBUGに分離

#### 📝 修正予定: `mcp_servers/recipe_history_mcp.py`
- **修正箇所数**: 約21箇所
- **主な修正内容**:
  - 処理開始ログからuser_idをDEBUGに分離
  - 認証成功ログはuser_idを含めてINFOのまま
  - 処理結果の詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `mcp_servers/recipe_history_crud.py`
- **修正箇所数**: 約14箇所
- **主な修正内容**:
  - 処理開始ログから詳細パラメータをDEBUGに分離
  - 処理結果の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/recipe_rag/client.py`
- **修正箇所数**: 約12箇所
- **主な修正内容**:
  - RAG検索の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/recipe_rag/menu_format.py`
- **修正箇所数**: 約12箇所
- **主な修正内容**:
  - メニュー変換の詳細をDEBUGに変更（既に一部DEBUG）
  - データ構造の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/recipe_rag/search.py`
- **修正箇所数**: 約3箇所
- **主な修正内容**:
  - 検索処理の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/recipe_rag/llm_solver.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - LLM解決処理の詳細をDEBUGに変更

#### 📝 修正予定: `mcp_servers/ocr_mapping_crud.py`
- **修正箇所数**: 約12箇所
- **主な修正内容**:
  - 処理開始ログから詳細パラメータをDEBUGに分離
  - 処理結果の詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `mcp_servers/client.py`
- **修正箇所数**: 約8箇所
- **主な修正内容**:
  - MCPツール呼び出しの詳細をDEBUGに変更（既に一部DEBUG）

---

### 優先度3: Service層

#### 📝 修正予定: `services/llm_service.py`
- **修正箇所数**: 約13箇所
- **主な修正内容**:
  - LLM処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/llm_client.py`
- **修正箇所数**: 約5箇所
- **主な修正内容**:
  - LLMクライアントの詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/service_handlers.py`
- **修正箇所数**: 約21箇所
- **主な修正内容**:
  - サービスハンドラーの詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `services/llm/response_processor.py`
- **修正箇所数**: 約9箇所
- **主な修正内容**:
  - レスポンス処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/response_formatters/recipe_formatter.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - フォーマット処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/response_formatters/inventory_formatter.py`
- **修正箇所数**: 約7箇所
- **主な修正内容**:
  - フォーマット処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/session_info_handler.py`
- **修正箇所数**: 約6箇所
- **主な修正内容**:
  - セッション情報処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/menu_data_generator.py`
- **修正箇所数**: 約5箇所
- **主な修正内容**:
  - メニューデータ生成の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/web_search_integrator.py`
- **修正箇所数**: 約3箇所
- **主な修正内容**:
  - Web検索統合の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/request_analyzer.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - リクエスト解析の詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/utils.py`
- **修正箇所数**: 約1箇所
- **主な修正内容**:
  - ユーティリティの詳細をDEBUGに変更

#### 📝 修正予定: `services/llm/prompt_manager/base.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - プロンプト管理の詳細をDEBUGに変更

#### 📝 修正予定: `services/tool_router.py`
- **修正箇所数**: 約15箇所
- **主な修正内容**:
  - ツールルーティングの詳細をDEBUGに変更

#### 📝 修正予定: `services/ocr_service.py`
- **修正箇所数**: 約6箇所
- **主な修正内容**:
  - OCR処理の詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `services/session/crud_manager.py`
- **修正箇所数**: 約10箇所
- **主な修正内容**:
  - セッションCRUDの詳細をDEBUGに変更

#### 📝 修正予定: `services/session/confirmation_manager.py`
- **修正箇所数**: 約11箇所
- **主な修正内容**:
  - 確認管理の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/helpers.py`
- **修正箇所数**: 約4箇所
- **主な修正内容**:
  - ヘルパー関数の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/help_state_manager.py`
- **修正箇所数**: 約8箇所
- **主な修正内容**:
  - ヘルプ状態管理の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/models/components/ingredient_mapper.py`
- **修正箇所数**: 約4箇所
- **主な修正内容**:
  - 材料マッピングの詳細をDEBUGに変更（既に一部DEBUG）

#### 📝 修正予定: `services/session/models/components/candidate.py`
- **修正箇所数**: 約1箇所
- **主な修正内容**:
  - 候補処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/models/components/proposal.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - 提案処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/models/components/context.py`
- **修正箇所数**: 約1箇所
- **主な修正内容**:
  - コンテキスト処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/session/models/components/stage.py`
- **修正箇所数**: 約1箇所
- **主な修正内容**:
  - ステージ処理の詳細をDEBUGに変更

#### 📝 修正予定: `services/confirmation_service.py`
- **修正箇所数**: 約7箇所
- **主な修正内容**:
  - 確認サービスの詳細をDEBUGに変更

#### 📝 修正予定: `services/confirmation/ambiguity_detector.py`
- **修正箇所数**: 約6箇所
- **主な修正内容**:
  - 曖昧性検出の詳細をDEBUGに変更

#### 📝 修正予定: `services/confirmation/response_parser.py`
- **修正箇所数**: 約5箇所
- **主な修正内容**:
  - レスポンス解析の詳細をDEBUGに変更

---

### 優先度4: Core層

#### 📝 修正予定: `core/agent.py`
- **修正箇所数**: 約23箇所
- **主な修正内容**:
  - エージェント処理の詳細をDEBUGに変更

#### 📝 修正予定: `core/executor.py`
- **修正箇所数**: 約47箇所
- **主な修正内容**:
  - タスク実行の詳細をDEBUGに変更

#### 📝 修正予定: `core/planner.py`
- **修正箇所数**: 約10箇所
- **主な修正内容**:
  - プランニングの詳細をDEBUGに変更

#### 📝 修正予定: `core/service_coordinator.py`
- **修正箇所数**: 約9箇所
- **主な修正内容**:
  - サービス調整の詳細をDEBUGに変更

#### 📝 修正予定: `core/dynamic_task_builder.py`
- **修正箇所数**: 約4箇所
- **主な修正内容**:
  - タスク構築の詳細をDEBUGに変更

#### 📝 修正予定: `core/handlers/confirmation_handler.py`
- **修正箇所数**: 約15箇所
- **主な修正内容**:
  - 確認ハンドラーの詳細をDEBUGに変更

#### 📝 修正予定: `core/handlers/selection_handler.py`
- **修正箇所数**: 約29箇所
- **主な修正内容**:
  - 選択ハンドラーの詳細をDEBUGに変更

#### 📝 修正予定: `core/handlers/stage_manager.py`
- **修正箇所数**: 約8箇所
- **主な修正内容**:
  - ステージ管理の詳細をDEBUGに変更

#### 📝 修正予定: `core/response_formatter.py`
- **修正箇所数**: 約2箇所
- **主な修正内容**:
  - レスポンスフォーマットの詳細をDEBUGに変更

#### 📝 修正予定: `core/models.py`
- **修正箇所数**: 約13箇所
- **主な修正内容**:
  - モデル処理の詳細をDEBUGに変更

#### 📝 修正予定: `core/context_manager.py`
- **修正箇所数**: 約8箇所
- **主な修正内容**:
  - コンテキスト管理の詳細をDEBUGに変更（既に一部DEBUG）

---

### その他

#### 📝 修正予定: `main.py`
- **修正箇所数**: 約4箇所（テスト用ログ含む）
- **主な修正内容**:
  - 起動時のテスト用ログは残す（切り分け用）

---

## 実装順序と判断基準

### 重要な判断基準

**Phase 1（MVP必須）の前にログレベル分類を実施する必要がある**

#### 理由

1. **現状の問題点**
   - 約1978箇所のログ出力があり、ほぼすべてがINFOログになっている
   - Phase 0（DEBUGログ出力修正）は完了しているが、ログレベル分類は未実施
   - 本番環境で`LOG_LEVEL=INFO`に設定すると、不要な詳細ログが大量に出力される

2. **Phase 1の前に分類する必要性**
   - Phase 1で環境変数対応を実装すると、本番環境でログレベルを制御できるようになる
   - しかし、現在ほぼすべてがINFOログになっているため、本番環境でINFOレベルに設定すると、大量の不要なログが出力される
   - 事前にログレベルを適切に分類することで、本番環境でのログ管理が容易になる
   - ログ量が適切になり、ログ分析が容易になる

3. **実装順序の確定**
   - ✅ Phase 0（DEBUGログ出力修正）: 完了
   - 🔄 **ログレベル分類（INFO/DEBUG）**: 現在のフェーズ（Phase 1の前に実施）
   - ⏳ Phase 1（環境変数対応、logrotate設定）: ログレベル分類完了後に実施

#### 注意事項

- **Phase 1の前にログレベル分類を実施すること**を明確に理解する
- Phase 1で環境変数対応を実装しても、ログレベル分類が未完了だと本番環境で大量の不要なログが出力される
- ログレベル分類は約58ファイル、約680箇所の修正が必要なため、段階的に実施する
- **優先度ごとにまとめて処理する**（優先度1→優先度2→優先度3→優先度4の順）

---

## 修正作業の進め方

### 優先度ごとの一括処理方式

各優先度（優先度1→優先度2→優先度3→優先度4）について、以下の手順で一括処理します：

#### ステップ1: 優先度ごとに全ファイルのログ出力箇所を確認
該当優先度の全ファイルについて、以下を確認：
1. ログ出力箇所の特定（grepで確認）
2. 分類基準に基づいた分類
3. 修正内容の明確化

#### ステップ2: 優先度ごとに修正プランを作成・提示
該当優先度の全ファイルについて、以下をまとめて提示：
- **修正対象ファイル一覧**（ファイル名と修正箇所数）
- **各ファイルの修正内容**（修正箇所、修正内容、修正理由、修正の影響）
- **修正パターンの分類**（どのパターンに該当するか）

#### ステップ3: 優先度ごとに承認を得る
該当優先度の修正プランを提示し、承認を得る

#### ステップ4: 優先度ごとに一括で修正実施
承認後、該当優先度の全ファイルを一括で修正実施

#### ステップ5: 優先度ごとに動作確認
修正後、該当優先度の動作確認を実施

### 処理順序

1. **優先度1（API層）**: 約10ファイル、約150箇所
2. **優先度2（MCP層）**: 約13ファイル、約200箇所
3. **優先度3（Service層）**: 約24ファイル、約200箇所
4. **優先度4（Core層）**: 約11ファイル、約130箇所

---

## 修正パターン一覧

### パターン1: リクエスト受信ログ（修正しない）
**現在:**
```python
logger.info(f"🔍 [API] Request received: param1={param1}, param2={param2}")
```

**修正後:**
```python
# 変更なし（詳細パラメータを分離するとログ行数が増えるだけ）
logger.info(f"🔍 [API] Request received: param1={param1}, param2={param2}")
```

### パターン2: user_idログ（認証成功ログを除く）
**修正前:**
```python
logger.info(f"🔍 [API] User ID: {user_id}")
```

**修正後:**
```python
logger.debug(f"🔍 [API] User ID: {user_id}")
```

### パターン3: 認証成功ログ（user_idを含める、修正しない）
**現在:**
```python
logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
```

**修正後:**
```python
# 変更なし（user_idは認証成功ログに重要なのでINFOに残す）
logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
```

### パターン4: 処理完了ログ（IDを含む、修正しない）
**現在:**
```python
logger.info(f"✅ [API] Item added: {item_id}")
```

**修正後:**
```python
# 変更なし（IDを分離するとログ行数が増えるだけ）
logger.info(f"✅ [API] Item added: {item_id}")
```

### パターン5: 件数ログ（修正しない）
**現在:**
```python
logger.info(f"✅ [API] Retrieved {count} items")
```

**修正後:**
```python
# 変更なし（件数を分離するとログ行数が増えるだけ）
logger.info(f"✅ [API] Retrieved {count} items")
```

### パターン6: データ構造の詳細（修正する）
**修正前:**
```python
logger.info(f"📊 [API] Result: {result}")
```

**修正後:**
```python
logger.debug(f"📊 [API] Result: {result}")
```

### パターン7: 中間処理の詳細（修正する）
**修正前:**
```python
logger.info(f"✅ [API] Applied mappings to {len(items)} items")
```

**修正後:**
```python
logger.debug(f"✅ [API] Applied mappings to {len(items)} items")
```

---

## 統計情報

- **総ファイル数**: 約58ファイル
- **総修正箇所数**: 約680箇所（推定）
- **優先度1（API層）**: 約10ファイル、約150箇所
- **優先度2（MCP層）**: 約13ファイル、約200箇所
- **優先度3（Service層）**: 約24ファイル、約200箇所
- **優先度4（Core層）**: 約11ファイル、約130箇所

---

## 注意事項

1. **認証成功ログのuser_id**: 認証成功ログにはuser_idを含める（INFOレベル）
2. **エラーログ**: ERRORレベルは変更しない
3. **警告ログ**: WARNINGレベルは変更しない
4. **後方互換性**: 既存の動作に影響を与えないよう注意
5. **テスト用ログ**: `main.py`の起動時テスト用ログは残す（切り分け用）
6. **ログ行数の増加を避ける**: 詳細パラメータ、ID、件数を分離して2行にする必要はない（ログ行数が増えるだけ）
   - リクエスト受信ログ: 詳細パラメータを含めたままINFOで残す
   - 処理完了ログ: IDを含めたままINFOで残す
   - 件数ログ: 件数を含めたままINFOで残す

---

## 更新履歴

- 2025-11-15: 初版作成
- 2025-11-15: `api/routes/inventory.py`修正完了を反映
- 2025-11-15: 修正作業の進め方を優先度ごとの一括処理方式に変更

