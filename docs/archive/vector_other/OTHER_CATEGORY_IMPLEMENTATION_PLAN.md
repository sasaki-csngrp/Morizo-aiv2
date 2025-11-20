# otherカテゴリ（その他）有効活用改修プラン

## 1. 目的と背景

### 1.1 目的
1. **otherカテゴリのレシピ検索・提案機能の実装**: 主菜・副菜・汁物と同様に、otherカテゴリのレシピを検索・提案できるようにする
2. **単体動作の実現**: 段階的提案ではなく、単体で動作する機能として実装
3. **category_detailの活用**: 麺もの、パスタ、丼物など、詳細カテゴリに基づく検索の実現

### 1.2 現状の問題点
- `other`カテゴリのベクトルDB（`recipe_vector_db_other_2`）は構築済みだが、検索機能が未実装
- ユーザーが「その他のレシピを教えて」「麺もののレシピを提案して」などのリクエストに対応できない
- RAG検索クライアントが主菜・副菜・汁物の3つのみ対応

### 1.3 前提条件
- `vector_data_sara.json`に`other`カテゴリのレシピが1043件存在
- `build_vector_db_by_category_2.py`で`other`カテゴリのベクトルDBが構築済み
- 処理ロジックは主菜・副菜・汁物と同じ方式を採用

---

## 2. 調査結果

### 2.1 otherカテゴリのデータ分析

#### 基本統計
- **総件数**: 1043件
- **ユニークなcategory_detailの種類数**: 60種類
- **空文字列のcategory_detail**: 198件

#### category_detailの分類

##### ご飯もの系（約300件以上）
| category_detail | 件数 |
|----------------|------|
| ご飯もの炊き込みご飯 | 66件 |
| ご飯ものチャーハン | 39件 |
| ご飯もの丼物豚丼 | 32件 |
| ご飯ものカレーライス | 30件 |
| ご飯もの丼物その他 | 24件 |
| ご飯ものおにぎり | 21件 |
| ご飯もの丼物そぼろ丼 | 21件 |
| ご飯ものオムライス | 20件 |
| ご飯もの雑炊＆リゾット | 16件 |
| ご飯もの寿司 | 14件 |
| ご飯ものその他 | 13件 |
| ご飯もの丼物海鮮丼 | 10件 |
| ご飯もの丼物中華丼 | 9件 |
| ご飯もの丼物牛丼 | 9件 |
| ご飯もの丼物親子丼 | 8件 |
| ご飯ものドリア | 7件 |
| ご飯もの丼物カツ丼 | 6件 |
| ご飯もの天津飯 | 6件 |
| ご飯ものパエリア | 5件 |
| ご飯ものハヤシライス | 4件 |
| ご飯もの丼物みそ丼 | 3件 |
| ご飯もの丼物天丼 | 1件 |

##### 麺もの系（約150件以上）
| category_detail | 件数 |
|----------------|------|
| 麺ものうどん | 42件 |
| 麺もの中華麺 | 32件 |
| 麺ものそうめん | 20件 |
| 麺もの焼きそば | 17件 |
| 麺ものそば | 11件 |
| 麺ものインスタントラーメン | 5件 |
| 麺もの冷たい麺 | 5件 |
| 麺ものビーフン | 4件 |

##### パスタ系（約150件以上）
| category_detail | 件数 |
|----------------|------|
| パスタその他 | 31件 |
| パスタトマト系 | 26件 |
| パスタ和風系 | 25件 |
| パスタクリーム系 | 20件 |
| パスタ冷製パスタ | 15件 |
| パスタナポリタン | 14件 |
| パスタカルボナーラ | 13件 |
| パスタミートソース | 10件 |
| パスタたらこ＆明太子 | 8件 |
| パスタペペロンチーノ | 4件 |

##### その他の分類
| category_detail | 件数 |
|----------------|------|
| ソース＆ドレッシング＆たれ | 53件 |
| 鍋＆ホットプレート | 37件 |
| 粉もの | 16件 |
| お店の味 | 18件 |
| おかずチヂミ | 15件 |
| おかずハンバーグ | 7件 |
| おせち料理 | 6件 |
| おかずチャーシュー＆角煮 | 4件 |
| おかず揚げ物フライ | 4件 |
| おかず揚げ物天ぷら | 4件 |
| おかずグラタン | 3件 |
| おかずおでん | 2件 |
| おかずシチュー | 2件 |
| おかず揚げ物からあげ | 2件 |
| おかず肉団子 | 2件 |
| おかずしゅうまい | 1件 |
| おかずしょうが焼き | 1件 |
| おかず揚げ物かき揚げ | 1件 |
| おかず肉巻き | 1件 |

