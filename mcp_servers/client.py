"""
Morizo AI v2 - MCP Client

This module provides the MCP client for tool communication with authentication.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

from config.loggers import GenericLogger

# .envファイルを読み込み
load_dotenv()


class MCPClient:
    """
    MCPクライアント（認証機能付き）
    
    FastMCPクライアントを使用してMCPサーバーと通信し、
    認証機能付きでツールを呼び出す。
    """
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.logger = GenericLogger("mcp", "client")
        
        if not all([self.supabase_url, self.supabase_key]):
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")
        
        self._client: Optional[Client] = None
        
        # FastMCPクライアントの初期化（サーバーファイルパスを指定）
        self.mcp_clients = {}
        
        # 各FastMCPサーバーへの接続設定
        self.servers = {
            "inventory": "mcp_servers/inventory_mcp.py",
            "recipe": "mcp_servers/recipe_mcp.py",
            "recipe_history": "mcp_servers/recipe_history_mcp.py"
        }
        
        # ツール名とMCPサーバーの対応表
        self.tool_server_mapping = {
            "inventory_add": "inventory",
            "inventory_list": "inventory",
            "inventory_list_by_name": "inventory",
            "inventory_get": "inventory",
            "inventory_update_by_id": "inventory",
            "inventory_update_by_name": "inventory",
            "inventory_update_by_name_oldest": "inventory",
            "inventory_update_by_name_latest": "inventory",
            "inventory_delete_by_id": "inventory",
            "inventory_delete_by_name": "inventory",
            "inventory_delete_by_name_oldest": "inventory",
            "inventory_delete_by_name_latest": "inventory",
            "generate_menu_plan_with_history": "recipe",
            "generate_menu_with_llm_constraints": "recipe",
            "get_recipe_history_for_user": "recipe",
            "search_menu_from_rag_with_history": "recipe",
            "search_recipe_from_web": "recipe",
            "generate_proposals": "recipe",
            "history_add": "recipe_history",
            "history_list": "recipe_history",
            "history_update_by_id": "recipe_history",
            "history_delete_by_id": "recipe_history",
            "history_get_recent_titles": "recipe_history",
        }
    
    def get_supabase_client(self) -> Client:
        """Supabaseクライアントを取得"""
        if self._client is None:
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client
    
    def verify_auth_token(self, token: str) -> bool:
        """認証トークンを検証"""
        try:
            # 空トークンや無効なトークンのチェック
            if not token or token.strip() == "":
                self.logger.warning("⚠️ [MCP] Empty or invalid token provided")
                return False
            
            client = self.get_supabase_client()
            user = client.auth.get_user(token)
            is_valid = user is not None
            self.logger.debug(f"🔐 [MCP] Token verification: {'Valid' if is_valid else 'Invalid'}")
            return is_valid
        except Exception as e:
            self.logger.error(f"❌ [MCP] Token verification failed: {e}")
            return False
    
    def get_authenticated_client(self, token: str) -> Client:
        """認証済みのSupabaseクライアントを取得"""
        if not self.verify_auth_token(token):
            raise ValueError("Invalid authentication token")
        
        client = self.get_supabase_client()
        client.auth.set_session(token)
        self.logger.debug("🔐 [MCP] Authenticated client created")
        return client
    
    async def _get_mcp_client(self, server_name: str):
        """指定されたサーバー名のMCPクライアントを取得（stdio接続）"""
        if server_name not in self.mcp_clients:
            server_path = self.servers[server_name]
            
            try:
                # FastMCPクライアントでサーバーファイルにstdio接続
                from fastmcp.client import Client
                self.mcp_clients[server_name] = Client(server_path)
                self.logger.debug(f"🔧 [MCP] MCP client created for {server_name} via stdio")
                
            except Exception as e:
                self.logger.error(f"❌ [MCP] Failed to create MCP client for {server_name}: {e}")
                raise
        
        return self.mcp_clients[server_name]
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any], token: str) -> Dict[str, Any]:
        """FastMCPクライアントでツールを呼び出し（stdio接続）"""
        self.logger.debug(f"🔧 [MCP] Calling tool")
        self.logger.debug(f"🔍 [MCP] Tool name: {tool_name}")
        self.logger.debug(f"📝 [MCP] Parameters: {parameters}")
        
        try:
            # 認証確認（空トークンの場合は警告して続行）
            if not token or token.strip() == "":
                self.logger.warning("⚠️ [MCP] No token provided, proceeding without authentication")
            elif not self.verify_auth_token(token):
                raise ValueError("Authentication failed")
            
            # ツール名から適切なサーバーを特定
            server_name = self.tool_server_mapping.get(tool_name)
            if not server_name:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            # FastMCPクライアントを取得
            mcp_client = await self._get_mcp_client(server_name)
            
            # token を parameters に追加
            parameters_with_token = parameters.copy()
            parameters_with_token['token'] = token

            # stdio接続でツールを呼び出し
            async with mcp_client:
                call_result = await mcp_client.call_tool(tool_name, parameters_with_token)
            
            # CallToolResultから実際のデータを抽出
            if hasattr(call_result, 'structured_content') and call_result.structured_content:
                # structured_contentが利用可能な場合
                actual_result = call_result.structured_content
            elif hasattr(call_result, 'data') and call_result.data:
                # data属性が利用可能な場合
                actual_result = call_result.data
            else:
                # フォールバック: contentからテキストを抽出
                if hasattr(call_result, 'content') and call_result.content:
                    import json
                    try:
                        # テキストコンテンツからJSONを解析
                        text_content = call_result.content[0].text if call_result.content else '{}'
                        actual_result = json.loads(text_content)
                    except (json.JSONDecodeError, IndexError, AttributeError):
                        actual_result = {'success': False, 'error': 'Failed to parse result'}
                else:
                    actual_result = {'success': False, 'error': 'No result data available'}
            
            self.logger.debug(f"✅ [MCP] Tool completed successfully")
            self.logger.debug(f"🔍 [MCP] Tool name: {tool_name}")
            self.logger.debug(f"📊 [MCP] Result: {actual_result}")
            
            return {
                "success": True,
                "result": actual_result,
                "tool": tool_name
            }
            
        except Exception as e:
            self.logger.error(f"❌ [MCP] Tool {tool_name} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        self.logger.info("🔧 [MCP] MCPクライアントのクリーンアップ")
        # 必要に応じてリソースのクリーンアップ処理を追加
        self.mcp_clients.clear()


# テスト実行
if __name__ == "__main__":
    print("🧪 Testing MCP Client...")
    
    try:
        client = MCPClient()
        print("✅ MCP Client created successfully")
        
        # テスト用のトークン（実際のテストでは認証ユーティリティを使用）
        test_token = "test_token"
        
        # 認証テスト
        is_valid = client.verify_auth_token(test_token)
        print(f"🔐 Token verification: {'Valid' if is_valid else 'Invalid'}")
        
        print("🎉 MCP Client test completed!")
        
    except Exception as e:
        print(f"❌ MCP Client test failed: {e}")