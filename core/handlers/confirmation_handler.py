"""
ConfirmationHandler: Handles confirmation process when ambiguity is detected.

This handler manages the confirmation flow including:
- Handling confirmation requests
- Resuming from confirmation
- Creating confirmation messages
- Integrating confirmation responses
"""

from typing import Optional, Dict, Any, Callable
from datetime import datetime
from ..models import TaskChainManager, ExecutionResult
from services.confirmation_service import ConfirmationService
from services.session_service import SessionService
from ..executor import TaskExecutor
from ..response_formatter import ResponseFormatter
from config.loggers import GenericLogger


class ConfirmationHandler:
    """Handles confirmation process when ambiguity is detected."""
    
    def __init__(
        self,
        session_service: SessionService,
        confirmation_service: ConfirmationService,
        task_executor: TaskExecutor,
        response_formatter: ResponseFormatter,
        process_request_callback: Callable = None
    ):
        self.logger = GenericLogger("core", "confirmation_handler")
        self.session_service = session_service
        self.confirmation_service = confirmation_service
        self.task_executor = task_executor
        self.response_formatter = response_formatter
        self.process_request_callback = process_request_callback
    
    async def handle_confirmation(
        self,
        execution_result: ExecutionResult,
        user_id: str,
        task_chain_manager: TaskChainManager,
        token: str,
        user_request: str
    ) -> dict:
        """Handle confirmation process when ambiguity is detected."""
        try:
            self.logger.info(f"🤝 [CONFIRMATION] Starting confirmation handling")
            self.logger.debug(f"🔍 [CONFIRMATION] User ID: {user_id}")
            
            # Pause execution for confirmation
            task_chain_manager.pause_for_confirmation()
            self.logger.info(f"⏸️ [CONFIRMATION] Execution paused for user confirmation")
            
            # Process confirmation with user
            confirmation_context = execution_result.confirmation_context
            if not confirmation_context:
                self.logger.error(f"❌ [CONFIRMATION] Confirmation context is missing")
                return {
                    "response": "確認情報が不足しています。",
                    "requires_confirmation": False
                }
            
            # 元のタスク情報を保持
            ambiguity_info = confirmation_context.get("ambiguity_info")
            original_tasks = confirmation_context.get("original_tasks", [])
            
            # Phase 1E: セッションに確認コンテキストを保存
            if task_chain_manager.sse_session_id:
                session = await self.session_service.get_session(task_chain_manager.sse_session_id, user_id)
                if not session:
                    # 指定IDでセッションを作成
                    session = await self.session_service.create_session(user_id, task_chain_manager.sse_session_id)
                    self.logger.info(f"✅ [CONFIRMATION] Created new session with ID: {task_chain_manager.sse_session_id}")
                
                confirmation_message = execution_result.message if hasattr(execution_result, 'message') else ""
                session.set_ambiguity_confirmation(
                    original_request=user_request,  # 元のユーザーリクエスト
                    question=confirmation_message,  # 確認質問
                    ambiguity_details=ambiguity_info.details if hasattr(ambiguity_info, 'details') else {}
                )
                self.logger.info(f"💾 [CONFIRMATION] Confirmation context saved to session")
            
            # 状態を保存
            state_data = {
                'task_chain_manager': task_chain_manager,
                'execution_result': execution_result,
                'original_tasks': original_tasks,
                'ambiguity_info': ambiguity_info,
                'created_at': datetime.now(),
                'user_id': user_id,
                'token': token
            }
            
            await self.session_service.save_confirmation_state(
                task_chain_manager.sse_session_id,
                user_id,
                state_data
            )
            self.logger.debug(f"💾 [CONFIRMATION] Confirmation state saved for session: {task_chain_manager.sse_session_id}")
            
            # ユーザーに確認メッセージを返す（次のリクエストで再開）
            # 曖昧性のタイプに応じて適切なメソッドを呼び出す
            if hasattr(ambiguity_info, 'details') and ambiguity_info.details.get("type") == "main_ingredient_optional_selection":
                confirmation_message = self.create_menu_confirmation_message(ambiguity_info)
            else:
                confirmation_message = self.create_confirmation_message(ambiguity_info)
            
            # デバッグログ: ambiguity_infoの詳細を出力
            self.logger.debug(f"🔍 [CONFIRMATION] Ambiguity info details: {ambiguity_info.details if hasattr(ambiguity_info, 'details') else 'No details'}")
            self.logger.debug(f"📝 [CONFIRMATION] Confirmation message: {confirmation_message}")
            
            result_dict = {
                "response": confirmation_message,
                "requires_confirmation": True,
                "confirmation_session_id": task_chain_manager.sse_session_id
            }
            
            # デバッグログ: 戻り値の辞書を出力
            self.logger.debug(f"📤 [CONFIRMATION] Returning confirmation result: {result_dict}")
            
            return result_dict
                
        except Exception as e:
            self.logger.error(f"❌ [CONFIRMATION] Confirmation handling failed: {str(e)}")
            return {
                "response": f"確認処理中にエラーが発生しました: {str(e)}",
                "requires_confirmation": False
            }
    
    async def resume_from_confirmation(
        self,
        saved_state: Dict[str, Any],
        user_response: str,
        user_id: str,
        token: str,
        sse_session_id: str
    ) -> Any:
        """
        保存された状態から曖昧性解決を再開
        
        Args:
            saved_state: 保存された状態
            user_response: ユーザーの回答（例：「最新のでお願い」）
            user_id: ユーザーID
            token: 認証トークン
            sse_session_id: SSEセッションID
        """
        try:
            self.logger.info(f"🔄 [CONFIRMATION] Resuming from confirmation for session: {sse_session_id}")
            
            # 保存された状態を復元
            task_chain_manager = saved_state['task_chain_manager']
            original_tasks = saved_state['original_tasks']
            ambiguity_info = saved_state['ambiguity_info']
            
            # Phase 1E: 曖昧性解消の場合は、コンテキスト統合を行う
            if hasattr(ambiguity_info, 'details') and ambiguity_info.details.get("type") == "main_ingredient_optional_selection":
                # 元のユーザーリクエストを取得（セッションから）
                session = await self.session_service.get_session(sse_session_id, user_id)
                if session and session.confirmation_context.get("original_request"):
                    original_request = session.confirmation_context.get("original_request")
                    
                    # コンテキスト統合
                    integrated_request = await self.integrate_confirmation_response(
                        original_request,
                        user_response,
                        ambiguity_info.details
                    )
                    
                    # 確認コンテキストをクリア
                    session.clear_confirmation_context()
                    
                    # 統合されたリクエストで通常のプランニングループを実行
                    self.logger.debug(f"▶️ [CONFIRMATION] Resuming planning loop with integrated request: {integrated_request}")
                    if self.process_request_callback:
                        result = await self.process_request_callback(integrated_request, user_id, token, sse_session_id, False)
                        return result
                    else:
                        self.logger.error(f"❌ [CONFIRMATION] process_request_callback not set")
                        return f"内部エラー: プロセス要求コールバックが設定されていません"
            
            # 既存の処理（在庫操作確認等）
            confirmation_context = {
                'ambiguity_info': ambiguity_info,
                'user_response': user_response,
                'original_tasks': original_tasks
            }
            
            confirmation_result = await self.confirmation_service.process_confirmation(
                ambiguity_info, user_response, confirmation_context, original_tasks
            )
            
            if confirmation_result.is_cancelled:
                await self.session_service.clear_confirmation_state(sse_session_id)
                return "操作はキャンセルされました。"
            
            # タスクを更新
            updated_tasks = await self.confirmation_service.maintain_task_chain(
                original_tasks, confirmation_result
            )
            
            # 実行再開
            task_chain_manager.resume_execution()
            task_chain_manager.set_tasks(updated_tasks)
            
            # ★ここでTaskExecutor再実行（ActionPlannerはスキップ）
            final_execution_result = await self.task_executor.execute(
                updated_tasks, user_id, task_chain_manager, token
            )
            
            # 状態をクリア
            await self.session_service.clear_confirmation_state(sse_session_id)
            
            # 最終レスポンス生成
            if final_execution_result.status == "success":
                final_response, menu_data = await self.response_formatter.format(final_execution_result.outputs, sse_session_id)
                task_chain_manager.send_complete(final_response, menu_data)
                return final_response
            else:
                return f"確認後のタスク実行中にエラーが発生しました: {final_execution_result.message}"
        
        except Exception as e:
            self.logger.error(f"❌ [CONFIRMATION] Resume from confirmation failed: {e}")
            await self.session_service.clear_confirmation_state(sse_session_id)
            return f"確認処理の再開中にエラーが発生しました: {str(e)}"
    
    def create_confirmation_message(self, ambiguity_info) -> str:
        """
        曖昧性情報から確認メッセージを生成
        
        Args:
            ambiguity_info: 曖昧性情報
            
        Returns:
            確認メッセージ
        """
        try:
            if not ambiguity_info:
                return "複数の選択肢があります。どちらを選択しますか？"
            
            # 曖昧性の詳細を取得
            details = ambiguity_info.details if hasattr(ambiguity_info, 'details') else {}
            tool_name = ambiguity_info.tool_name if hasattr(ambiguity_info, 'tool_name') else "操作"
            
            # 在庫操作の場合の確認メッセージ
            if tool_name.startswith("inventory_"):
                if 'items' in details:
                    items = details['items']
                    if len(items) > 1:
                        item_name = items[0].get('item_name', 'アイテム')
                        operation = "削除" if "delete" in tool_name else "更新"
                        
                        message = f"「{item_name}」が{len(items)}件見つかりました。\n\n"
                        for i, item in enumerate(items, 1):
                            message += f"アイテム{i}:\n"
                            if 'quantity' in item:
                                message += f"  数量: {item['quantity']} {item.get('unit', '')}\n"
                            if 'storage_location' in item and item['storage_location']:
                                message += f"  保存場所: {item['storage_location']}\n"
                            if 'expiry_date' in item and item['expiry_date']:
                                message += f"  期限: {item['expiry_date']}\n"
                            if 'created_at' in item:
                                message += f"  追加日: {item['created_at']}\n"
                            message += "\n"
                        
                        message += "以下のいずれかを選択してください：\n"
                        message += "- 「最新の」または「新しい」: 最も最近追加されたもの\n"
                        message += "- 「古い」または「古いの」: 最も古いもの\n"
                        message += "- 「全部」または「すべて」: 全てのアイテム\n"
                        message += "- 「キャンセル」: 操作を中止"
                        return message
                
                # itemsがない場合のフォールバック
                return f"複数のアイテムが見つかりました。どれを{tool_name.replace('inventory_', '').replace('_', ' ')}しますか？"
            
            # デフォルトメッセージ
            return "複数の選択肢があります。どちらを選択しますか？"
            
        except Exception as e:
            self.logger.error(f"❌ [CONFIRMATION] Error creating confirmation message: {e}")
            return "複数の選択肢があります。どちらを選択しますか？"
    
    def create_menu_confirmation_message(self, ambiguity_info) -> str:
        """
        献立提案の曖昧性情報から確認メッセージを生成
        
        Args:
            ambiguity_info: 曖昧性情報
            
        Returns:
            確認メッセージ
        """
        details = ambiguity_info.details if hasattr(ambiguity_info, 'details') else {}
        return details.get("message", "複数の選択肢があります。どちらを選択しますか？")
    
    async def integrate_confirmation_response(
        self, 
        original_request: str,  # 「主菜を教えて」
        user_response: str,     # 「レンコンでお願い」
        confirmation_context: Dict[str, Any]  # 確認時のコンテキスト
    ) -> str:
        """
        元のリクエストとユーザー回答を統合して、
        完全なリクエストを生成する
        
        例:
        - 元: 「主菜を教えて」
        - 回答: 「レンコンでお願い」
        - 結果: 「レンコンの主菜を教えて」
        """
        
        self.logger.debug(f"🔗 [CONFIRMATION] Integrating request")
        self.logger.debug(f"  Original: {original_request}")
        self.logger.debug(f"  Response: {user_response}")
        
        # パターン1: 「指定しない」系の回答
        proceed_keywords = ["いいえ", "そのまま", "提案して", "在庫から", "このまま", "進めて", "指定しない", "2"]
        if any(keyword in user_response for keyword in proceed_keywords):
            # 元のリクエストをそのまま使用
            integrated_request = original_request
            self.logger.debug(f"✅ [CONFIRMATION] Integrated (proceed): {integrated_request}")
            return integrated_request
        
        # パターン2: 食材名が含まれている
        # 簡易的な統合（LLMを使わない方式）
        # 「レンコン」「レンコンで」「レンコンを使って」等を抽出
        ingredient = self.extract_ingredient_simple(user_response)
        
        if ingredient:
            # 元のリクエストに食材を追加
            # 「主菜を教えて」→「レンコンの主菜を教えて」
            if "主菜" in original_request or "メイン" in original_request:
                integrated_request = f"{ingredient}の主菜を教えて"
            elif "料理" in original_request:
                integrated_request = f"{ingredient}の料理を教えて"
            else:
                integrated_request = f"{ingredient}を使って{original_request}"
            
            self.logger.debug(f"✅ [CONFIRMATION] Integrated (ingredient): {integrated_request}")
            return integrated_request
        
        # パターン3: 統合できない場合は元のリクエストを返す
        self.logger.warning(f"⚠️ [CONFIRMATION] Could not integrate, using original request")
        return original_request
    
    def extract_ingredient_simple(self, user_response: str) -> Optional[str]:
        """ユーザー応答から食材名を簡易抽出"""
        
        # 助詞を除去
        cleaned = user_response.replace("で", "").replace("を", "").replace("が", "")
        cleaned = cleaned.replace("使って", "").replace("お願い", "").replace("ください", "")
        cleaned = cleaned.strip()
        
        # 空でなければ食材名として扱う
        if cleaned and len(cleaned) > 0:
            return cleaned
        
        return None

