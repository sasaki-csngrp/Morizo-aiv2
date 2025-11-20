# recipe_mcp.py リファクタリングプラン

## 現状の問題点

### 1. 関数の肥大化
- `generate_proposals`: 258行（479-715行）
- `search_recipe_from_web`: 210行（245-454行）
- `search_menu_from_rag_with_history`: 108行（117-224行）

### 2. 責務の混在
- エラーハンドリング、ログ出力、データ変換、ビジネスロジックが同一関数内に混在

### 3. 重複コード
- 認証クライアント取得の重複
- ログ出力パターンの重複
- エラーハンドリングパターンの重複

### 4. 複雑な条件分岐
- `search_recipe_from_web`内の`menu_source`判定ロジック（303-313行）
- 単一カテゴリ/一括提案の分岐（351-445行）

### 5. 可読性の低下
- 過剰なデバッグログ（`generate_proposals`内に多数）
- ネストが深い

---

## リファクタリング案

### 案1: ヘルパー関数への抽出（段階的・低リスク）

**目的**: 大きな関数を小さな関数に分割し、可読性と保守性を向上

**修正箇所**:
- `mcp_servers/recipe_mcp.py`内の各関数

**修正内容**:

#### 1.1 認証処理の共通化
```python
async def _get_authenticated_client_safe(user_id: str, token: str = None) -> Client:
    """
    認証済みクライアントを安全に取得（エラーハンドリングとログを含む）
    
    Args:
        user_id: ユーザーID
        token: 認証トークン
    
    Returns:
        Client: 認証済みSupabaseクライアント
    
    Raises:
        Exception: 認証に失敗した場合
    """
    logger.debug(f"🔐 [RECIPE] Getting authenticated client for user_id={user_id}")
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [RECIPE] Authenticated client created successfully for user: {user_id}")
        return client
    except Exception as e:
        logger.error(f"❌ [RECIPE] Failed to get authenticated client: {e}")
        raise
```

**適用箇所**:
- `get_recipe_history_for_user` (63行目)
- `generate_menu_plan_with_history` (102行目)
- `search_menu_from_rag_with_history` (154行目)
- `generate_proposals` (497行目)

#### 1.2 データ変換ロジックの抽出

##### 1.2.1 RAGメニュー結果のフォーマット
```python
def _format_rag_menu_result(
    menu_result: Dict[str, Any],
    inventory_items: List[str]
) -> Dict[str, Any]:
    """
    RAG検索結果を統一フォーマットに変換
    
    Args:
        menu_result: RAG検索結果（selectedキーを含む）
        inventory_items: 在庫食材リスト
    
    Returns:
        Dict[str, Any]: フォーマット済みデータ
    """
    selected_menu = menu_result.get("selected", {})
    
    main_dish_data = selected_menu.get("main_dish", {})
    side_dish_data = selected_menu.get("side_dish", {})
    soup_data = selected_menu.get("soup", {})
    
    main_dish_ingredients = main_dish_data.get("ingredients", []) if isinstance(main_dish_data, dict) else []
    side_dish_ingredients = side_dish_data.get("ingredients", []) if isinstance(side_dish_data, dict) else []
    soup_ingredients = soup_data.get("ingredients", []) if isinstance(soup_data, dict) else []
    
    ingredients_used = []
    ingredients_used.extend(main_dish_ingredients)
    ingredients_used.extend(side_dish_ingredients)
    ingredients_used.extend(soup_ingredients)
    ingredients_used = list(set(ingredients_used))
    
    return {
        "main_dish": main_dish_data.get("title", "") if isinstance(main_dish_data, dict) else str(main_dish_data),
        "side_dish": side_dish_data.get("title", "") if isinstance(side_dish_data, dict) else str(side_dish_data),
        "soup": soup_data.get("title", "") if isinstance(soup_data, dict) else str(soup_data),
        "main_dish_ingredients": main_dish_ingredients,
        "side_dish_ingredients": side_dish_ingredients,
        "soup_ingredients": soup_ingredients,
        "ingredients_used": ingredients_used
    }
```

