# 冷蔵庫画像から在庫の新規登録 - 実装詳細プラン

## 1. 機能概要

冷蔵庫内の写真（または画像ファイル）をアップロードし、画像解析で在庫候補を抽出して在庫の新規登録を行う機能。

- **入力**: 冷蔵庫内を写した画像（写真撮影 or 画像読み取りの2種類。OCR在庫登録と同様）
- **出力**: 抽出された在庫候補リスト（フロントで選択後に登録）

### 1.1 アーキテクチャ（3層構成）

モバイルとバックエンドの間に **Morizo-web** が API ルートとして存在する。

```
Morizo-mobile（クライアント）
    ↓  API 呼び出し
Morizo-web（API ルート）  … ソース: /app/Morizo-web
    ↓  プロキシ（認証ヘッダー付き）
Morizo-aiv2（バックエンド）  … ソース: 本リポジトリ
```

- モバイルは **Morizo-web** の API を呼ぶ（aiv2 を直接叩かない）。
- Morizo-web は認証チェック後に aiv2 の `POST /api/inventory/...` にプロキシする。OCR レシートは既に `ocr-receipt` で同パターンが実装されている。

## 2. 流用元の整理（OCR読み取りによる在庫新規登録）

本機能は **OCRレシートによる在庫登録** の流れを流用する。

| 項目 | OCR（流用元） | 本機能（冷蔵庫画像） |
|------|----------------|----------------------|
| エンドポイント | `POST /inventory/ocr-receipt`（aiv2） | 新規 `POST /inventory/photo-refrigerator`（aiv2。Morizo-web は同パスでプロキシ） |
| 画像検証 | `validate_image_file()` | **流用** |
| 画像解析 | `OCRService.analyze_receipt_image()` レシート用プロンプト | 新規 冷蔵庫画像用プロンプトで解析 |
| 利用回数制限 | `subscription_service.check_usage_limit(..., "ocr")` | **制限なし**（何回でも可能。写真からのアップデート対応時に再検討） |
| 変換テーブル適用 | `ocr_service.apply_item_mappings()` | **使用しない**（現状は変換なし。変換テーブルへの登録もなし） |
| バリデーション | `validate_ocr_items()` | **流用**（同一フォーマット） |
| レスポンス形式 | `OCRReceiptResponse`（items, registered_count, errors） | **流用**（同一形式で返す） |
| 登録タイミング | フロントで選択後に登録（registered_count=0で返す） | **同様** |

### 2.1 流用元の主要コード位置（Morizo-aiv2）

- **API**: `api/routes/inventory.py`  
  - `ocr_receipt()`（行 238〜356）
- **画像解析**: `services/ocr_service.py`  
  - `OCRService.analyze_receipt_image()`, `apply_item_mappings()`, `normalize_item_name()`
- **画像検証**: `api/utils/file_validator.py`  
  - `validate_image_file()`
- **バリデーション**: `api/utils/ocr_validator.py`  
  - `validate_ocr_items()`
- **レスポンスモデル**: `api/models/requests.py`  
  - `OCRReceiptItem`, `OCRReceiptResponse`
- **利用回数**: `api/utils/subscription_service.py`（feature `"ocr"`）、`api/routes/subscription.py`（ocr_count）

---

## 3. バックエンド（Morizo-aiv2）実装プラン

### 3.1 新規エンドポイント

| 項目 | 内容 |
|------|------|
| パス | `POST /inventory/photo-refrigerator`（確定） |
| リクエスト | `image: UploadFile`（OCR と同様） |
| レスポンス | `OCRReceiptResponse` を流用（`items`, `registered_count`, `errors`） |

処理フロー:

1. 認証・クライアント取得（`get_authenticated_user_and_client`）
2. 画像検証（`validate_image_file` 流用）
3. **冷蔵庫画像解析**（新規メソッド、3.2）
4. バリデーション（`validate_ocr_items` 流用）
5. `registered_count=0` でレスポンス返却（登録はフロントで実施）

※ 利用回数制限は行わない。変換テーブル（`ocr_item_mappings`）の適用・登録は行わない。

