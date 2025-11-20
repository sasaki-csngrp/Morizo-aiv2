#!/usr/bin/env python3
"""
ServiceCoordinator - サービス調整専門クラス

Core LayerとService Layerの橋渡しを担当
ToolRouterの一元管理とサービス呼び出しの調整を提供
"""

from typing import Dict, Any
from services.tool_router import ToolRouter
from config.loggers import GenericLogger


class ServiceCoordinator:
    """サービス調整クラス - ToolRouterの一元管理とサービス呼び出しの調整"""
    
    def __init__(self):
        """初期化"""
        self.tool_router = ToolRouter()
        self.logger = GenericLogger("core", "service_coordinator")
    
    async def execute_service(self, service: str, method: str, parameters: Dict[str, Any], token: str) -> Any:
        """サービスメソッドの実行"""
        try:
            # Phase 3A: 提案タスク実行前に主要食材をセッションに保存
            if service == "recipe_service" and method == "generate_proposals":
                sse_session_id = parameters.get("sse_session_id")
                if sse_session_id:
                    from services.session_service import session_service
                    
                    # セッションが存在しない場合は作成
                    user_id = parameters.get("user_id")
                    session = await session_service.get_session(sse_session_id, user_id)
                    if not session:
                        if user_id:
                            # 指定IDでセッションを作成
                            session = await session_service.create_session(user_id, sse_session_id)
                            self.logger.info(f"✅ [ServiceCoordinator] Created new session with ID: {sse_session_id}")
                    
                    if session:
                        main_ingredient = parameters.get("main_ingredient")
                        menu_type = parameters.get("menu_type", "")
                        inventory_items = parameters.get("inventory_items")
                        category_detail_keyword = parameters.get("category_detail_keyword")
                        
                        # セッションコンテキストを保存
                        session.set_context("main_ingredient", main_ingredient)
                        session.set_context("menu_type", menu_type)
                        if inventory_items:
                            session.set_context("inventory_items", inventory_items)
                        if category_detail_keyword:
                            session.set_context("category_detail_keyword", category_detail_keyword)
                        self.logger.debug(f"💾 [ServiceCoordinator] Saved main_ingredient='{main_ingredient}' and menu_type='{menu_type}' to session")
                        if category_detail_keyword:
                            self.logger.debug(f"💾 [ServiceCoordinator] Saved category_detail_keyword='{category_detail_keyword}' to session")
                        
                        # Phase 3A: セッション内の提案済みレシピを取得してexcluded_recipesに追加
                        category = parameters.get("category", "main")
                        proposed_titles = session.get_proposed_recipes(category)
                        
                        if proposed_titles:
                            excluded_recipes = parameters.get("excluded_recipes", [])
                            if not isinstance(excluded_recipes, list):
                                excluded_recipes = []
                            
                            # 提案済みレシピを除外リストに追加（重複回避）
                            all_excluded = excluded_recipes.copy()
                            for title in proposed_titles:
                                if title not in all_excluded:
                                    all_excluded.append(title)
                            
                            parameters["excluded_recipes"] = all_excluded
                            self.logger.debug(f"📝 [ServiceCoordinator] Added {len(proposed_titles)} proposed {category} recipes to excluded list (total: {len(all_excluded)} recipes)")
                        else:
                            self.logger.debug(f"📝 [ServiceCoordinator] No proposed {category} recipes found in session")
                
                # Phase 3A: sse_session_idはMCPツールに渡す必要があるため、削除しない
                self.logger.debug(f"🔧 [ServiceCoordinator] Passing sse_session_id to MCP tool for session-based exclusion")
            
            # ToolRouterのroute_service_methodを使用してサービス名・メソッド名からMCPツールをルーティング
            result = await self.tool_router.route_service_method(service, method, parameters, token)
            
            # Check for ambiguity detection
            if isinstance(result, dict) and result.get("status") == "ambiguity_detected":
                from .exceptions import AmbiguityDetected
                raise AmbiguityDetected(
                    context=result.get("context", {}),
                    message=result.get("message", "Ambiguity detected")
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Service execution failed: {service}.{method} - {str(e)}")
            raise
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """利用可能なツールの説明を取得"""
        try:
            self.logger.debug(f"🔧 [ServiceCoordinator] Getting tool descriptions")
            descriptions = self.tool_router.get_tool_descriptions()
            self.logger.debug(f"✅ [ServiceCoordinator] Retrieved {len(descriptions)} tool descriptions")
            return descriptions
        except Exception as e:
            self.logger.error(f"❌ [ServiceCoordinator] Error getting tool descriptions: {e}")
            return {}
    
    def get_available_tools_description(self) -> str:
        """利用可能なツールの説明を文字列形式で取得"""
        try:
            self.logger.debug(f"🔧 [ServiceCoordinator] Getting available tools description")
            
            tool_descriptions = self.get_tool_descriptions()
            
            description_text = "利用可能なツール:\n"
            for tool_name, description in tool_descriptions.items():
                description_text += f"- {tool_name}: {description}\n"
            
            self.logger.debug(f"✅ [ServiceCoordinator] Tools description generated successfully")
            return description_text
            
        except Exception as e:
            self.logger.error(f"❌ [ServiceCoordinator] Error in get_available_tools_description: {e}")
            return "ツール情報の取得に失敗しました。"