**適用箇所**:
- `search_menu_from_rag_with_history` (190-215行を置き換え)

##### 1.2.2 Web検索結果の分類
```python
def _categorize_web_search_results(
    results: List[Dict[str, Any]],
    recipe_titles: List[str],
    menu_categories: List[str],
    menu_source: str
) -> Dict[str, Any]:
    """
    Web検索結果をllm_menu/rag_menu構造に分類
    
    Args:
        results: 検索結果のリスト
        recipe_titles: レシピタイトルのリスト
        menu_categories: カテゴリのリスト
        menu_source: 検索元（llm, rag, mixed）
    
    Returns:
        Dict[str, Any]: 分類済み結果
    """
    categorized_results = {
        "llm_menu": {
            "main_dish": {"title": "", "recipes": []},
            "side_dish": {"title": "", "recipes": []},
            "soup": {"title": "", "recipes": []}
        },
        "rag_menu": {
            "main_dish": {"title": "", "recipes": []},
            "side_dish": {"title": "", "recipes": []},
            "soup": {"title": "", "recipes": []}
        }
    }
    
    for i, result in enumerate(results):
        if isinstance(result, Exception) or not result.get("success"):
            continue
        
        recipes = result.get("data", [])
        category = menu_categories[i] if menu_categories and i < len(menu_categories) else "main_dish"
        source = "rag_menu" if (menu_source == "rag" or (menu_source == "mixed" and i >= len(recipe_titles) // 2)) else "llm_menu"
        
        categorized_results[source][category] = {
            "title": recipe_titles[i],
            "recipes": recipes
        }
    
    return categorized_results
```

**適用箇所**:
- `search_recipe_from_web` (402-445行を置き換え)

#### 1.3 検索ロジックの分離
```python
async def _search_single_recipe_with_rag_fallback(
    title: str,
    index: int,
    rag_results: Dict[str, Dict[str, Any]],
    menu_source: str,
    num_results: int
) -> Dict[str, Any]:
    """
    単一の料理名でレシピ検索（RAG検索結果のURLを優先）
    
    Args:
        title: レシピタイトル
        index: インデックス（menu_source判定に使用）
        rag_results: RAG検索結果の辞書
        menu_source: 検索元（llm, rag, mixed）
        num_results: 取得結果数
    
    Returns:
        Dict[str, Any]: 検索結果
    """
    # RAG検索結果からURLを取得（既に取得済みの場合）
    if rag_results and title in rag_results:
        rag_result = rag_results[title]
        rag_url = rag_result.get('url', '')
        if rag_url:
            logger.debug(f"🔍 [RECIPE] Found URL from RAG search for '{title}': {rag_url}")
            return {
                "success": True,
                "data": [{
                    "title": title,
                    "url": rag_url,
                    "source": "vector_db",
                    "description": rag_result.get('category_detail', ''),
                    "site": "cookpad.com" if "cookpad.com" in rag_url else "other"
                }],
                "title": title,
                "count": 1
            }
    
    # URLがない場合のみWeb検索APIを呼び出す
    effective_source = menu_source
    if menu_source == "mixed":
        total_count = len(recipe_titles) if 'recipe_titles' in locals() else 0
        effective_source = "llm" if index < total_count / 2 else "rag"
    
    client = get_search_client(menu_source=effective_source)
    recipes = await client.search_recipes(title, num_results)
    
    prioritized_recipes = prioritize_recipes(recipes)
    filtered_recipes = filter_recipe_results(prioritized_recipes)
    
    return {
        "success": True,
        "data": filtered_recipes,
        "title": title,
        "count": len(filtered_recipes)
    }
```

**適用箇所**:
- `search_recipe_from_web` (276-345行を置き換え)

