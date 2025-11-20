"""
Morizo AI v2 - Recipe MCP Server

This module provides MCP server for recipe generation with LLM-based tools.
"""

import sys
import os
import asyncio
import traceback
# プロジェクトルートをPythonのモジュール検索パスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from fastmcp import FastMCP

from mcp_servers.recipe_llm import RecipeLLM
from mcp_servers.recipe_rag import RecipeRAGClient
from mcp_servers.recipe_web import search_client, get_search_client, prioritize_recipes, filter_recipe_results
from mcp_servers.utils import get_authenticated_client
from config.loggers import GenericLogger

# .envファイルを読み込み
load_dotenv()

# MCPサーバー初期化
mcp = FastMCP("Recipe MCP Server")

# 処理クラスのインスタンス
llm_client = RecipeLLM()
rag_client = RecipeRAGClient()
logger = GenericLogger("mcp", "recipe_server", initialize_logging=False)

# 手動でログハンドラーを設定
from config.logging import get_logger
import logging

# ルートロガーを取得してハンドラーを設定
root_logger = logging.getLogger('morizo_ai')
if not root_logger.handlers:
    from config.logging import setup_logging
    setup_logging(initialize=False)  # ローテーションなし


# ============================================================================
# ヘルパー関数
# ============================================================================

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


