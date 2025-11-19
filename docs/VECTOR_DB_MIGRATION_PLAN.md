# ベクトルDB移行・拡張実装プラン

## 1. 目的と背景

### 1.1 目的
1. **Google Search APIの使用回数削減**: ベクトルDBにURLを埋め込むことで、Web検索の回数を減らし課金額を削減
2. **データ構造の最適化**: Lora FineTuning用のデータ形式から、ベクトルDB専用の構造化フォーマットへ移行

### 1.2 現状の問題点
- 現在のデータ形式は `(title)`, `(ingredientText)`, `[回答]` を含むテキスト形式で、パース処理が複雑
- URL情報がベクトルDBに含まれておらず、毎回Google Search APIを呼び出す必要がある
- データ量: 約6,000件

### 1.3 前提条件
- 元データ（DB）にはURL情報が含まれている
- DBから再生成するバッチスクリプトを別途準備する
- URL取得は一括で実行（バッチスクリプトで処理）

---

## 2. 新しいデータフォーマット設計

### 2.1 JSONL形式の新フォーマット

```json
{
  "id": "25194593",
  "title": "肉じゃが",
  "category": "main",
  "category_detail": "おかず肉じゃが",
  "ingredients": ["牛肉", "じゃがいも", "玉ねぎ", "にんじん"],
  "main_ingredients": [""],
  "url": "https://cookpad.com/jp/recipes/25194593"
}
```

**注意**: `main_ingredients` は任意フィールドです。データ品質が低い場合（例: 調味料が含まれる）や、DBに情報がない場合は空文字列の配列 `[""]` で問題ありません。検索ロジックには使用されず、検索結果の表示にのみ使用されます。

### 2.2 フィールド定義

#### 必須フィールド（RAG検索に必要）

| フィールド | 型 | 必須 | 用途 | 説明 |
|-----------|-----|------|------|------|
| `id` | string | 必須 | 内部管理 | レシピの一意識別子（例: `25194593`） |
| `title` | string | 必須 | ベクトル化・メタデータ・検索結果 | レシピのタイトル |
| `category` | string | 必須 | メタデータ・検索結果 | カテゴリ: `"main"`, `"sub"`, `"soup"` |
| `ingredients` | array[string] | 必須 | **ベクトル化** | 食材リスト（調味料除外済み） |
| `url` | string | 必須 | メタデータ・検索結果 | レシピのURL（Google Search削減のため） |

#### 任意フィールド（オプション）

| フィールド | 型 | 必須 | 用途 | 説明 |
|-----------|-----|------|------|------|
| `category_detail` | string | 任意 | 検索結果 | 詳細カテゴリ（例: `"丼もの"`, `"ラーメン"`, `"おかず肉じゃが"`） |
| `main_ingredients` | array[string] | 任意 | 検索結果 | 主材料リスト（検索結果に表示される）<br>**注意**: データ品質が低い場合や存在しない場合は空文字列の配列 `[""]` でOK |

#### 削除したフィールド（RAG検索に未使用）

以下のフィールドは、現状の実装では使用されていないため削除：

- `description`: ベクトル化にも検索結果にも含まれていない
- `cooking_time`: 検索には使用されていない
- `difficulty`: 検索には使用されていない
- `source`: 検索には使用されていない（URLから抽出可能）

**注意**: 将来的にこれらの情報が必要になった場合は、後から追加可能です。

### 2.3 カテゴリ分類

- **`main`**: 主菜
- **`sub`**: 副菜
- **`soup`**: 汁物

---

## 3. URL埋め込み方法

### 3.1 URLの取得と埋め込み

1. **DBから再生成するバッチスクリプトでURLを含める**
   - 元データ（DB）からURL情報を取得
   - 新フォーマットのJSONLファイルにURLを含めて出力

2. **ベクトルDB構築時にメタデータにURLを追加**
   - `metadata` に `url` フィールドを追加
   - 検索結果から直接URLを取得可能にする

3. **Web検索の最適化**
   - RAG検索結果にURLが含まれている場合は、Google Search APIをスキップ
   - URLが無効または古い場合のフォールバック処理を実装

### 3.2 メタデータ構造

```python
metadata = {
    'title': recipe['title'],
    'recipe_category': recipe['category'],
    'category_detail': recipe.get('category_detail', ''),
    'main_ingredients': ', '.join(recipe.get('main_ingredients', [])[:3]),
    'url': recipe.get('url', ''),  # 新規追加（Google Search削減のため）
    'original_index': i,
    'category_index': len(processed_recipes)
}
```

---

## 4. 実装ステップ