#### 1.4 ログ出力の共通化
```python
def _log_function_start(func_name: str, params: Dict[str, Any]) -> None:
    """
    関数開始時のログ出力
    
    Args:
        func_name: 関数名
        params: パラメータの辞書
    """
    logger.info(f"🔧 [RECIPE] Starting {func_name}")
    for key, value in params.items():
        if key == "token" and value:
            logger.debug(f"  - {key}: ***")
        else:
            logger.debug(f"  - {key}: {value}")


def _log_function_end(func_name: str, result: Dict[str, Any]) -> None:
    """
    関数終了時のログ出力
    
    Args:
        func_name: 関数名
        result: 結果の辞書
    """
    if result.get("success"):
        logger.info(f"✅ [RECIPE] {func_name} completed successfully")
    else:
        logger.error(f"❌ [RECIPE] {func_name} failed: {result.get('error')}")
```

**適用箇所**:
- 全MCPツール関数

**修正の理由**:
- 関数を小さくして可読性を向上
- 重複を削減
- テストしやすくする
- 既存のMCPツールインターフェースは維持

**修正の影響**:
- 既存のAPIインターフェースは変更なし
- 内部実装のみ変更
- 段階的に適用可能

---

### 案2: サービス層への分離（中規模・中リスク）

**目的**: ビジネスロジックをサービス層に分離し、MCPツール層を薄くする

**修正箇所**:
- 新規: `mcp_servers/services/recipe_service.py`
- 修正: `mcp_servers/recipe_mcp.py`

**修正内容**:

#### 2.1 RecipeServiceクラスの作成

```python
# mcp_servers/services/recipe_service.py

from typing import Dict, Any, List, Optional
from supabase import Client
from mcp_servers.recipe_llm import RecipeLLM
from mcp_servers.recipe_rag import RecipeRAGClient
from config.loggers import GenericLogger

class RecipeService:
    """レシピ関連のビジネスロジックを扱うサービス層"""
    
    def __init__(self):
        self.llm_client = RecipeLLM()
        self.rag_client = RecipeRAGClient()
        self.logger = GenericLogger("mcp", "recipe_service", initialize_logging=False)
    
    async def generate_proposals(
        self,
        client: Client,
        inventory_items: List[str],
        category: str,
        menu_type: str = "",
        main_ingredient: Optional[str] = None,
        used_ingredients: List[str] = None,
        excluded_recipes: List[str] = None,
        category_detail_keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        汎用提案メソッド（主菜・副菜・汁物・その他対応）
        
        Args:
            client: 認証済みSupabaseクライアント
            inventory_items: 在庫食材リスト
            category: "main", "sub", "soup", "other"
            menu_type: 献立タイプ
            main_ingredient: 主食材
            used_ingredients: 使用済み食材
            excluded_recipes: 除外レシピ
            category_detail_keyword: カテゴリ詳細キーワード
        
        Returns:
            Dict[str, Any]: 提案結果
        """
        # 現在のgenerate_proposalsのロジックをここに移動
        # （認証処理は除く）
        pass
    
    async def search_recipes_from_web(
        self,
        recipe_titles: List[str],
        num_results: int = 5,
        menu_categories: List[str] = None,
        menu_source: str = "mixed",
        rag_results: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Web検索によるレシピ検索
        
        Args:
            recipe_titles: 検索するレシピタイトルのリスト
            num_results: 各料理名あたりの取得結果数
            menu_categories: 料理名の分類リスト
            menu_source: 検索元（llm, rag, mixed）
            rag_results: RAG検索結果の辞書
        
        Returns:
            Dict[str, Any]: 分類された検索結果
        """
        # 現在のsearch_recipe_from_webのロジックをここに移動
        pass
    
    async def search_menu_from_rag(
        self,
        inventory_items: List[str],
        menu_type: str = "",
        excluded_recipes: List[str] = None
    ) -> Dict[str, Any]:
        """
        RAG検索による伝統的な献立タイトル生成
        
        Args:
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
            excluded_recipes: 除外するレシピタイトル
        
        Returns:
            Dict[str, Any]: 献立結果
        """
        # 現在のsearch_menu_from_rag_with_historyのロジックをここに移動
        # （認証処理は除く）
        pass
```

#### 2.2 MCPツール関数の簡素化