### 2.2 想定されるユーザーリクエスト例

#### カテゴリ全体のリクエスト
- 「その他のレシピを教えて」
- 「その他のレシピを提案して」

#### ご飯もの系のリクエスト
- 「丼のレシピを教えて」
- 「チャーハンのレシピを提案して」
- 「カレーライスのレシピを教えて」
- 「おにぎりのレシピを提案して」

#### 麺もの系のリクエスト
- 「麺もののレシピを教えて」
- 「うどんのレシピを提案して」
- 「焼きそばのレシピを教えて」
- 「そうめんのレシピを提案して」

#### パスタ系のリクエスト
- 「パスタのレシピを提案して」
- 「トマトパスタのレシピを教えて」
- 「カルボナーラのレシピを提案して」

---

## 3. 改修内容

### 3.1 修正箇所1: `mcp_servers/recipe_rag/client.py`

#### 修正内容

##### 3.1.1 `__init__()`メソッド
- `other`カテゴリのベクトルDBパスを環境変数から取得する処理を追加

```python
# 環境変数から4つのChromaDBのパスを取得
self.vector_db_path_main = os.getenv("CHROMA_PERSIST_DIRECTORY_MAIN", "./recipe_vector_db_main")
self.vector_db_path_sub = os.getenv("CHROMA_PERSIST_DIRECTORY_SUB", "./recipe_vector_db_sub")
self.vector_db_path_soup = os.getenv("CHROMA_PERSIST_DIRECTORY_SOUP", "./recipe_vector_db_soup")
self.vector_db_path_other = os.getenv("CHROMA_PERSIST_DIRECTORY_OTHER", "./recipe_vector_db_other_2")  # 追加
```

##### 3.1.2 `_get_vectorstores()`メソッド
- `other`カテゴリのベクトルストアを追加

```python
self._vectorstores = {
    "main": Chroma(...),
    "sub": Chroma(...),
    "soup": Chroma(...),
    "other": Chroma(  # 追加
        persist_directory=self.vector_db_path_other,
        embedding_function=self.embeddings
    )
}
```

##### 3.1.3 `_get_search_engines()`メソッド
- `other`カテゴリの検索エンジンを追加

```python
self._search_engines = {
    "main": RecipeSearchEngine(vectorstores["main"]),
    "sub": RecipeSearchEngine(vectorstores["sub"]),
    "soup": RecipeSearchEngine(vectorstores["soup"]),
    "other": RecipeSearchEngine(vectorstores["other"])  # 追加
}
```

##### 3.1.4 `search_candidates()`メソッド
- `category`パラメータに`"other"`を追加し、`other`カテゴリに対応

```python
async def search_candidates(
    self,
    ingredients: List[str],
    menu_type: str,
    category: str,  # "main", "sub", "soup", "other" に拡張
    ...
):
    # 適切なベクトルストアを選択
    if category not in ["main", "sub", "soup", "other"]:
        raise ValueError(f"Invalid category: {category}")
    
    search_engine = self._get_search_engines()[category]
    ...
```

#### 修正理由
- `other`カテゴリのベクトルDB検索機能を有効化するため

#### 修正の影響
- `other`カテゴリのRAG検索が可能になる
- 既存の主菜・副菜・汁物の検索機能には影響なし

---

### 3.2 修正箇所2: `services/llm/request_analyzer.py`

#### 修正内容

##### 3.2.1 `_detect_pattern()`メソッド
- `other`カテゴリの検出ロジックを追加

