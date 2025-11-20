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

from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv
from supabase import create_client, Client
from fastmcp import FastMCP

from mcp_servers.recipe_llm import RecipeLLM
from mcp_servers.recipe_rag import RecipeRAGClient
from mcp_servers.utils import get_authenticated_client
from mcp_servers.decorators import authenticated_tool, logged_tool, error_handled_tool
from mcp_servers.services.recipe_service import RecipeService
from config.loggers import GenericLogger

# .envファイルを読み込み
load_dotenv()

# MCPサーバー初期化
mcp = FastMCP("Recipe MCP Server")

# 処理クラスのインスタンス
llm_client = RecipeLLM()
rag_client = RecipeRAGClient()
recipe_service = RecipeService()
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
@error_handled_tool
@logged_tool
@authenticated_tool
async def get_recipe_history_for_user(user_id: str, token: str = None, client: Any = None) -> Dict[str, Any]:
    """
    ユーザーのレシピ履歴を取得
    
    Args:
        user_id: ユーザーID
        token: 認証トークン
        client: 認証済みSupabaseクライアント（デコレータが自動注入）
    
    Returns:
        Dict[str, Any]: レシピ履歴のリスト
    """
    result = await llm_client.get_recipe_history(client, user_id)
    logger.debug(f"📊 [RECIPE] Recipe history result: {result}")
    return result


@mcp.tool()
@error_handled_tool
@logged_tool
@authenticated_tool
async def generate_menu_plan_with_history(
    inventory_items: List[str],
    user_id: str,
    menu_type: str = "",
    excluded_recipes: List[str] = None,
    token: str = None,
    client: Any = None
) -> Dict[str, Any]:
    """
    LLM推論による独創的な献立プラン生成（履歴考慮）
    
    Args:
        inventory_items: 在庫食材リスト
        user_id: ユーザーID
        menu_type: 献立のタイプ（和食・洋食・中華）
        excluded_recipes: 除外するレシピタイトル
        token: 認証トークン
        client: 認証済みSupabaseクライアント（デコレータが自動注入）
    
    Returns:
        Dict[str, Any]: 生成された献立プラン
    """
    result = await llm_client.generate_menu_titles(inventory_items, menu_type, excluded_recipes)
    logger.debug(f"📊 [RECIPE] Menu plan with history result: {result}")
    return result


@mcp.tool()
@error_handled_tool
@logged_tool
@authenticated_tool
async def search_menu_from_rag_with_history(
    inventory_items: List[str],
    user_id: str,
    menu_type: str = "",
    excluded_recipes: List[str] = None,
    token: str = None,
    client: Any = None
) -> Dict[str, Any]:
    """
    RAG検索による伝統的な献立タイトル生成
    
    Args:
        inventory_items: 在庫食材リスト
        user_id: ユーザーID
        menu_type: 献立のタイプ
        excluded_recipes: 除外するレシピタイトル
        token: 認証トークン
        client: 認証済みSupabaseクライアント（デコレータが自動注入）
    
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
    return await recipe_service.search_menu_from_rag(
        inventory_items=inventory_items,
        menu_type=menu_type,
        excluded_recipes=excluded_recipes
    )


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
@error_handled_tool
@logged_tool
async def search_recipe_from_web(
    recipe_titles: List[str], 
    num_results: int = 5, 
    user_id: str = "", 
    token: str = None,
    menu_categories: List[str] = None,
    menu_source: str = "mixed",
    rag_results: Dict[str, Dict[str, Any]] = None,
    use_perplexity: bool = None
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
        use_perplexity: 強制的にPerplexityを使用するか（Noneの場合はmenu_sourceに基づいて決定）
    
    Returns:
        Dict[str, Any]: 分類された検索結果のレシピリスト（画像URL含む）
    """
    return await recipe_service.search_recipes_from_web(
        recipe_titles=recipe_titles,
        num_results=num_results,
        menu_categories=menu_categories,
        menu_source=menu_source,
        rag_results=rag_results,
        use_perplexity=use_perplexity
    )


@mcp.tool()
@error_handled_tool
@logged_tool
@authenticated_tool
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
    category_detail_keyword: Optional[str] = None,
    client: Any = None
) -> Dict[str, Any]:
    """
    汎用提案メソッド（主菜・副菜・汁物・その他対応）
    
    Args:
        category: "main", "sub", "soup", "other"
        used_ingredients: すでに使った食材（副菜・汁物で使用）
        menu_category: 献立カテゴリ（汁物の判断に使用）
        client: 認証済みSupabaseクライアント（デコレータが自動注入）
    """
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




if __name__ == "__main__":
    logger.debug("🚀 Starting Recipe MCP Server")
    mcp.run()