```python
# mcp_servers/recipe_mcp.py

from mcp_servers.services.recipe_service import RecipeService

recipe_service = RecipeService()

@mcp.tool()
async def generate_proposals(
    inventory_items: List[str],
    user_id: str,
    category: str = "main",
    menu_type: str = "",
    main_ingredient: Optional[str] = None,
    used_ingredients: List[str] = None,
    excluded_recipes: List[str] = None,
    menu_category: str = "japanese",
    sse_session_id: str = None,
    token: str = None,
    category_detail_keyword: Optional[str] = None
) -> Dict[str, Any]:
    """
    汎用提案メソッド（主菜・副菜・汁物・その他対応）
    """
    try:
        client = _get_authenticated_client_safe(user_id, token)
        return await recipe_service.generate_proposals(
            client=client,
            inventory_items=inventory_items,
            category=category,
            menu_type=menu_type,
            main_ingredient=main_ingredient,
            used_ingredients=used_ingredients,
            excluded_recipes=excluded_recipes,
            category_detail_keyword=category_detail_keyword
        )
    except Exception as e:
        logger.error(f"❌ [RECIPE] Error in generate_proposals: {e}")
        return {"success": False, "error": str(e)}
```

**修正の理由**:
- 責務の明確化（MCPツール層は薄く、ビジネスロジックはサービス層）
- 再利用性の向上
- テスト容易性の向上

**修正の影響**:
- 新規ファイル追加が必要
- 既存のMCPツールインターフェースは維持
- 段階的移行が可能（まず`generate_proposals`から）

---

### 案3: データクラス/モデルの導入（中規模・中リスク）

**目的**: データ構造を明確化し、型安全性を向上

**修正箇所**:
- 新規: `mcp_servers/models/recipe_models.py`
- 修正: `mcp_servers/recipe_mcp.py`

**修正内容**:

#### 3.1 データモデルの定義

```python
# mcp_servers/models/recipe_models.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class RecipeProposal:
    """レシピ提案のデータモデル"""
    title: str
    ingredients: List[str]
    source: str  # "llm" or "rag"
    url: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            "title": self.title,
            "ingredients": self.ingredients,
            "source": self.source
        }
        if self.url:
            result["url"] = self.url
        if self.description:
            result["description"] = self.description
        return result

@dataclass
class MenuResult:
    """献立結果のデータモデル"""
    main_dish: str
    side_dish: str
    soup: str
    main_dish_ingredients: List[str]
    side_dish_ingredients: List[str]
    soup_ingredients: List[str]
    ingredients_used: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "main_dish": self.main_dish,
            "side_dish": self.side_dish,
            "soup": self.soup,
            "main_dish_ingredients": self.main_dish_ingredients,
            "side_dish_ingredients": self.side_dish_ingredients,
            "soup_ingredients": self.soup_ingredients,
            "ingredients_used": self.ingredients_used
        }

@dataclass
class WebSearchResult:
    """Web検索結果のデータモデル"""
    title: str
    url: str
    source: str  # "vector_db" or "web"
    description: Optional[str] = None
    site: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            "title": self.title,
            "url": self.url,
            "source": self.source
        }
        if self.description:
            result["description"] = self.description
        if self.site:
            result["site"] = self.site
        return result
```

#### 3.2 データ変換の明確化