```python
def _detect_pattern(
    self, 
    request: str, 
    sse_session_id: str, 
    session_context: dict
) -> str:
    # 優先度1-3: 既存の処理（主菜・副菜・汁物）...
    
    # 優先度3.5: otherカテゴリの検出（主菜・副菜・汁物の後、献立生成の前）
    if self._is_other_category_request(request):
        return "other"
    
    # 優先度4: 在庫操作
    if self._is_inventory_operation(request):
        return "inventory"
    
    # 優先度5: 献立生成
    if "献立" in request or "メニュー" in request or "menu" in request.lower():
        return "menu"
    
    # 優先度6: その他
    return "other"

def _is_other_category_request(self, request: str) -> bool:
    """otherカテゴリのリクエストかどうかを判定"""
    request_lower = request.lower()
    
    # カテゴリ全体のキーワード
    if any(keyword in request for keyword in ["その他のレシピ", "その他を", "その他が", "その他の"]):
        return True
    
    # ご飯もの系のキーワード
    if any(keyword in request for keyword in [
        "丼のレシピ", "丼を", "丼が", "丼物",
        "チャーハン", "カレーライス", "おにぎり", "オムライス",
        "雑炊", "リゾット", "寿司", "ドリア", "パエリア", "ハヤシライス"
    ]):
        return True
    
    # 麺もの系のキーワード
    if any(keyword in request for keyword in [
        "麺もの", "麺のレシピ", "麺を", "麺が",
        "うどん", "そば", "そうめん", "焼きそば",
        "中華麺", "ラーメン", "ビーフン"
    ]):
        return True
    
    # パスタ系のキーワード
    if any(keyword in request for keyword in [
        "パスタ", "カルボナーラ", "ミートソース", "ナポリタン",
        "ペペロンチーノ", "たらこパスタ", "明太子パスタ"
    ]):
        return True
    
    # その他のキーワード
    if any(keyword in request for keyword in [
        "ソース", "ドレッシング", "たれ",
        "鍋", "ホットプレート", "粉もの", "チヂミ",
        "ハンバーグ", "グラタン", "おでん", "シチュー"
    ]):
        return True
    
    return False
```

#### 修正理由
- ユーザーリクエストから`other`カテゴリを正確に検出するため

#### 修正の影響
- `other`カテゴリのリクエストを正しく認識できるようになる
- 既存の主菜・副菜・汁物の検出ロジックには影響なし（優先度が適切に設定されているため）

---

### 3.3 修正箇所3: `mcp_servers/recipe_mcp.py`

#### 修正内容

##### 3.3.1 `generate_proposals()`関数
- `category`パラメータに`"other"`を追加し、`other`カテゴリの処理を実装

```python
@mcp.tool()
async def generate_proposals(
    inventory_items: List[str],
    user_id: str,
    category: str = "main",  # "main", "sub", "soup", "other" に拡張
    menu_type: str = "",
    main_ingredient: Optional[str] = None,
    used_ingredients: List[str] = None,
    excluded_recipes: List[str] = None,
    menu_category: str = "japanese",
    sse_session_id: str = None,
    token: str = None
) -> Dict[str, Any]:
    """
    汎用提案メソッド（主菜・副菜・汁物・その他対応）
    
    Args:
        category: "main", "sub", "soup", "other"
        ...
    """
    # otherカテゴリの場合の処理
    if category == "other":
        # used_ingredientsは使用しない（単体動作のため）
        used_ingredients = None
    
    # 既存の処理（LLMとRAGを並列実行）
    llm_task = llm_client.generate_candidates(
        inventory_items=inventory_items,
        menu_type=menu_type,
        category=category,
        main_ingredient=main_ingredient,
        used_ingredients=used_ingredients,
        excluded_recipes=all_excluded,
        count=2
    )
    rag_task = rag_client.search_candidates(
        ingredients=inventory_items,
        menu_type=menu_type,
        category=category,  # "other"も対応
        main_ingredient=main_ingredient,
        used_ingredients=used_ingredients,
        excluded_recipes=all_excluded,
        limit=3
    )
    ...
```

#### 修正理由
- `other`カテゴリのレシピ提案機能を有効化するため

#### 修正の影響
- `other`カテゴリのレシピ提案が可能になる
- 既存の主菜・副菜・汁物の提案機能には影響なし

---

### 3.4 修正箇所4: 環境変数の追加

#### 修正内容

##### 3.4.1 `.env`ファイル（または`.env.example`）
- `CHROMA_PERSIST_DIRECTORY_OTHER`環境変数を追加