### 3.2 サービス層：冷蔵庫画像解析

**対象ファイル**: `services/ocr_service.py` または新規 `services/refrigerator_image_service.py`

- **推奨**: `OCRService` に `analyze_refrigerator_image(image_bytes)` を追加し、レシート用と冷蔵庫用でプロンプトだけ分ける。
- **役割**: 冷蔵庫内が写った画像から、写っている食材・食品を在庫候補として抽出する。
- **入出力**:
  - 入力: `image_bytes: bytes`
  - 出力: OCR と同形式 `{ "success": bool, "items": [...], "error": str | None }`
  - `items` 各要素: `item_name`, `quantity`, `unit`, `storage_location`, `expiry_date`（OCRReceiptItem と同一）

**プロンプト方針**:

- 「冷蔵庫（または保存場所）の写真から、写っている食材・食品を列挙する」
- 見た目から推測できる数量・単位（1本、1パックなど）を記載
- 保管場所は「冷蔵庫」「冷凍庫」等を推測
- 消費期限は写っていれば抽出、なければ `null`
- レスポンス形式は OCR と同じ JSON 配列（コードブロック形式）に統一

※ レシート用の「ブランド名除外」「食材名のみ」などの正規化は、冷蔵庫画像用にも `normalize_item_name` を適用するか、プロンプトで「食材名のみ」を指示するかは実装時に調整。

### 3.3 既存コンポーネントの流用一覧

| コンポーネント | ファイル | 流用内容 |
|----------------|----------|----------|
| 画像検証 | `api/utils/file_validator.py` | `validate_image_file(image_bytes, filename)` |
| バリデーション | `api/utils/ocr_validator.py` | `validate_ocr_items(items)` |
| レスポンス形式 | `api/models/requests.py` | `OCRReceiptResponse` / `OCRReceiptItem` |
| 認証 | `api/utils/inventory_auth.py` | `get_authenticated_user_and_client(http_request)` |

※ 変換テーブル（`ocr_item_mappings`）は使用しない。`apply_item_mappings` は呼ばない。

### 3.4 利用回数制限の扱い

- **現状**: 写真在庫登録は**利用回数制限なし**（何回でも可能）。
- 理由: 初期登録でしか利用しない想定のため。
- **将来**: 写真からのアップデート（既存在庫の更新）まで対応した時点で、利用回数制限を検討する。

バックエンドでは `subscription_service` のチェック・インクリメントは行わない。

### 3.5 修正・追加対象ファイル一覧（Morizo-aiv2）

| 種別 | ファイル | 内容 |
|------|----------|------|
| API | `api/routes/inventory.py` | `POST /inventory/photo-refrigerator` ハンドラ追加（ocr_receipt をベースに、解析呼び出しのみ冷蔵庫用に変更。利用回数・変換テーブル処理は含めない） |
| サービス | `services/ocr_service.py` | `analyze_refrigerator_image(image_bytes)` 追加（冷蔵庫用プロンプト＋既存の JSON 解析・normalize 流用） |

※ モデル・バリデーター・file_validator は流用のため変更不要（必要ならコメント追記のみ）。

---

## 4. Morizo-web（APIルート）の改修内容

ソースは `/app/Morizo-web`（別リポジトリ）。モバイルからのリクエストを受け、aiv2 にプロキシする。

- **新規 API ルートの追加**
  - パス: `POST /api/inventory/photo-refrigerator`
  - 実装場所: `app/api/inventory/photo-refrigerator/route.ts` を新規作成
  - 流用元: `app/api/inventory/ocr-receipt/route.ts` と同様のパターンで実装する。

- **処理内容**
  - リクエストの認証（`authenticateRequest`）。
  - FormData から `image` を取得し、存在しなければ 400 を返す。
  - `MORIZO_AI_URL` に対して `POST ${MORIZO_AI_URL}/api/inventory/photo-refrigerator` に FormData（`image`）と `Authorization: Bearer ${token}` を付与して転送。
  - レスポンスをそのまま JSON で返す（`success`, `items`, `registered_count`, `errors`）。OCR レシートと同一形式。
  - CORS ヘッダー設定・OPTIONS ハンドラ・タイムアウト（例: 3分）・エラーハンドリングは ocr-receipt に合わせる。