### ステップ1: データ変換スクリプトの作成

**ファイル**: `scripts/convert_recipe_data_to_new_format.py`

**機能**:
1. DBからレシピデータを取得（URL含む）
2. 既存の `recipe_data.jsonl` 形式から新フォーマットへ変換
3. 新フォーマットのJSONLファイルを出力

**出力ファイル**: `me2you/recipe_data_new.jsonl`

### ステップ2: ベクトルDB構築スクリプトの更新

**ファイル**: `scripts/build_vector_db_by_category.py`

**変更内容**:
1. 新フォーマットのJSONLファイルを読み込む
2. URLをメタデータに追加
3. 3つのベクトルDBを構築: `main`, `sub`, `soup`

**出力ディレクトリ**:
- `recipe_vector_db_main`
- `recipe_vector_db_sub`
- `recipe_vector_db_soup`

### ステップ3: RAGクライアントの更新

**ファイル**: `mcp_servers/recipe_rag/client.py`

**変更内容**:
1. URLをメタデータから取得する処理を追加
2. 検索結果にURLを含める処理を追加

### ステップ4: Web検索の最適化

**ファイル**: `mcp_servers/recipe_web.py`, `mcp_servers/recipe_mcp.py`

**変更内容**:
1. RAG検索結果にURLが含まれている場合、Google Search APIをスキップ
2. URLの有効性チェック（オプション）
3. URLが無効な場合のフォールバック処理


---

## 5. 詳細実装仕様

### 5.1 データ変換スクリプト詳細

```python
# scripts/convert_recipe_data_to_new_format.py

def convert_old_format_to_new(old_recipe: Dict[str, Any], recipe_id: str, url: str) -> Dict[str, Any]:
    """
    旧フォーマットから新フォーマットへ変換
    
    Args:
        old_recipe: 旧フォーマットのレシピデータ
        recipe_id: レシピID（DBから取得、例: "25194593"）
        url: レシピのURL（DBから取得）
        
    Returns:
        新フォーマットのレシピデータ
    """
    # 既存のextract_recipe_info()を利用して情報を抽出
    recipe_info = extract_recipe_info(old_recipe)
    
    # 新フォーマットに変換（RAG検索に必要なフィールドのみ）
    # idはDBから取得したレシピIDをそのまま使用（例: "25194593"）
    new_recipe = {
        'id': recipe_id,  # DBから取得したレシピID
        'title': recipe_info['title'],
        'category': recipe_info['category'],
        'category_detail': recipe_info.get('category_detail', ''),
        'ingredients': normalize_ingredients(recipe_info['ingredients_text']),
        'main_ingredients': recipe_info.get('main_ingredients', [""]),  # 任意: データ品質が低い場合は空文字列の配列でOK
        'url': url
    }
    
    # 注意: main_ingredients が存在しない場合や品質が低い場合は空文字列の配列 [""] のまま
    # 検索ロジックには使用されず、検索結果の表示にのみ使用される
    
    return new_recipe
```

### 5.2 ベクトルDB構築スクリプトの変更点

```python
# scripts/build_vector_db_by_category.py

# カテゴリリスト
categories = [
    ('main', 'recipe_vector_db_main', '主菜'),
    ('sub', 'recipe_vector_db_sub', '副菜'),
    ('soup', 'recipe_vector_db_soup', '汁物')
]

# メタデータにURLを追加（RAG検索に必要なフィールドのみ）
metadata = {
    'title': recipe['title'],
    'recipe_category': recipe['category'],
    'category_detail': recipe.get('category_detail', ''),
    'main_ingredients': ', '.join(recipe.get('main_ingredients', [])[:3]),
    'url': recipe.get('url', ''),  # 新規追加（Google Search削減のため）
    'original_index': i,
    'category_index': len(processed_recipes)
}
```

### 5.3 Web検索の最適化

```python
# mcp_servers/recipe_mcp.py

async def search_recipe_from_web(
    recipe_titles: List[str],
    ...
) -> Dict[str, Any]:
    """
    レシピをWeb検索（URLが既にある場合はスキップ）
    """
    results = []
    
    for title in recipe_titles:
        # RAG検索結果からURLを取得（既に取得済みの場合）
        rag_result = get_rag_result_by_title(title)
        if rag_result and rag_result.get('url'):
            # URLが既にある場合はWeb検索をスキップ
            results.append({
                'title': title,
                'url': rag_result['url'],
                'source': 'vector_db'  # ベクトルDBから取得
            })
        else:
            # URLがない場合のみGoogle Search APIを呼び出す
            web_result = await search_client.search_recipes(title, num_results)
            results.append({
                'title': title,
                'url': web_result[0].get('url', ''),
                'source': 'web_search'  # Web検索から取得
            })
    
    return results
```