```bash
# ベクトルDBパス設定
CHROMA_PERSIST_DIRECTORY_MAIN=./recipe_vector_db_main_2
CHROMA_PERSIST_DIRECTORY_SUB=./recipe_vector_db_sub_2
CHROMA_PERSIST_DIRECTORY_SOUP=./recipe_vector_db_soup_2
CHROMA_PERSIST_DIRECTORY_OTHER=./recipe_vector_db_other_2  # 追加
```

#### 修正理由
- `other`カテゴリのベクトルDBパスを環境変数で管理可能にするため

#### 修正の影響
- 環境変数でベクトルDBのパスを柔軟に設定可能になる
- 既存の環境変数には影響なし

---

### 3.5 修正箇所5: `category_detail`に基づく検索の最適化（オプション）

#### 修正内容

##### 3.5.1 `mcp_servers/recipe_rag/search.py`の`RecipeSearchEngine`クラス
- `other`カテゴリ検索時に`category_detail`を考慮した検索を実装

```python
async def search_similar_recipes(
    self,
    ingredients: List[str],
    menu_type: str,
    excluded_recipes: List[str] = None,
    limit: int = 5,
    main_ingredient: str = None,
    category_detail_keyword: str = None  # 追加: "麺もの", "パスタ", "丼"など
) -> List[Dict[str, Any]]:
    """
    在庫食材に基づく類似レシピ検索
    
    Args:
        ...
        category_detail_keyword: category_detailのキーワード（otherカテゴリ用）
    """
    # category_detail_keywordがある場合、検索クエリに追加
    if category_detail_keyword:
        query = f"{category_detail_keyword} {' '.join(normalized_ingredients)} {menu_type}"
    else:
        query = f"{' '.join(normalized_ingredients)} {menu_type}"
    
    # 検索実行
    results = self.vectorstore.similarity_search(query, k=limit * 4)
    
    # category_detail_keywordがある場合、フィルタリング
    if category_detail_keyword:
        filtered_results = []
        for result in results:
            metadata = result.metadata
            category_detail = metadata.get('category_detail', '')
            if category_detail_keyword in category_detail:
                filtered_results.append(result)
            if len(filtered_results) >= limit:
                break
        results = filtered_results[:limit]
    ...
```

##### 3.5.2 `services/llm/request_analyzer.py`の拡張
- リクエストから`category_detail`のキーワードを抽出

```python
def _extract_category_detail_keyword(self, request: str) -> Optional[str]:
    """リクエストからcategory_detailのキーワードを抽出"""
    # 麺もの系
    if "うどん" in request:
        return "麺ものうどん"
    elif "そば" in request and "パスタ" not in request:
        return "麺ものそば"
    elif "そうめん" in request:
        return "麺ものそうめん"
    elif "焼きそば" in request:
        return "麺もの焼きそば"
    elif "中華麺" in request or "ラーメン" in request:
        return "麺もの中華麺"
    
    # パスタ系
    elif "カルボナーラ" in request:
        return "パスタカルボナーラ"
    elif "ミートソース" in request:
        return "パスタミートソース"
    elif "ナポリタン" in request:
        return "パスタナポリタン"
    elif "トマト" in request and "パスタ" in request:
        return "パスタトマト系"
    elif "パスタ" in request:
        return "パスタ"  # 汎用的なパスタ
    
    # ご飯もの系
    elif "丼" in request:
        return "ご飯もの丼物"
    elif "チャーハン" in request:
        return "ご飯ものチャーハン"
    elif "カレー" in request:
        return "ご飯ものカレーライス"
    elif "おにぎり" in request:
        return "ご飯ものおにぎり"
    
    return None
```

#### 修正理由
- より精度の高い検索結果を提供するため（例: 「うどんのレシピ」→`category_detail`が「麺ものうどん」のレシピを優先）

#### 修正の影響
- 検索精度が向上する
- 実装が複雑になるため、最初はオプションとして実装し、後から有効化することも可能

---

## 4. 実装順序

### Phase 1: 基本機能の実装（必須）
1. 修正箇所1: `mcp_servers/recipe_rag/client.py`の修正
2. 修正箇所2: `services/llm/request_analyzer.py`の修正
3. 修正箇所3: `mcp_servers/recipe_mcp.py`の修正
4. 修正箇所4: 環境変数の追加

### Phase 2: 検索精度の向上（オプション）
5. 修正箇所5: `category_detail`に基づく検索の最適化

---