async def _search_single_recipe_with_rag_fallback(
    title: str,
    index: int,
    rag_results: Dict[str, Dict[str, Any]],
    menu_source: str,
    recipe_titles: List[str],
    num_results: int
) -> Dict[str, Any]:
    """
    単一の料理名でレシピ検索（RAG検索結果のURLを優先）
    
    Args:
        title: レシピタイトル
        index: インデックス（menu_source判定に使用）
        rag_results: RAG検索結果の辞書
        menu_source: 検索元（llm, rag, mixed）
        recipe_titles: レシピタイトルのリスト（menu_source判定に使用）
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
        total_count = len(recipe_titles)
        if index < total_count / 2:
            effective_source = "llm"
            logger.debug(f"🔍 [RECIPE] Index {index} < {total_count}/2, treating as LLM proposal")
        else:
            effective_source = "rag"
            logger.debug(f"🔍 [RECIPE] Index {index} >= {total_count}/2, treating as RAG proposal")
    
    logger.debug(f"🔍 [RECIPE] Getting search client for menu_source='{menu_source}' (effective: '{effective_source}')")
    client = get_search_client(menu_source=effective_source)
    client_type = type(client).__name__
    logger.debug(f"🔍 [RECIPE] Using search client: {client_type}")
    recipes = await client.search_recipes(title, num_results)
    logger.debug(f"🔍 [RECIPE] Web search completed")
    logger.debug(f"📊 [RECIPE] Title: '{title}', found {len(recipes)} recipes")
    
    # レシピを優先順位でソート
    prioritized_recipes = prioritize_recipes(recipes)
    logger.debug(f"📊 [RECIPE] Recipes prioritized for '{title}'")
    
    # 結果をフィルタリング
    filtered_recipes = filter_recipe_results(prioritized_recipes)
    logger.debug(f"📊 [RECIPE] Recipes filtered for '{title}', final count: {len(filtered_recipes)}")
    
    return {
        "success": True,
        "data": filtered_recipes,
        "title": title,
        "count": len(filtered_recipes)
    }


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


# ============================================================================
# MCPツール関数
# ============================================================================

@mcp.tool()
async def get_recipe_history_for_user(user_id: str, token: str = None) -> Dict[str, Any]:
    """
    ユーザーのレシピ履歴を取得
    
    Args:
        user_id: ユーザーID
        token: 認証トークン
    
    Returns:
        Dict[str, Any]: レシピ履歴のリスト
    """
    logger.info(f"🔧 [RECIPE] Starting get_recipe_history_for_user")
    logger.debug(f"🔍 [RECIPE] User ID: {user_id}")
    
    try:
        client = await _get_authenticated_client_safe(user_id)
        
        result = await llm_client.get_recipe_history(client, user_id)
        logger.info(f"✅ [RECIPE] get_recipe_history_for_user completed successfully")
        logger.debug(f"📊 [RECIPE] Recipe history result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE] Error in get_recipe_history_for_user: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def generate_menu_plan_with_history(
    inventory_items: List[str],
    user_id: str,
    menu_type: str = "",
    excluded_recipes: List[str] = None,
    token: str = None
) -> Dict[str, Any]:
    """
    LLM推論による独創的な献立プラン生成（履歴考慮）
    
    Args:
        inventory_items: 在庫食材リスト
        user_id: ユーザーID
        menu_type: 献立のタイプ（和食・洋食・中華）
        excluded_recipes: 除外するレシピタイトル
        token: 認証トークン
    
    Returns:
        Dict[str, Any]: 生成された献立プラン
    """
    logger.info(f"🔧 [RECIPE] Starting generate_menu_plan_with_history")
    logger.debug(f"🔍 [RECIPE] User ID: {user_id}, menu_type: {menu_type}")
    
    try:
        client = await _get_authenticated_client_safe(user_id, token)
        
        result = await llm_client.generate_menu_titles(inventory_items, menu_type, excluded_recipes)
        logger.info(f"✅ [RECIPE] generate_menu_plan_with_history completed successfully")
        logger.debug(f"📊 [RECIPE] Menu plan with history result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE] Error in generate_menu_plan_with_history: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_menu_from_rag_with_history(
    inventory_items: List[str],
    user_id: str,
    menu_type: str = "",
    excluded_recipes: List[str] = None,
    token: str = None
) -> Dict[str, Any]:
    """
    RAG検索による伝統的な献立タイトル生成
    
    Args:
        inventory_items: 在庫食材リスト
        user_id: ユーザーID
        menu_type: 献立のタイプ
        excluded_recipes: 除外するレシピタイトル
    
    Returns:
        {
            "candidates": [
                {
                    "main_dish": {"title": "牛乳と卵のフレンチトースト", "ingredients": ["牛乳", "卵", "パン"]},
                    "side_dish": {"title": "ほうれん草の胡麻和え", "ingredients": ["ほうれん草", "胡麻"]},
                    "soup": {"title": "白菜とハムのクリームスープ", "ingredients": ["白菜", "ハム", "牛乳"]}
                }
            ],
            "selected": {
                "main_dish": {"title": "牛乳と卵のフレンチトースト", "ingredients": ["牛乳", "卵", "パン"]},
                "side_dish": {"title": "ほうれん草の胡麻和え", "ingredients": ["ほうれん草", "胡麻"]},
                "soup": {"title": "白菜とハムのクリームスープ", "ingredients": ["白菜", "ハム", "牛乳"]}
            }
        }
    """
    logger.info(f"🔧 [RECIPE] Starting search_menu_from_rag_with_history")
    logger.debug(f"🔍 [RECIPE] User ID: {user_id}, menu_type: {menu_type}")
    
    try:
        # 認証済みクライアントを取得（一貫性のため）
        client = await _get_authenticated_client_safe(user_id, token)
        
        # RAG検索を実行（3ベクトルDB対応）
        categorized_results = await rag_client.search_recipes_by_category(
            ingredients=inventory_items,
            menu_type=menu_type,
            excluded_recipes=excluded_recipes,
            limit=10  # 多めに取得して献立構成に使用
        )
        
        logger.info(f"🔍 [RECIPE] RAG search completed, found categorized results")
        logger.debug(f"📊 [RECIPE] Main: {len(categorized_results.get('main', []))} recipes")
        logger.debug(f"📊 [RECIPE] Sub: {len(categorized_results.get('sub', []))} recipes")
        logger.debug(f"📊 [RECIPE] Soup: {len(categorized_results.get('soup', []))} recipes")
        
        # RAG検索結果を献立形式に変換（3ベクトルDB対応）
        try:
            logger.info(f"🔄 [RECIPE] Starting convert_categorized_results_to_menu_format")
            menu_result = await rag_client.convert_categorized_results_to_menu_format(
                categorized_results=categorized_results,
                inventory_items=inventory_items,
                menu_type=menu_type
            )
            logger.info(f"✅ [RECIPE] convert_categorized_results_to_menu_format completed")
        except Exception as e:
            logger.error(f"❌ [RECIPE] Error in convert_categorized_results_to_menu_format: {e}")
            logger.error(f"❌ [RECIPE] Categorized results: {categorized_results}")
            raise
        
        logger.info(f"✅ [RECIPE] search_menu_from_rag_with_history completed successfully")
        logger.debug(f"📊 [RECIPE] RAG menu result: {menu_result}")
        
        # RAG検索結果を統一フォーマットに変換
        formatted_data = _format_rag_menu_result(menu_result, inventory_items)
        
        return {
            "success": True,
            "data": formatted_data
        }
        
    except Exception as e:
        logger.error(f"❌ [RECIPE] Error in search_menu_from_rag_with_history: {e}")
        return {"success": False, "error": str(e)}


def extract_recipe_titles_from_proposals(proposals_result: Dict[str, Any]) -> List[str]:
    """主菜提案結果からレシピタイトルを抽出"""
    titles = []
    
    if proposals_result.get("success") and "data" in proposals_result:
        data = proposals_result["data"]
        if "candidates" in data:
            candidates = data["candidates"]
            for candidate in candidates:
                if isinstance(candidate, dict) and "title" in candidate:
                    titles.append(candidate["title"])
                elif isinstance(candidate, str):
                    titles.append(candidate)
    
    return titles


@mcp.tool()
async def search_recipe_from_web(
    recipe_titles: List[str], 
    num_results: int = 5, 
    user_id: str = "", 
    token: str = None,
    menu_categories: List[str] = None,
    menu_source: str = "mixed",
    rag_results: Dict[str, Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Web検索によるレシピ検索（主菜提案対応・複数料理名対応・並列実行・詳細分類）
    
    Args:
        recipe_titles: 検索するレシピタイトルのリスト（主菜提案結果のcandidatesから抽出可能）
        num_results: 各料理名あたりの取得結果数
        user_id: ユーザーID（一貫性のため受け取るが使用しない）
        token: 認証トークン
        menu_categories: 料理名の分類リスト（main_dish, side_dish, soup）
        menu_source: 検索元（llm, rag, mixed）
        rag_results: RAG検索結果の辞書（タイトルをキーとしてURLを含む） - オプション
    
    Returns:
        Dict[str, Any]: 分類された検索結果のレシピリスト（画像URL含む）
    """
    logger.debug(f"🔧 [RECIPE] Starting search_recipe_from_web")
    logger.debug(f"🔍 [RECIPE] Titles count: {len(recipe_titles)}, titles: {recipe_titles}, num_results: {num_results}")
    logger.debug(f"📊 [RECIPE] Menu categories: {menu_categories}, source: {menu_source}")
    
    try:
        import asyncio
        
        async def search_single_recipe(title: str, index: int) -> Dict[str, Any]:
            """単一の料理名でレシピ検索（RAG検索結果のURLを優先）"""
            try:
                return await _search_single_recipe_with_rag_fallback(
                    title=title,
                    index=index,
                    rag_results=rag_results,
                    menu_source=menu_source,
                    recipe_titles=recipe_titles,
                    num_results=num_results
                )
            except Exception as e:
                logger.error(f"❌ [RECIPE] Error searching for '{title}': {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "title": title,
                    "count": 0
                }
        
        # 並列実行（インデックスを渡す）
        tasks = [search_single_recipe(title, index) for index, title in enumerate(recipe_titles)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 単一カテゴリ提案かどうかを判定（主菜・副菜・汁物のいずれか1つのみ）
        # menu_categoriesがNone、空、または単一カテゴリのみの場合
        single_category = None
        if not menu_categories or len(menu_categories) == 0:
            # menu_categoriesが指定されていない場合は、デフォルトでmain_dishとみなす
            single_category = "main_dish"
        elif len(set(menu_categories)) == 1:
            # すべて同じカテゴリの場合
            single_category = menu_categories[0]
        
        is_single_category = single_category in ["main_dish", "side_dish", "soup"]
        
        successful_searches = 0
        # 単一カテゴリ提案の場合は、候補リストの順序に合わせてレシピを配置
        single_category_recipes = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ [RECIPE] Search failed for '{recipe_titles[i]}': {result}")
                continue
            elif result.get("success"):
                recipes = result.get("data", [])
                successful_searches += 1
                logger.debug(f"✅ [RECIPE] Found recipes")
                logger.debug(f"📊 [RECIPE] Found {len(recipes)} recipes for '{recipe_titles[i]}'")
                # 単一カテゴリ提案の場合は、各レシピタイトルに対応する最初のレシピを取得
                # （候補リストの順序と一致させるため）
                if is_single_category:
                    if recipes:
                        single_category_recipes.append(recipes[0])
            else:
                logger.error(f"❌ [RECIPE] Search failed for '{recipe_titles[i]}': {result.get('error')}")
        
        logger.info(f"✅ [RECIPE] Recipe search completed")
        logger.debug(f"📊 [RECIPE] Successful searches: {successful_searches}/{len(recipe_titles)}")
        
        # 単一カテゴリ提案の場合はシンプルな構造を返す
        if is_single_category:
            result = {
                "success": True,
                "data": {
                    single_category: {
                        "title": recipe_titles[0] if recipe_titles else "",
                        "recipes": single_category_recipes
                    }
                },
                "total_count": len(single_category_recipes),
                "searches_completed": successful_searches,
                "total_searches": len(recipe_titles)
            }
        else:
            # 一括提案の場合はllm_menu/rag_menu構造を返す
            categorized_results = _categorize_web_search_results(
                results=results,
                recipe_titles=recipe_titles,
                menu_categories=menu_categories,
                menu_source=menu_source
            )
            
            result = {
                "success": True,
                "data": categorized_results,
                "total_count": sum(len(cat["recipes"]) for menu in categorized_results.values() for cat in menu.values()),
                "searches_completed": successful_searches,
                "total_searches": len(recipe_titles)
            }
        
        logger.debug(f"✅ [RECIPE] search_recipe_from_web completed successfully")
        logger.debug(f"📊 [RECIPE] Web search result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE] Error in search_recipe_from_web: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def generate_proposals(
    inventory_items: List[str],
    user_id: str,
    category: str = "main",  # "main", "sub", "soup", "other"
    menu_type: str = "",
    main_ingredient: Optional[str] = None,
    used_ingredients: List[str] = None,
    excluded_recipes: List[str] = None,
    menu_category: str = "japanese",  # "japanese", "western", "chinese"
    sse_session_id: str = None,
    token: str = None,
    category_detail_keyword: Optional[str] = None
) -> Dict[str, Any]:
    """
    汎用提案メソッド（主菜・副菜・汁物・その他対応）
    
    Args:
        category: "main", "sub", "soup", "other"
        used_ingredients: すでに使った食材（副菜・汁物で使用）
        menu_category: 献立カテゴリ（汁物の判断に使用）
    """
    logger.debug(f"🔧 [RECIPE] ========== generate_proposals START ==========")
    logger.debug(f"🔧 [RECIPE] Function called with parameters:")
    logger.debug(f"  - inventory_items: {inventory_items} (type: {type(inventory_items).__name__}, len: {len(inventory_items) if inventory_items else 0})")
    logger.debug(f"  - user_id: {user_id} (type: {type(user_id).__name__})")
    logger.debug(f"  - category: {category} (type: {type(category).__name__})")
    logger.debug(f"  - menu_type: {menu_type} (type: {type(menu_type).__name__})")
    logger.debug(f"  - main_ingredient: {main_ingredient} (type: {type(main_ingredient).__name__})")
    logger.debug(f"  - used_ingredients: {used_ingredients} (type: {type(used_ingredients).__name__}, len: {len(used_ingredients) if used_ingredients else 0})")
    logger.debug(f"  - excluded_recipes: {excluded_recipes} (type: {type(excluded_recipes).__name__}, len: {len(excluded_recipes) if excluded_recipes else 0})")
    logger.debug(f"  - menu_category: {menu_category} (type: {type(menu_category).__name__})")
    logger.debug(f"  - sse_session_id: {sse_session_id} (type: {type(sse_session_id).__name__})")
    logger.debug(f"  - token: {'***' if token else None} (type: {type(token).__name__ if token else 'NoneType'})")
    logger.debug(f"  - category_detail_keyword: {category_detail_keyword} (type: {type(category_detail_keyword).__name__})")
    
    try:
        # 認証済みクライアントを取得
        logger.debug(f"🔐 [RECIPE] Step 1: Getting authenticated client for user_id={user_id}")
        logger.debug(f"🔐 [RECIPE] Token provided: {bool(token)}")
        client = await _get_authenticated_client_safe(user_id, token)
        logger.debug(f"🔐 [RECIPE] Client type: {type(client).__name__}")
        
        # Phase 3A: セッション内の提案済みレシピは、呼び出し元でexcluded_recipesとして渡されるため
        # MCPサーバー内では追加処理は不要（プロセス分離のため）
        logger.debug(f"📊 [RECIPE] Step 2: Processing excluded recipes")
        all_excluded = (excluded_recipes or []).copy()
        logger.debug(f"📊 [RECIPE] Total excluded: {len(all_excluded)} recipes")
        if all_excluded:
            logger.debug(f"📊 [RECIPE] Excluded recipe titles (first 5): {all_excluded[:5]}")
        
        # otherカテゴリの場合はused_ingredientsを使用しない（単体動作のため）
        logger.debug(f"📊 [RECIPE] Step 3: Processing category-specific logic")
        if category == "other":
            logger.debug(f"📊 [RECIPE] Category is 'other', setting used_ingredients to None")
            used_ingredients = None
        else:
            logger.debug(f"📊 [RECIPE] Category is '{category}', keeping used_ingredients: {used_ingredients}")
        
        # LLMとRAGを並列実行（汎用メソッドを使用）
        logger.debug(f"📊 [RECIPE] Step 4: Creating LLM and RAG tasks")
        logger.debug(f"📊 [RECIPE] LLM task parameters:")
        logger.debug(f"  - inventory_items: {inventory_items}")
        logger.debug(f"  - menu_type: {menu_type}")
        logger.debug(f"  - category: {category}")
        logger.debug(f"  - main_ingredient: {main_ingredient}")
        logger.debug(f"  - used_ingredients: {used_ingredients}")
        logger.debug(f"  - excluded_recipes count: {len(all_excluded)}")
        logger.debug(f"  - count: 2")
        logger.debug(f"  - category_detail_keyword: {category_detail_keyword}")
        
        logger.debug(f"📊 [RECIPE] RAG task parameters:")
        logger.debug(f"  - ingredients: {inventory_items}")
        logger.debug(f"  - menu_type: {menu_type}")
        logger.debug(f"  - category: {category}")
        logger.debug(f"  - main_ingredient: {main_ingredient}")
        logger.debug(f"  - used_ingredients: {used_ingredients}")
        logger.debug(f"  - excluded_recipes count: {len(all_excluded)}")
        logger.debug(f"  - limit: 3")
        logger.debug(f"  - category_detail_keyword: {category_detail_keyword}")
        
        try:
            logger.debug(f"📊 [RECIPE] Creating LLM task...")
            llm_task = llm_client.generate_candidates(
                inventory_items=inventory_items,
                menu_type=menu_type,
                category=category,
                main_ingredient=main_ingredient,
                used_ingredients=used_ingredients,
                excluded_recipes=all_excluded,
                count=2,
                category_detail_keyword=category_detail_keyword
            )
            logger.debug(f"✅ [RECIPE] LLM task created successfully (type: {type(llm_task).__name__})")
        except Exception as e:
            logger.error(f"❌ [RECIPE] Failed to create LLM task: {e}")
            logger.error(f"❌ [RECIPE] LLM task creation error type: {type(e).__name__}")
            logger.error(f"❌ [RECIPE] LLM task creation traceback: {traceback.format_exc()}")
            raise
        
        try:
            logger.debug(f"📊 [RECIPE] Creating RAG task...")
            rag_task = rag_client.search_candidates(
                ingredients=inventory_items,
                menu_type=menu_type,
                category=category,
                main_ingredient=main_ingredient,
                used_ingredients=used_ingredients,
                excluded_recipes=all_excluded,
                limit=3,
                category_detail_keyword=category_detail_keyword
            )
            logger.debug(f"✅ [RECIPE] RAG task created successfully (type: {type(rag_task).__name__})")
        except Exception as e:
            logger.error(f"❌ [RECIPE] Failed to create RAG task: {e}")
            logger.error(f"❌ [RECIPE] RAG task creation error type: {type(e).__name__}")
            logger.error(f"❌ [RECIPE] RAG task creation traceback: {traceback.format_exc()}")
            raise
        
        # 両方の結果を待つ（並列実行）
        logger.debug(f"📊 [RECIPE] Step 5: Executing asyncio.gather for LLM and RAG tasks")
        logger.debug(f"📊 [RECIPE] LLM task type: {type(llm_task).__name__}")
        logger.debug(f"📊 [RECIPE] RAG task type: {type(rag_task).__name__}")
        
        try:
            logger.debug(f"📊 [RECIPE] Awaiting asyncio.gather...")
            llm_result, rag_result = await asyncio.gather(llm_task, rag_task)
            logger.debug(f"✅ [RECIPE] asyncio.gather completed successfully")
            logger.debug(f"📊 [RECIPE] LLM result type: {type(llm_result).__name__}")
            logger.debug(f"📊 [RECIPE] RAG result type: {type(rag_result).__name__}")
        except Exception as e:
            logger.error(f"❌ [RECIPE] asyncio.gather failed: {e}")
            logger.error(f"❌ [RECIPE] asyncio.gather error type: {type(e).__name__}")
            logger.error(f"❌ [RECIPE] asyncio.gather traceback: {traceback.format_exc()}")
            raise
        
        # 統合（sourceフィールドを追加）
        logger.debug(f"📊 [RECIPE] Step 6: Processing and integrating results")
        logger.debug(f"📊 [RECIPE] LLM result structure:")
        logger.debug(f"  - Type: {type(llm_result).__name__}")
        logger.debug(f"  - Keys: {list(llm_result.keys()) if isinstance(llm_result, dict) else 'N/A'}")
        logger.debug(f"  - Success: {llm_result.get('success') if isinstance(llm_result, dict) else 'N/A'}")
        if isinstance(llm_result, dict) and llm_result.get("success"):
            llm_data = llm_result.get("data", {})
            logger.debug(f"  - Data keys: {list(llm_data.keys()) if isinstance(llm_data, dict) else 'N/A'}")
            llm_candidates_list = llm_data.get("candidates", [])
            logger.debug(f"  - Candidates count: {len(llm_candidates_list)}")
            logger.debug(f"  - Candidates type: {type(llm_candidates_list).__name__}")
        
        logger.debug(f"📊 [RECIPE] RAG result structure:")
        logger.debug(f"  - Type: {type(rag_result).__name__}")
        if isinstance(rag_result, list):
            logger.debug(f"  - List length: {len(rag_result)}")
            if rag_result:
                logger.debug(f"  - First item keys: {list(rag_result[0].keys()) if isinstance(rag_result[0], dict) else 'N/A'}")
        elif isinstance(rag_result, dict):
            logger.debug(f"  - Dict keys: {list(rag_result.keys())}")
        
        candidates = []
        
        # LLM結果の処理
        logger.debug(f"📊 [RECIPE] Processing LLM results...")
        if llm_result.get("success"):
            try:
                llm_candidates = llm_result["data"]["candidates"]
                logger.debug(f"📊 [RECIPE] LLM candidates extracted: {len(llm_candidates)} items")
                # LLM候補にsourceフィールドを追加
                for i, candidate in enumerate(llm_candidates):
                    if "source" not in candidate:
                        candidate["source"] = "llm"
                    logger.debug(f"📊 [RECIPE] LLM candidate {i+1}: title='{candidate.get('title', 'N/A')}', source='{candidate.get('source', 'N/A')}'")
                candidates.extend(llm_candidates)
                logger.debug(f"✅ [RECIPE] Added {len(llm_candidates)} LLM candidates")
            except Exception as e:
                logger.error(f"❌ [RECIPE] Error processing LLM results: {e}")
                logger.error(f"❌ [RECIPE] LLM result processing error type: {type(e).__name__}")
                logger.error(f"❌ [RECIPE] LLM result processing traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"⚠️ [RECIPE] LLM result indicates failure: {llm_result.get('error', 'Unknown error')}")
        
        # RAG結果の処理
        logger.debug(f"📊 [RECIPE] Processing RAG results...")
        if rag_result:
            try:
                logger.debug(f"📊 [RECIPE] RAG result is truthy, processing...")
                # RAG候補にsourceフィールドとURLを追加
                rag_candidates = []
                for i, r in enumerate(rag_result):
                    logger.debug(f"📊 [RECIPE] Processing RAG result {i+1}: type={type(r).__name__}, keys={list(r.keys()) if isinstance(r, dict) else 'N/A'}")
                    candidate = {
                        "title": r["title"],
                        "ingredients": r.get("ingredients", []),
                        "source": "rag"
                    }
                    # URLが含まれている場合は追加（ベクトルDBから取得）
                    if "url" in r and r["url"]:
                        candidate["url"] = r["url"]
                        logger.debug(f"📊 [RECIPE] RAG candidate {i+1} has URL: {r['url']}")
                    rag_candidates.append(candidate)
                    logger.debug(f"📊 [RECIPE] RAG candidate {i+1}: title='{candidate.get('title', 'N/A')}', source='{candidate.get('source', 'N/A')}'")
                candidates.extend(rag_candidates)
                logger.debug(f"✅ [RECIPE] Added {len(rag_candidates)} RAG candidates")
            except Exception as e:
                logger.error(f"❌ [RECIPE] Error processing RAG results: {e}")
                logger.error(f"❌ [RECIPE] RAG result processing error type: {type(e).__name__}")
                logger.error(f"❌ [RECIPE] RAG result processing traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"⚠️ [RECIPE] RAG result is empty or falsy")
        
        # デバッグログ: 各候補のsourceを確認
        logger.debug(f"📊 [RECIPE] Final candidates summary:")
        logger.debug(f"  - Total candidates: {len(candidates)}")
        for i, candidate in enumerate(candidates):
            logger.debug(f"🔍 [RECIPE] Candidate {i+1}: title='{candidate.get('title', 'N/A')}', source='{candidate.get('source', 'N/A')}', has_url={bool(candidate.get('url'))}")
        
        logger.info(f"✅ [RECIPE] generate_proposals completed")
        llm_count = len(llm_result.get('data', {}).get('candidates', [])) if llm_result.get('success') else 0
        rag_count = len(rag_result) if rag_result else 0
        logger.debug(f"📊 [RECIPE] Final counts - Total: {len(candidates)}, LLM: {llm_count}, RAG: {rag_count}")
        
        logger.debug(f"📊 [RECIPE] Step 7: Building return value")
        return_value = {
            "success": True,
            "data": {
                "candidates": candidates,
                "category": category,
                "total": len(candidates),
                "main_ingredient": main_ingredient,
                "excluded_count": len(all_excluded),
                "llm_count": len(llm_result.get("data", {}).get("candidates", [])) if llm_result.get("success") else 0,
                "rag_count": len(rag_result) if rag_result else 0
            }
        }
        logger.debug(f"📊 [RECIPE] Return value structure:")
        logger.debug(f"  - success: {return_value['success']}")
        logger.debug(f"  - data keys: {list(return_value['data'].keys())}")
        logger.debug(f"  - candidates count: {len(return_value['data']['candidates'])}")
        logger.debug(f"🔧 [RECIPE] ========== generate_proposals END (SUCCESS) ==========")
        return return_value
        
    except Exception as e:
        logger.error(f"❌ [RECIPE] ========== generate_proposals END (ERROR) ==========")
        logger.error(f"❌ [RECIPE] Exception occurred in generate_proposals")
        logger.error(f"❌ [RECIPE] Exception type: {type(e).__name__}")
        logger.error(f"❌ [RECIPE] Exception message: {str(e)}")
        logger.error(f"❌ [RECIPE] Exception args: {e.args}")
        logger.error(f"❌ [RECIPE] Full traceback:")
        logger.error(f"{traceback.format_exc()}")
        logger.error(f"❌ [RECIPE] Error context - Parameters at error time:")
        logger.error(f"  - inventory_items: {inventory_items}")
        logger.error(f"  - user_id: {user_id}")
        logger.error(f"  - category: {category}")
        logger.error(f"  - menu_type: {menu_type}")
        logger.error(f"  - main_ingredient: {main_ingredient}")
        logger.error(f"  - used_ingredients: {used_ingredients}")
        logger.error(f"  - excluded_recipes count: {len(excluded_recipes) if excluded_recipes else 0}")
        logger.error(f"  - category_detail_keyword: {category_detail_keyword}")
        return {"success": False, "error": str(e)}




if __name__ == "__main__":
    logger.debug("🚀 Starting Recipe MCP Server")
    mcp.run()
