"""
Morizo AI v2 - Inventory MCP Server

This module provides MCP server for inventory management with tool definitions only.
"""

import sys
import os
# プロジェクトルートをPythonのモジュール検索パスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from fastmcp import FastMCP

from mcp_servers.inventory_crud import InventoryCRUD
from mcp_servers.inventory_advanced import InventoryAdvanced
from mcp_servers.utils import get_authenticated_client
from config.loggers import GenericLogger

# .envファイルを読み込み
load_dotenv()

# MCPサーバー初期化
mcp = FastMCP("Inventory MCP Server")

# 処理クラスのインスタンス
crud = InventoryCRUD()
advanced = InventoryAdvanced()
logger = GenericLogger("mcp", "inventory_server", initialize_logging=False)

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
async def inventory_add(
    user_id: str,
    item_name: str,
    quantity: float,
    unit: str = "個",
    storage_location: str = "冷蔵庫",
    expiry_date: Optional[str] = None,
    token: str = ""
) -> Dict[str, Any]:
    """在庫にアイテムを1件追加（個別在庫法）"""
    logger.debug(f"🔧 [INVENTORY] inventory_add を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}, アイテム: {item_name}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.add_item(client, user_id, item_name, quantity, unit, storage_location, expiry_date)
        logger.debug(f"✅ [INVENTORY] inventory_add が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] Add result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_add でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def inventory_list(user_id: str, token: str = "") -> Dict[str, Any]:
    """ユーザーの全在庫アイテムを取得"""
    logger.debug(f"🔧 [INVENTORY] inventory_list を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.get_all_items(client, user_id)
        logger.debug(f"✅ [INVENTORY] inventory_list が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] List result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_list でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def inventory_list_by_name(user_id: str, item_name: str, token: str = "") -> Dict[str, Any]:
    """指定したアイテム名の在庫アイテムを取得"""
    logger.debug(f"🔧 [INVENTORY] inventory_list_by_name を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}, アイテム: {item_name}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.get_items_by_name(client, user_id, item_name)
        logger.debug(f"✅ [INVENTORY] inventory_list_by_name が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] List by name result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_list_by_name でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def inventory_get(user_id: str, item_id: str, token: str = "") -> Dict[str, Any]:
    """指定したIDの在庫アイテムを取得"""
    logger.debug(f"🔧 [INVENTORY] inventory_get を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}, アイテムID: {item_id}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.get_item_by_id(client, user_id, item_id)
        logger.debug(f"✅ [INVENTORY] inventory_get が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] Get result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_get でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def inventory_update_by_id(
    user_id: str,
    item_id: str,
    item_name: Optional[str] = None,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    storage_location: Optional[str] = None,
    expiry_date: Optional[str] = None,
    token: str = ""
) -> Dict[str, Any]:
    """指定したIDの在庫アイテムを更新"""
    logger.debug(f"🔧 [INVENTORY] inventory_update_by_id を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}, アイテムID: {item_id}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.update_item_by_id(client, user_id, item_id, item_name, quantity, unit, storage_location, expiry_date)
        logger.debug(f"✅ [INVENTORY] inventory_update_by_id が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] Update by id result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_update_by_id でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def inventory_delete_by_id(user_id: str, item_id: str, token: str = "") -> Dict[str, Any]:
    """指定したIDの在庫アイテムを削除"""
    logger.debug(f"🔧 [INVENTORY] inventory_delete_by_id を開始します")
    logger.debug(f"🔍 [INVENTORY] ユーザーID: {user_id}, アイテムID: {item_id}")
    
    try:
        client = get_authenticated_client(user_id, token)
        logger.info(f"🔐 [INVENTORY] ユーザー {user_id} の認証済みクライアントを作成しました")
        
        result = await crud.delete_item_by_id(client, user_id, item_id)
        logger.debug(f"✅ [INVENTORY] inventory_delete_by_id が正常に完了しました")
        logger.debug(f"📊 [INVENTORY] Delete by id result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [INVENTORY] inventory_delete_by_id でエラーが発生しました: {e}")
        return {"success": False, "error": str(e)}


# 高度な操作
@mcp.tool()
async def inventory_update_by_name(
    user_id: str,
    item_name: str,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    storage_location: Optional[str] = None,
    expiry_date: Optional[str] = None,
    token: str = ""
) -> Dict[str, Any]:
    """名前指定での在庫アイテム一括更新"""
    client = get_authenticated_client(user_id, token)
    return await advanced.update_by_name(client, user_id, item_name, quantity, unit, storage_location, expiry_date)


@mcp.tool()
async def inventory_update_by_name_oldest(
    user_id: str,
    item_name: str,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    storage_location: Optional[str] = None,
    expiry_date: Optional[str] = None,
    token: str = ""
) -> Dict[str, Any]:
    """名前指定での最古アイテム更新（FIFO原則）"""
    client = get_authenticated_client(user_id, token)
    return await advanced.update_by_name_oldest(client, user_id, item_name, quantity, unit, storage_location, expiry_date)


@mcp.tool()
async def inventory_update_by_name_latest(
    user_id: str,
    item_name: str,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    storage_location: Optional[str] = None,
    expiry_date: Optional[str] = None,
    token: str = ""
) -> Dict[str, Any]:
    """名前指定での最新アイテム更新"""
    client = get_authenticated_client(user_id, token)
    return await advanced.update_by_name_latest(client, user_id, item_name, quantity, unit, storage_location, expiry_date)




@mcp.tool()
async def inventory_delete_by_name(user_id: str, item_name: str, token: str = "") -> Dict[str, Any]:
    """名前指定での在庫アイテム一括削除"""
    client = get_authenticated_client(user_id, token)
    return await advanced.delete_by_name(client, user_id, item_name)


@mcp.tool()
async def inventory_delete_by_name_oldest(user_id: str, item_name: str, token: str = "") -> Dict[str, Any]:
    """名前指定での最古アイテム削除（FIFO原則）"""
    client = get_authenticated_client(user_id, token)
    return await advanced.delete_by_name_oldest(client, user_id, item_name)


@mcp.tool()
async def inventory_delete_by_name_latest(user_id: str, item_name: str, token: str = "") -> Dict[str, Any]:
    """名前指定での最新アイテム削除"""
    client = get_authenticated_client(user_id, token)
    return await advanced.delete_by_name_latest(client, user_id, item_name)


if __name__ == "__main__":
    logger.debug("🚀 在庫MCPサーバーを起動中")
    mcp.run()