```python
# mcp_servers/recipe_mcp.py 内で使用

def _convert_rag_result_to_menu_result(
    rag_result: Dict[str, Any],
    inventory_items: List[str]
) -> MenuResult:
    """
    RAG検索結果をMenuResultに変換
    
    Args:
        rag_result: RAG検索結果
        inventory_items: 在庫食材リスト
    
    Returns:
        MenuResult: 変換済みデータモデル
    """
    selected_menu = rag_result.get("selected", {})
    
    main_dish_data = selected_menu.get("main_dish", {})
    side_dish_data = selected_menu.get("side_dish", {})
    soup_data = selected_menu.get("soup", {})
    
    main_dish_ingredients = main_dish_data.get("ingredients", []) if isinstance(main_dish_data, dict) else []
    side_dish_ingredients = side_dish_data.get("ingredients", []) if isinstance(side_dish_data, dict) else []
    soup_ingredients = soup_data.get("ingredients", []) if isinstance(soup_data, dict) else []
    
    ingredients_used = list(set(main_dish_ingredients + side_dish_ingredients + soup_ingredients))
    
    return MenuResult(
        main_dish=main_dish_data.get("title", "") if isinstance(main_dish_data, dict) else str(main_dish_data),
        side_dish=side_dish_data.get("title", "") if isinstance(side_dish_data, dict) else str(side_dish_data),
        soup=soup_data.get("title", "") if isinstance(soup_data, dict) else str(soup_data),
        main_dish_ingredients=main_dish_ingredients,
        side_dish_ingredients=side_dish_ingredients,
        soup_ingredients=soup_ingredients,
        ingredients_used=ingredients_used
    )
```

**修正の理由**:
- データ構造の明確化
- 型安全性の向上
- バグの早期発見

**修正の影響**:
- 新規ファイル追加が必要
- 既存のAPIインターフェースは維持（内部でモデルを使用）
- 段階的移行が可能

---

### 案4: デコレータパターンの導入（小規模・低リスク）

**目的**: 共通処理（認証、ログ、エラーハンドリング）をデコレータで統一

**修正箇所**:
- 新規: `mcp_servers/decorators.py`
- 修正: `mcp_servers/recipe_mcp.py`

**修正内容**:

#### 4.1 デコレータの作成

```python
# mcp_servers/decorators.py

from functools import wraps
from typing import Callable, Any
from supabase import Client
from mcp_servers.utils import get_authenticated_client
from config.loggers import GenericLogger

logger = GenericLogger("mcp", "recipe_decorators", initialize_logging=False)

def authenticated_tool(func: Callable) -> Callable:
    """
    認証処理を自動化するデコレータ
    
    関数の引数からuser_idとtokenを取得し、認証済みクライアントを取得して
    client引数として関数に渡す
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
        token = kwargs.get('token')
        
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"🔐 [RECIPE] Authenticated client created for user: {user_id}")
            kwargs['client'] = client
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ [RECIPE] Authentication failed: {e}")
            return {"success": False, "error": str(e)}
    
    return wrapper

def logged_tool(func: Callable) -> Callable:
    """
    ログ出力を自動化するデコレータ
    
    関数の開始・終了・エラーを自動的にログ出力
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"🔧 [RECIPE] Starting {func_name}")
        logger.debug(f"🔍 [RECIPE] Parameters: {kwargs}")
        
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, dict) and result.get("success"):
                logger.info(f"✅ [RECIPE] {func_name} completed successfully")
            else:
                logger.warning(f"⚠️ [RECIPE] {func_name} returned non-success result")
            return result
        except Exception as e:
            logger.error(f"❌ [RECIPE] {func_name} failed: {e}")
            raise
    
    return wrapper

def error_handled_tool(func: Callable) -> Callable:
    """
    エラーハンドリングを統一するデコレータ
    
    例外をキャッチして統一フォーマットで返す
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ [RECIPE] Error in {func.__name__}: {e}")
            import traceback
            logger.error(f"❌ [RECIPE] Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
    
    return wrapper
```

#### 4.2 既存関数への適用

```python
# mcp_servers/recipe_mcp.py

from mcp_servers.decorators import authenticated_tool, logged_tool, error_handled_tool

@mcp.tool()
@error_handled_tool
@logged_tool
@authenticated_tool
async def generate_proposals(
    inventory_items: List[str],
    user_id: str,
    client: Client,  # デコレータが自動的に注入
    category: str = "main",
    # ... 他のパラメータ
) -> Dict[str, Any]:
    """
    汎用提案メソッド（主菜・副菜・汁物・その他対応）
    """
    # 認証処理とログ出力はデコレータが自動的に処理
    # ビジネスロジックのみ記述
    # ...
```

**修正の理由**:
- 横断的関心事の分離
- コードの重複削減
- 一貫性の向上