- **変更不要**
  - 認証・ロギング・環境変数（`MORIZO_AI_URL`）は既存の ocr-receipt と共通のため、新規ルートのみ追加すればよい。

---

## 5. モバイル側（Morizo-mobile）の改修内容

リポジトリは `/app/Morizo-mobile`（別リポジトリ）のため、別環境で実装する。以下は改修内容の記載のみ。

- **写真撮影**
  - 冷蔵庫画像登録用のカメラ撮影 UI を追加する。
  - 撮影後に **Morizo-web** の `POST /api/inventory/photo-refrigerator` に画像を送信する。

- **画像読み取り（ギャラリー選択）**
  - 端末の画像ライブラリから冷蔵庫画像を選択する UI を追加する。
  - 選択後に **Morizo-web** の `POST /api/inventory/photo-refrigerator` に画像を送信する。

- **API 連携**
  - 呼び先: **Morizo-web** の `POST /api/inventory/photo-refrigerator`（モバイルは aiv2 を直接呼ばない）。
  - リクエスト: 画像ファイル（multipart、キーは ocr-receipt と同様 `image` 想定）で送信。
  - レスポンス: OCR と同形式（`success`, `items`, `registered_count`, `errors`）として扱い、既存の「OCR結果→選択→登録」フローを流用する。

- **利用回数制限**
  - 本機能は利用回数制限なしのため、403 は想定しない。将来的に制限を導入した場合は、その時点でエラー表示を追加する。

- **UX**
  - 冷蔵庫画像用の入口（例: 「冷蔵庫の写真から追加」）を、既存の「レシートから追加」と並べて配置する。
  - 解析結果の一覧・選択・在庫登録の流れは OCR 登録と同じにすると実装負荷を抑えられる。

---

## 6. 確定済み事項

- **エンドポイントパス**: `POST /inventory/photo-refrigerator` で確定。
- **利用回数**: 現状は制限なし（何回でも可能）。写真からのアップデート対応時に再検討。
- **変換テーブル**: 冷蔵庫画像では `ocr_item_mappings` の適用・登録は行わない（変換なし）。

---

## 7. 実装セッションの目安

| 対象 | 変更量の目安 | 1セッションで実施可能か | コンテキスト溢れのリスク |
|------|----------------|--------------------------|----------------------------|
| **Morizo-aiv2** | 2ファイル。API にハンドラ追加（約80行）、`ocr_service` に `analyze_refrigerator_image` 追加（約90行）。いずれも ocr_receipt の流用で新規追加のみ。 | 可能。 | 低。参照する既存コードも少なめ。 |
| **Morizo-web** | 1ファイル新規。`app/api/inventory/photo-refrigerator/route.ts` を ocr-receipt のコピー＋URL・ログ文言の差し替えで作成（約160行）。 | 可能。 | 低。ocr-receipt 1本を参照すれば足りる。 |
| **Morizo-mobile** | 別リポジトリ。写真撮影・ギャラリー選択・API 呼び出し・結果表示など、既存 OCR フローの流用を含むため、触るファイル数は多くなりがち。 | 1セッションでやる場合は、aiv2・web の後に回すとよい。 | 中。既存 OCR 周りを複数開く必要があると、コンテキストが膨らむ可能性あり。 |

**推奨**

- **aiv2 ＋ Morizo-web のみ**: 1回のセッションで実施して問題ない。コンテキストが溢れる心配は小さい。
- **モバイルまで含める場合**: 別環境のため **「aiv2 → web」を 1 セッション、「Morizo-mobile」を別セッション** に分けると、コンテキストを抑えつつ進めやすい。モバイルを同じセッションでやる場合は、aiv2 → web → mobile の順で進め、参照ファイルが増えてきた時点で一度区切るか、セッション分割を検討すると安全。