---

## 6. 移行手順

### 6.1 準備フェーズ

1. **バックアップ**
   - 既存の `recipe_data.jsonl` をバックアップ
   - 既存のベクトルDBディレクトリをバックアップ

2. **DBから新フォーマットJSONL生成**
   - DBから再生成するバッチスクリプトを実行
   - `me2you/recipe_data_new.jsonl` を生成

### 6.2 変換フェーズ

1. **データ変換スクリプトの実行**
   ```bash
   python scripts/convert_recipe_data_to_new_format.py
   ```

2. **新フォーマットJSONLの検証**
   - データ件数の確認
   - URLの有無確認

### 6.3 ベクトルDB構築フェーズ

1. **新ベクトルDBの構築**
   ```bash
   python scripts/build_vector_db_by_category.py
   ```

2. **ベクトルDBの検証**
   - 3つのベクトルDBが正常に構築されたか確認
   - メタデータにURLが含まれているか確認
   - 検索テストの実行

### 6.4 コード更新フェーズ

1. **RAGクライアントの更新**
   - `mcp_servers/recipe_rag/client.py` を更新
   - 環境変数の追加

2. **Web検索の最適化**
   - `mcp_servers/recipe_mcp.py` を更新

### 6.5 テストフェーズ

1. **単体テスト**
   - URL取得ロジックのテスト
   - メタデータへのURL埋め込みのテスト

2. **統合テスト**
   - URL埋め込み後のWeb検索スキップのテスト
   - RAG検索結果にURLが含まれることの確認

3. **動作確認**
   - 既存機能（主菜・副菜・汁物）の動作確認
   - Google Search APIの使用回数削減の確認

### 6.6 デプロイフェーズ

1. **段階的デプロイ**
   - ステージング環境でテスト
   - 本番環境へのデプロイ

2. **モニタリング**
   - Google Search APIの使用回数削減を確認

---

## 7. テスト計画

### 7.1 単体テスト

#### テスト1: URL埋め込み
- **テストケース1**: URLが含まれるレシピ → メタデータにURLが追加される
- **テストケース2**: URLが空の場合 → 空文字列がメタデータに追加される

### 7.2 統合テスト

#### テスト1: Web検索の最適化
- **テストケース1**: RAG検索結果にURLがある場合、Google Search APIが呼ばれない
- **テストケース2**: RAG検索結果にURLがない場合、Google Search APIが呼ばれる

### 7.3 パフォーマンステスト

- **テスト1**: ベクトルDB構築時間の測定（6,000件）
- **テスト2**: URL埋め込み後の検索レスポンス時間

---

## 8. リスクと対策

### 8.1 リスク1: URLの無効化

**リスク**: 時間が経過してURLが無効になる

**対策**:
- URLの有効性チェック機能を実装（オプション）
- URLが無効な場合のフォールバック処理（Google Search APIを呼び出す）

### 8.2 リスク2: 既存機能への影響

**リスク**: 既存の主菜・副菜・汁物検索に影響が出る

**対策**:
- 既存機能のテストを十分に実施
- 段階的なデプロイ
- ロールバック手順の準備

---

## 9. 今後の拡張可能性

### 9.1 追加可能な機能

1. **レシピの評価・レビュー情報の埋め込み**
2. **調理時間・難易度によるフィルタリング**
3. **アレルギー情報の追加**
4. **画像URLの追加**

### 9.2 データ品質の向上

1. **URLの定期更新バッチ**
2. **レシピデータの重複チェック**
3. **食材名の正規化の改善**

---

## 10. 参考資料

### 10.1 関連ファイル

- `scripts/build_vector_db_by_category.py`: 既存のベクトルDB構築スクリプト
- `mcp_servers/recipe_rag/client.py`: RAGクライアント
- `mcp_servers/recipe_web.py`: Web検索クライアント
- `mcp_servers/recipe_mcp.py`: レシピMCPサーバー

### 10.2 データファイル

- `me2you/recipe_data.jsonl`: 既存のレシピデータ（旧フォーマット）
- `me2you/recipe_data_new.jsonl`: 新フォーマットのレシピデータ（生成予定）

---

## 11. 承認事項

この実装プランに基づいて実装を進める場合は、以下の承認が必要です：

1. ✅ データフォーマット設計の承認
2. ✅ URL埋め込み方法の承認
3. ✅ 実装ステップの承認
4. ✅ 移行手順の承認

承認後、実装作業を開始します。