## 5. テスト計画

### 5.1 単体テスト

#### テストケース1: RAG検索の動作確認
- `other`カテゴリのベクトルDBからレシピを検索できることを確認
- 検索結果に`url`が含まれていることを確認

#### テストケース2: リクエスト分析の動作確認
- 「その他のレシピを教えて」→`other`パターンが返されることを確認
- 「麺もののレシピを提案して」→`other`パターンが返されることを確認
- 「パスタのレシピを教えて」→`other`パターンが返されることを確認
- 「丼のレシピを提案して」→`other`パターンが返されることを確認

#### テストケース3: レシピ提案の動作確認
- `generate_proposals(category="other")`が正常に動作することを確認
- 提案結果に`other`カテゴリのレシピが含まれていることを確認

### 5.2 統合テスト

#### テストケース1: エンドツーエンドの動作確認
1. ユーザーが「その他のレシピを教えて」と入力
2. `RequestAnalyzer`が`other`パターンを返す
3. `generate_proposals(category="other")`が呼び出される
4. RAG検索が`other`カテゴリのベクトルDBから検索を実行
5. レシピ提案が正常に返される

#### テストケース2: category_detailに基づく検索（Phase 2実装時）
1. ユーザーが「うどんのレシピを教えて」と入力
2. `category_detail_keyword`が「麺ものうどん」として抽出される
3. RAG検索が`category_detail`を考慮して検索を実行
4. うどんのレシピが優先的に返される

---

## 6. 注意事項

### 6.1 既存機能への影響
- 主菜・副菜・汁物の既存機能には影響しない
- `other`カテゴリは単体動作のため、段階的提案のロジックには含めない

### 6.2 パフォーマンス
- ベクトルDBが1つ増えるため、初期化時間が若干増加する可能性がある
- 検索処理は並列実行されるため、レスポンス時間への影響は最小限

### 6.3 データ整合性
- `recipe_vector_db_other_2`が存在することを前提とする
- ベクトルDBが存在しない場合のエラーハンドリングを実装する

---

## 7. 参考資料

### 7.1 関連ファイル
- `scripts/build_vector_db_by_category_2.py`: ベクトルDB構築スクリプト
- `mcp_servers/recipe_rag/client.py`: RAG検索クライアント
- `services/llm/request_analyzer.py`: リクエスト分析クラス
- `mcp_servers/recipe_mcp.py`: レシピMCPサーバー

### 7.2 データソース
- `me2you/vector_data_sara.json`: レシピデータソース（1043件の`other`カテゴリレシピを含む）

---

## 8. 改修後の動作例

### 8.1 ユーザーリクエスト例1: 「その他のレシピを教えて」
```
ユーザー: その他のレシピを教えて
システム: [otherカテゴリのレシピを5件提案]
```

### 8.2 ユーザーリクエスト例2: 「麺もののレシピを提案して」
```
ユーザー: 麺もののレシピを提案して
システム: [麺もの系のレシピ（うどん、そば、そうめんなど）を5件提案]
```

### 8.3 ユーザーリクエスト例3: 「パスタのレシピを教えて」
```
ユーザー: パスタのレシピを教えて
システム: [パスタ系のレシピ（トマト系、クリーム系など）を5件提案]
```

### 8.4 ユーザーリクエスト例4: 「丼のレシピを提案して」
```
ユーザー: 丼のレシピを提案して
システム: [丼物系のレシピ（豚丼、牛丼、親子丼など）を5件提案]
```

---

## 9. 今後の拡張案

### 9.1 category_detailの詳細マッピング
- より詳細な`category_detail`マッピングを実装し、検索精度を向上

### 9.2 複数カテゴリの組み合わせ検索
- 「麺ものとパスタのレシピを教えて」などの複数カテゴリ検索に対応

### 9.3 人気レシピの優先表示
- `category_detail`ごとの人気レシピを優先的に表示

---

## 10. 承認待ち項目

このプランに基づいて実装を進める前に、以下の確認が必要です：

1. ✅ 調査結果の確認（`other`カテゴリの`category_detail`の種類と件数）
2. ⏳ 改修プランの承認
3. ⏳ 実装順序の確認（Phase 1のみか、Phase 2も含めるか）
4. ⏳ テスト計画の確認

承認いただけましたら、実装作業に着手いたします。

