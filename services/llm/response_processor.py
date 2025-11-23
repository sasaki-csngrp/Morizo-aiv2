#!/usr/bin/env python3
"""
ResponseProcessor - レスポンス処理

LLMServiceから分離したレスポンス処理専用クラス
JSON解析、タスク形式変換、最終回答整形を担当
"""

import json
from typing import Dict, Any, List, Optional
from config.loggers import GenericLogger
from .utils import ResponseProcessorUtils
from .response_formatters import ResponseFormatters
from .menu_data_generator import MenuDataGenerator
from .service_handlers import InventoryServiceHandler, RecipeServiceHandler, GenericServiceHandler
from .session_info_handler import SessionInfoHandler
from .web_search_integrator import WebSearchResultIntegrator


class ResponseProcessor:
    """レスポンス処理クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response")
        self.utils = ResponseProcessorUtils()
        self.formatters = ResponseFormatters()
        self.menu_generator = MenuDataGenerator()
        from services.session_service import session_service
        self.session_service = session_service
        
        # ハンドラーの初期化
        self.inventory_handler = InventoryServiceHandler()
        self.recipe_handler = RecipeServiceHandler()
        self.generic_handler = GenericServiceHandler()
        self.stage_info_handler = SessionInfoHandler()
        self.web_integrator = WebSearchResultIntegrator()
    
    def parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        LLMレスポンスを解析してタスクリストを抽出
        
        Args:
            response: LLMからのレスポンス
        
        Returns:
            解析されたタスクリスト
        """
        try:
            self.logger.debug(f"🔧 [ResponseProcessor] Parsing LLM response")
            
            # JSON部分を抽出（```json```で囲まれている場合がある）
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response.strip()
            
            # JSON解析（{{形式の正規化処理を追加）
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # {{形式のレスポンスを正規化して再試行
                normalized_json = json_str.replace("{{", "{").replace("}}", "}")
                self.logger.warning(f"⚠️ [ResponseProcessor] JSON parse failed, trying normalized format ({{{{ -> {{)")
                try:
                    result = json.loads(normalized_json)
                except json.JSONDecodeError as e:
                    # 正規化後も失敗した場合は、元のエラーをログに記録
                    self.logger.error(f"❌ [ResponseProcessor] JSON parsing failed even after normalization: {e}")
                    self.logger.error(f"Response content: {response}")
                    return []
            
            tasks = result.get("tasks", [])
            
            self.logger.debug(f"✅ [ResponseProcessor] Parsed {len(tasks)} tasks from LLM response")
            return tasks
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ [ResponseProcessor] JSON parsing failed: {e}")
            self.logger.error(f"Response content: {response}")
            return []
        except Exception as e:
            self.logger.error(f"❌ [ResponseProcessor] Error parsing LLM response: {e}")
            return []
    
    def convert_to_task_format(self, tasks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """
        LLMタスクをActionPlannerが期待する形式に変換
        
        Args:
            tasks: LLMから取得したタスクリスト
            user_id: ユーザーID
        
        Returns:
            変換されたタスクリスト
        """
        try:
            self.logger.debug(f"🔧 [ResponseProcessor] Converting {len(tasks)} tasks to ActionPlanner format")
            
            converted_tasks = []
            for task in tasks:
                # user_idをパラメータに追加
                parameters = task.get("parameters", {})
                if "user_id" not in parameters:
                    parameters["user_id"] = user_id
                
                converted_task = {
                    "service": task.get("service"),
                    "method": task.get("method"),
                    "parameters": parameters,
                    "dependencies": task.get("dependencies", [])
                }
                converted_tasks.append(converted_task)
            
            self.logger.debug(f"✅ [ResponseProcessor] Converted {len(converted_tasks)} tasks successfully")
            return converted_tasks
            
        except Exception as e:
            self.logger.error(f"❌ [ResponseProcessor] Error converting tasks: {e}")
            return []
    
    async def format_final_response(self, results: Dict[str, Any], sse_session_id: str = None) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        最終回答整形（サービス・メソッドベース）
        
        Args:
            results: タスク実行結果辞書
            sse_session_id: SSEセッションID
        
        Returns:
            (整形された回答, JSON形式のレシピデータ)
        """
        try:
            # 献立提案シナリオかどうかを判定
            is_menu_scenario = self.utils.is_menu_scenario(results)
            
            # レスポンス構築
            response_parts, menu_data = await self._build_response_parts(results, is_menu_scenario, sse_session_id)
            
            # 空レスポンスの処理
            return self._handle_empty_response(response_parts, menu_data)
            
        except Exception as e:
            self.logger.error(f"❌ [ResponseProcessor] Error in format_final_response: {e}")
            return "タスクが完了しましたが、レスポンスの生成に失敗しました。", None
    
    async def _build_response_parts(self, results: Dict[str, Any], is_menu_scenario: bool, sse_session_id: str = None) -> tuple[List[str], Optional[Dict[str, Any]]]:
        """
        レスポンスパーツを構築
        
        Args:
            results: タスク実行結果辞書
            is_menu_scenario: 献立提案シナリオかどうか
        
        Returns:
            (レスポンスパーツリスト, JSON形式のレシピデータ)
        """
        response_parts = []
        menu_data = None
        
        # サービス・メソッドベースの処理
        for task_id, task_result in results.items():
            try:
                # タスクの成功チェック
                if not task_result.get("success"):
                    continue
                
                # サービス・メソッド情報の取得
                service = task_result.get("service", "")
                method = task_result.get("method", "")
                service_method = f"{service}.{method}"
                
                # データの取得
                data = self._extract_task_data(task_result)
                
                # サービス・メソッド別の処理
                parts, menu = await self._process_service_method(service_method, data, is_menu_scenario, task_id, results, sse_session_id)
                response_parts.extend(parts)
                
                # メニューデータの更新（最初に見つかったものを使用）
                if menu and not menu_data:
                    menu_data = menu
                    
            except Exception as e:
                self.logger.error(f"❌ [ResponseProcessor] Error processing task {task_id}: {e}")
                continue
        
        return response_parts, menu_data
    
    def _extract_task_data(self, task_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク結果からデータを抽出
        
        Args:
            task_result: タスク実行結果
        
        Returns:
            抽出されたデータ（辞書形式）
        """
        result_value = task_result.get("result", {})
        return result_value if isinstance(result_value, dict) else {}
    
    async def _process_service_method(self, service_method: str, data: Any, is_menu_scenario: bool, task_id: str, results: Dict[str, Any] = None, sse_session_id: str = None) -> tuple[List[str], Optional[Dict[str, Any]]]:
        """
        サービス・メソッド別の処理
        
        Args:
            service_method: サービス・メソッド名
            data: 処理データ
            is_menu_scenario: 献立提案シナリオかどうか
            task_id: タスクID
            results: 全タスクの実行結果
        
        Returns:
            (レスポンスパーツリスト, JSON形式のレシピデータ)
        """
        # サービス別にディスパッチ
        if service_method.startswith("inventory_service."):
            return await self.inventory_handler.handle(
                service_method, data, is_menu_scenario, sse_session_id,
                self.formatters, self.session_service
            )
        elif service_method.startswith("recipe_service."):
            return await self.recipe_handler.handle(
                service_method, data, is_menu_scenario, task_id, results, sse_session_id,
                self.formatters, self.menu_generator, self.session_service,
                self.stage_info_handler, self.web_integrator, self.utils
            )
        else:
            return self.generic_handler.handle(service_method, data, self.formatters)
    
    def _handle_empty_response(self, response_parts: List[str], menu_data: Optional[Dict[str, Any]]) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        空レスポンスの処理
        
        Args:
            response_parts: レスポンスパーツリスト
            menu_data: JSON形式のレシピデータ
        
        Returns:
            (最終レスポンス, JSON形式のレシピデータ)
        """
        # レスポンスが空の場合は適切な挨拶メッセージを返す
        if not response_parts:
            return "こんにちは！何かお手伝いできることはありますか？", None
        
        final_response = "\n".join(response_parts)
        self.logger.debug(f"🔧 [ResponseProcessor] Final response: {final_response}")
        self.logger.debug(f"✅ [ResponseProcessor] Response formatted successfully")
        
        # JSON形式のレシピデータがある場合は、レスポンスに含める
        if menu_data:
            self.logger.debug(f"📊 [ResponseProcessor] Menu data JSON generated: {len(str(menu_data))} characters")
            self.logger.debug(f"🔍 [ResponseProcessor] Menu data preview: {str(menu_data)[:200]}...")
        else:
            self.logger.debug(f"⚠️ [ResponseProcessor] No menu data generated")
        
        return final_response, menu_data
