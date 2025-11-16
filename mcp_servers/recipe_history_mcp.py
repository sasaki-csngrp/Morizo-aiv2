"""
Morizo AI v2 - Recipe History MCP Server

This module provides MCP server for recipe history management with tool definitions only.
"""

import sys
import os
# プロジェクトルートをPythonのモジュール検索パスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from fastmcp import FastMCP

from mcp_servers.recipe_history_crud import RecipeHistoryCRUD
from mcp_servers.utils import get_authenticated_client
from config.loggers import GenericLogger

# .envファイルを読み込み
load_dotenv()

# MCPサーバー初期化
mcp = FastMCP("Recipe History MCP Server")

# 処理クラスのインスタンス
crud = RecipeHistoryCRUD()
logger = GenericLogger("mcp", "recipe_history_server", initialize_logging=False)

# 手動でログハンドラーを設定
from config.logging import get_logger
import logging

# ルートロガーを取得してハンドラーを設定
root_logger = logging.getLogger('morizo_ai')
if not root_logger.handlers:
    from config.logging import setup_logging
    setup_logging(initialize=False)  # ローテーションなし


# 基本CRUD操作
@mcp.tool()
async def history_add(
    user_id: str,
    title: str,
    source: str,
    url: Optional[str] = None,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    レシピを保存する
    
    Args:
        user_id: ユーザーID
        title: レシピタイトル
        source: レシピの出典
        url: レシピのURL
    
    Returns:
        Dict[str, Any]: 保存結果
    """
    logger.info(f"🔧 [RECIPE_HISTORY] Starting history_add")
    logger.debug(f"🔍 [RECIPE_HISTORY] User ID: {user_id}, title: {title}")
    
    try:
        client = get_authenticated_client(user_id)
        logger.info(f"🔐 [RECIPE_HISTORY] Authenticated client created for user: {user_id}")
        
        result = await crud.add_history(client, user_id, title, source, url)
        logger.info(f"✅ [RECIPE_HISTORY] history_add completed successfully")
        logger.debug(f"📊 [RECIPE_HISTORY] Add result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE_HISTORY] Error in history_add: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def history_list(user_id: str) -> Dict[str, Any]:
    """
    ユーザーのレシピ履歴を取得する
    
    Args:
        user_id: ユーザーID
    
    Returns:
        Dict[str, Any]: レシピ履歴のリスト
    """
    logger.info(f"🔧 [RECIPE_HISTORY] Starting history_list")
    logger.debug(f"🔍 [RECIPE_HISTORY] User ID: {user_id}")
    
    try:
        client = get_authenticated_client(user_id)
        logger.info(f"🔐 [RECIPE_HISTORY] Authenticated client created for user: {user_id}")
        
        result = await crud.list_history(client, user_id)
        logger.info(f"✅ [RECIPE_HISTORY] history_list completed successfully")
        logger.debug(f"📊 [RECIPE_HISTORY] List result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE_HISTORY] Error in history_list: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def history_get(user_id: str, history_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    特定のレシピ履歴を1件取得
    
    Args:
        user_id: ユーザーID
        history_id: 履歴ID
    
    Returns:
        レシピ履歴の詳細
    """
    client = get_authenticated_client(user_id, token)
    return await crud.get_history_by_id(client, user_id, history_id)


@mcp.tool()
async def history_update_by_id(
    user_id: str,
    history_id: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    レシピ履歴を更新する
    
    Args:
        user_id: ユーザーID
        history_id: 履歴ID
        title: レシピタイトル
        source: レシピの出典
        url: レシピのURL
    
    Returns:
        Dict[str, Any]: 更新結果
    """
    logger.info(f"🔧 [RECIPE_HISTORY] Starting history_update_by_id")
    logger.debug(f"🔍 [RECIPE_HISTORY] User ID: {user_id}, history_id: {history_id}")
    
    try:
        client = get_authenticated_client(user_id)
        logger.info(f"🔐 [RECIPE_HISTORY] Authenticated client created for user: {user_id}")
        
        result = await crud.update_history_by_id(client, user_id, history_id, title, source, url)
        logger.info(f"✅ [RECIPE_HISTORY] history_update_by_id completed successfully")
        logger.debug(f"📊 [RECIPE_HISTORY] Update by id result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE_HISTORY] Error in history_update_by_id: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def history_delete_by_id(user_id: str, history_id: str) -> Dict[str, Any]:
    """
    レシピ履歴を削除する
    
    Args:
        user_id: ユーザーID
        history_id: 履歴ID
    
    Returns:
        Dict[str, Any]: 削除結果
    """
    logger.info(f"🔧 [RECIPE_HISTORY] Starting history_delete_by_id")
    logger.debug(f"🔍 [RECIPE_HISTORY] User ID: {user_id}, history_id: {history_id}")
    
    try:
        client = get_authenticated_client(user_id)
        logger.info(f"🔐 [RECIPE_HISTORY] Authenticated client created for user: {user_id}")
        
        result = await crud.delete_history_by_id(client, user_id, history_id)
        logger.info(f"✅ [RECIPE_HISTORY] history_delete_by_id completed successfully")
        logger.debug(f"📊 [RECIPE_HISTORY] Delete by id result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE_HISTORY] Error in history_delete_by_id: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def history_get_recent_titles(
    user_id: str,
    category: str,  # "main", "sub", "soup"
    days: int = 14,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    指定期間内のレシピタイトルを取得（重複回避用）
    
    Args:
        user_id: ユーザーID
        category: カテゴリ（"main", "sub", "soup"）
        days: 重複回避期間（日数）
        token: 認証トークン
    
    Returns:
        Dict[str, Any]: レシピタイトルのリスト
    """
    logger.debug(f"🔧 [RECIPE_HISTORY] Starting history_get_recent_titles")
    logger.debug(f"🔍 [RECIPE_HISTORY] User ID: {user_id}, category: {category}, days: {days}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [RECIPE_HISTORY] Authenticated client created for user: {user_id}")
        
        result = await crud.get_recent_recipe_titles(client, user_id, category, days)
        logger.debug(f"✅ [RECIPE_HISTORY] history_get_recent_titles completed successfully")
        logger.debug(f"📊 [RECIPE_HISTORY] Recent titles result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [RECIPE_HISTORY] Error in history_get_recent_titles: {e}")
        return {"success": False, "error": str(e), "data": []}


if __name__ == "__main__":
    logger.debug("🚀 Starting Recipe History MCP Server")
    mcp.run()