**修正の影響**:
- 新規ファイル追加が必要
- 既存のMCPツールインターフェースは維持
- 段階的適用が可能

---

## 推奨アプローチ

**段階的リファクタリング（案1 → 案4 → 案2の順）**

### 第1段階: 案1（ヘルパー関数への抽出）
- **リスク**: 低
- **効果**: 可読性向上、重複削減
- **期間**: 短期（1-2日）
- **実施内容**:
  1. `_get_authenticated_client_safe`の作成と適用
  2. `_format_rag_menu_result`の作成と適用
  3. `_categorize_web_search_results`の作成と適用
  4. `_search_single_recipe_with_rag_fallback`の作成と適用
  5. ログ出力の共通化（オプション）

### 第2段階: 案4（デコレータパターン）
- **リスク**: 低
- **効果**: 共通処理の統一
- **期間**: 短期（1日）
- **実施内容**:
  1. `mcp_servers/decorators.py`の作成
  2. デコレータの実装
  3. 既存関数への段階的適用

### 第3段階: 案2（サービス層への分離）
- **リスク**: 中
- **効果**: アーキテクチャの改善
- **期間**: 中期（3-5日）
- **実施内容**:
  1. `mcp_servers/services/recipe_service.py`の作成
  2. `RecipeService`クラスの実装
  3. ビジネスロジックの移行
  4. MCPツール関数の簡素化

### オプション: 案3（データモデルの導入）
- **リスク**: 中
- **効果**: 型安全性の向上
- **期間**: 中期（2-3日）
- **実施タイミング**: 案2と並行または案2の後

---

## ファイル情報

- **対象ファイル**: `mcp_servers/recipe_mcp.py`
- **現在の行数**: 722行
- **主要な肥大化関数**:
  - `generate_proposals`: 258行（479-715行）
  - `search_recipe_from_web`: 210行（245-454行）
  - `search_menu_from_rag_with_history`: 108行（117-224行）

---

## 注意事項

### 承認制の遵守
- **修正作業は必ず承認後に実施**
- 各段階で承認を得てから次の段階に進む

### デグレード対策
- **既存のMCPツールインターフェースは変更しない**
- 内部実装のみ変更し、外部APIは維持
- 各段階で動作確認を実施

### 段階的実施
- **一度に全てを変更せず、段階的に実施**
- 各段階でコミットし、問題があればロールバック可能にする

### テスト
- **各段階で動作確認を実施**
- 既存のテストケースが通ることを確認
- 必要に応じて新規テストを追加

### ログの整理
- **過剰なデバッグログを整理**
- 重要な情報のみログ出力
- ログレベルを適切に設定

---

## 実装チェックリスト

### 第1段階: ヘルパー関数への抽出
- [ ] `_get_authenticated_client_safe`の実装
- [ ] `_format_rag_menu_result`の実装
- [ ] `_categorize_web_search_results`の実装
- [ ] `_search_single_recipe_with_rag_fallback`の実装
- [ ] 各関数への適用
- [ ] 動作確認
- [ ] テスト実行

### 第2段階: デコレータパターン
- [ ] `mcp_servers/decorators.py`の作成
- [ ] `authenticated_tool`の実装
- [ ] `logged_tool`の実装
- [ ] `error_handled_tool`の実装
- [ ] 既存関数への適用
- [ ] 動作確認
- [ ] テスト実行

### 第3段階: サービス層への分離
- [ ] `mcp_servers/services/`ディレクトリの作成
- [ ] `recipe_service.py`の作成
- [ ] `RecipeService`クラスの実装
- [ ] ビジネスロジックの移行
- [ ] MCPツール関数の簡素化
- [ ] 動作確認
- [ ] テスト実行

---

## 参考情報

- 現在のファイル構造: `mcp_servers/recipe_mcp.py` (722行)
- 関連ファイル:
  - `mcp_servers/recipe_llm.py`
  - `mcp_servers/recipe_rag.py` (ディレクトリ構造を確認)
  - `mcp_servers/recipe_web.py`
  - `mcp_servers/utils.py`

