"""
Morizo AI v2 - Recipe Web Search Module

This module provides web search functionality for recipe retrieval using Google Search API and Perplexity API.
"""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from config.loggers import GenericLogger
from mcp_servers.recipe_web_google import GoogleSearchClient
from mcp_servers.recipe_web_perplexity import PerplexitySearchClient

# 環境変数の読み込み
load_dotenv()

# ロガーの初期化
logger = GenericLogger("mcp", "recipe_web", initialize_logging=False)


def prioritize_recipes(recipes: List[Dict]) -> List[Dict]:
    """レシピを優先順位でソート"""
    priority_order = ['cookpad.com', 'kurashiru.com', 'recipe.rakuten.co.jp', 'delishkitchen.tv']
    
    def get_priority(recipe):
        site = recipe.get('site', '')
        try:
            return priority_order.index(site)
        except ValueError:
            return len(priority_order)
    
    return sorted(recipes, key=get_priority)


def filter_recipe_results(recipes: List[Dict]) -> List[Dict]:
    """レシピ結果をフィルタリング"""
    filtered = []
    
    for recipe in recipes:
        # 基本的な検証
        if recipe.get('title') and recipe.get('url'):
            # レシピサイトかどうかを確認
            if recipe.get('site') in ['cookpad.com', 'kurashiru.com', 'recipe.rakuten.co.jp', 'delishkitchen.tv']:
                filtered.append(recipe)
    
    return filtered


# グローバルインスタンス（デフォルトはGoogle Search）
# 環境変数 USE_PERPLEXITY_SEARCH でPerplexityに切り替え可能
USE_PERPLEXITY_SEARCH = os.getenv('USE_PERPLEXITY_SEARCH', 'False').lower() in ('true', '1', 'yes')

# グローバルインスタンス（後方互換性のため）
try:
    if USE_PERPLEXITY_SEARCH:
        search_client = PerplexitySearchClient()
        logger.info("🔍 [WEB] Perplexity検索を使用中（グローバル）")
    else:
        search_client = GoogleSearchClient()
        logger.info("🔍 [WEB] Google検索を使用中（グローバル）")
except Exception as e:
    logger.warning(f"⚠️ [WEB] 検索クライアントの初期化に失敗しました: {e}、Google検索にフォールバックします")
    search_client = GoogleSearchClient()

# 検索クライアントのインスタンス（再利用のため）
_google_search_client = None
_perplexity_search_client = None


def _get_or_create_perplexity_client() -> Any:
    """Perplexityクライアントを取得または作成（エラー時はGoogle Searchにフォールバック）"""
    global _google_search_client, _perplexity_search_client
    
    if _perplexity_search_client is None:
        try:
            _perplexity_search_client = PerplexitySearchClient()
            logger.info("✅ [WEB] Perplexity検索クライアントの初期化に成功しました")
        except ValueError as e:
            logger.error(f"❌ [WEB] Perplexity APIキーが設定されていません: {e}")
            logger.warning(f"⚠️ [WEB] Falling back to Google Search (may use mock data)")
            return _get_or_create_google_client()
        except Exception as e:
            logger.error(f"❌ [WEB] Perplexityクライアントの初期化に失敗しました: {e}")
            logger.warning(f"⚠️ [WEB] Falling back to Google Search (may use mock data)")
            return _get_or_create_google_client()
    
    return _perplexity_search_client


def _get_or_create_google_client() -> Any:
    """Google Searchクライアントを取得または作成"""
    global _google_search_client
    
    if _google_search_client is None:
        _google_search_client = GoogleSearchClient()
    
    return _google_search_client


def get_search_client(menu_source: str = "mixed", use_perplexity: bool = None) -> Any:
    """
    検索クライアントを取得（menu_sourceに基づいて動的に選択）
    
    Args:
        menu_source: メニューのソース（"llm", "rag", "mixed"）
        use_perplexity: 強制的にPerplexityを使用するか（Noneの場合はmenu_sourceに基づいて決定）
    
    Returns:
        検索クライアントインスタンス
    """
    # 優先順位: 環境変数 > 明示的指定 > menu_source判定 > デフォルト
    
    # 1. 環境変数で全体を切り替える場合
    if USE_PERPLEXITY_SEARCH:
        return _get_or_create_perplexity_client()
    
    # 2. use_perplexityが明示的に指定されている場合も、Google Searchを使用
    # （Perplexity APIの残金切れのため、一時的にGoogle Searchに統一）
    # if use_perplexity is True:
    #     return _get_or_create_perplexity_client()
    
    # 3. menu_sourceが"llm"の場合も、Google Searchを使用
    # （Perplexity APIの残金切れのため、一時的にGoogle Searchに統一）
    # if menu_source == "llm":
    #     logger.debug(f"🔍 [WEB] menu_source='llm' detected, attempting to use Perplexity Search")
    #     client = _get_or_create_perplexity_client()
    #     logger.debug(f"🔍 [WEB] Returning Perplexity Search client for LLM proposals")
    #     return client
    
    # 4. デフォルトはGoogle Search（すべてのケースでGoogle Searchを使用）
    logger.debug(f"🔍 [WEB] Using Google Search (menu_source={menu_source}, use_perplexity={use_perplexity})")
    return _get_or_create_google_client()
