"""
TrueReactAgent: Main orchestrator for the core layer.

This component coordinates the entire ReAct loop, orchestrating:
- Task planning (via ActionPlanner)
- Task execution (via TaskExecutor)
- Confirmation handling (via ConfirmationHandler)
- User selection processing (via SelectionHandler)
- Stage management (via StageManager)
- Response formatting (via ResponseFormatter)
"""

from typing import Optional, Dict, Any
from .models import TaskChainManager, ExecutionResult
from .planner import ActionPlanner
from .executor import TaskExecutor
from .service_coordinator import ServiceCoordinator
from .response_formatter import ResponseFormatter
from .handlers.confirmation_handler import ConfirmationHandler
from .handlers.selection_handler import SelectionHandler
from .handlers.stage_manager import StageManager
from services.confirmation_service import ConfirmationService
from config.loggers import GenericLogger
from core.help_handler import HelpHandler


class TrueReactAgent:
    """
    Main orchestrator for the unified ReAct agent.
    
    This component coordinates the entire process from user request
    to final response, managing task planning, execution, and confirmation.
    """
    
    def __init__(self):
        self.logger = GenericLogger("core", "agent")
        self.action_planner = ActionPlanner()
        self.service_coordinator = ServiceCoordinator()
        self.confirmation_service = ConfirmationService(self.service_coordinator.tool_router)
        self.task_executor = TaskExecutor(self.service_coordinator, self.confirmation_service)
        self.response_formatter = ResponseFormatter()
        from services.session_service import SessionService
        self.session_service = SessionService()
        
        # Handler initialization
        # Note: Callbacks are set later to avoid circular references
        self.confirmation_handler = ConfirmationHandler(
            session_service=self.session_service,
            confirmation_service=self.confirmation_service,
            task_executor=self.task_executor,
            response_formatter=self.response_formatter,
            process_request_callback=None
        )
        self.stage_manager = StageManager(session_service=self.session_service)
        self.selection_handler = SelectionHandler(
            session_service=self.session_service,
            process_request_callback=None,
            stage_manager=self.stage_manager
        )
    
    def _set_confirmation_handler_callback(self):
        """Set ConfirmationHandler callback (called after initialization to avoid circular references)"""
        self.confirmation_handler.process_request_callback = self.process_request
    
    def _set_selection_handler_callbacks(self):
        """Set SelectionHandler callback (called after initialization to avoid circular references)"""
        self.selection_handler.process_request_callback = self.process_request
    
    async def process_request(self, user_request: str, user_id: str, token: str, sse_session_id: Optional[str] = None, is_confirmation_response: bool = False) -> Dict[str, Any]:
        """
        Process user request through the complete ReAct loop.
        
        Args:
            user_request: User's natural language request
            user_id: User identifier
            token: Authentication token
            sse_session_id: Optional SSE session ID for progress tracking
            is_confirmation_response: Whether this is a response to confirmation request
            
        Returns:
            Final response string
        """
        # Set callbacks on first invocation (to avoid circular references)
        if self.confirmation_handler.process_request_callback is None:
            self._set_confirmation_handler_callback()
        if self.selection_handler.process_request_callback is None:
            self._set_selection_handler_callbacks()
        
        try:
            self.logger.info(f"🎯 [AGENT] Starting request processing")
            self.logger.debug(f"🔍 [AGENT] User ID: {user_id}")
            self.logger.info(f"📝 [AGENT] User request: '{user_request}'")
            self.logger.debug(f"🔄 [AGENT] Is confirmation response: {is_confirmation_response}")
            
            # ============================================================
            # ヘルプ機能の処理（通常のタスク処理より優先）
            # ============================================================
            help_handler = HelpHandler()
            # セッションIDがなくても、ユーザーID単位でヘルプ状態を検索できる
            help_state = await self.session_service.get_help_state(sse_session_id, user_id)
            
            # ヘルプキーワードの検知（誤検知防止のため、明確なキーワードのみ）
            is_help_request = self._is_help_keyword(user_request)
            
            if is_help_request or help_state:
                # ヘルプモードの処理
                response = await self._handle_help_mode(
                    user_request=user_request,
                    help_state=help_state,
                    help_handler=help_handler,
                    sse_session_id=sse_session_id,
                    user_id=user_id
                )
                if response:
                    # ヘルプ応答の場合もSSE完了イベントを送信（モバイルアプリ対応）
                    # HTTPレスポンスとSSE完了イベントの両方を返す
                    if sse_session_id:
                        task_chain_manager = TaskChainManager(sse_session_id)
                        task_chain_manager.send_complete(response)
                    return {"response": response}
                # responseがNoneの場合は通常処理に進む
            
            # ============================================================
            # 通常のタスク処理（既存の処理）
            # ============================================================
            
            # Handle confirmation response if needed
            if is_confirmation_response and sse_session_id:
                saved_state = await self.session_service.get_confirmation_state(sse_session_id)
                if saved_state:
                    self.logger.info(f"🔄 [AGENT] Resuming from confirmation")
                    return await self.confirmation_handler.resume_from_confirmation(
                        saved_state, user_request, user_id, token, sse_session_id
                    )
                else:
                    self.logger.warning(f"⚠️ [AGENT] Confirmation response but no saved state found for session: {sse_session_id}")
            
            # Initialize task chain manager
            task_chain_manager = TaskChainManager(sse_session_id)
            self.logger.info(f"🔗 [AGENT] TaskChainManager initialized")
            
            # Step 1: Planning - Generate task list
            self.logger.info(f"📋 [AGENT] Starting planning phase...")
            tasks = await self.action_planner.plan(user_request, user_id, sse_session_id)
            
            # Inject session context for additional proposals
            if sse_session_id and any(t.parameters.get("inventory_items", "").startswith("session.context.") for t in tasks):
                self.logger.info(f"🔄 [AGENT] Detected session context references, injecting values")
                for task in tasks:
                    for key, value in task.parameters.items():
                        if isinstance(value, str) and value.startswith("session.context."):
                            context_key = value.replace("session.context.", "")
                            context_value = await self.session_service.get_session_context(
                                sse_session_id, context_key, None
                            )
                            task.parameters[key] = context_value
                            self.logger.debug(f"💾 [AGENT] Injected session context: {context_key} = {context_value}")
            task_chain_manager.set_tasks(tasks)
            self.logger.info(f"✅ [AGENT] Planning phase completed: {len(tasks)} tasks generated")
            
            # Step 2: Execution - Execute tasks
            self.logger.info(f"⚙️ [AGENT] Starting execution phase...")
            execution_result = await self.task_executor.execute(
                tasks, user_id, task_chain_manager, token
            )
            self.logger.info(f"✅ [AGENT] Execution phase completed: status={execution_result.status}")
            
            # Step 3: Handle confirmation if needed
            if execution_result.status == "needs_confirmation":
                self.logger.info(f"⚠️ [AGENT] Confirmation required, handling user interaction...")
                confirmation_result = await self.confirmation_handler.handle_confirmation(
                    execution_result, user_id, task_chain_manager, token, user_request
                )
                
                if confirmation_result.get("requires_confirmation"):
                    task_chain_manager.send_complete(
                        confirmation_result["response"],
                        confirmation_data={
                            "requires_confirmation": True,
                            "confirmation_session_id": confirmation_result["confirmation_session_id"]
                        }
                    )
                    return confirmation_result
                else:
                    return confirmation_result["response"]
            
            # Step 4: Format final response
            if execution_result.status == "success":
                self.logger.info(f"📄 [AGENT] Starting response formatting...")
                final_response, menu_data = await self.response_formatter.format(execution_result.outputs, sse_session_id)
                self.logger.debug(f"🔍 [AGENT] Menu data received: {menu_data is not None}")
                if menu_data:
                    self.logger.debug(f"📊 [AGENT] Menu data size: {len(str(menu_data))} characters")
                task_chain_manager.send_complete(final_response, menu_data)
                self.logger.info(f"✅ [AGENT] Response formatting completed")
                self.logger.info(f"🎉 [AGENT] Request processing completed successfully")
                
                # Return selection UI data if needed
                if menu_data and isinstance(menu_data, dict) and menu_data.get("requires_selection"):
                    return {
                        "response": final_response,
                        "requires_selection": menu_data.get("requires_selection", False),
                        "candidates": menu_data.get("candidates"),
                        "task_id": menu_data.get("task_id"),
                        "message": menu_data.get("message", "選択してください"),
                        "current_stage": menu_data.get("current_stage"),
                        "used_ingredients": menu_data.get("used_ingredients"),
                        "menu_category": menu_data.get("menu_category")
                    }
                else:
                    return {"response": final_response}
            else:
                error_msg = f"タスクの実行中にエラーが発生しました: {execution_result.message}"
                self.logger.error(f"❌ [AGENT] Execution failed: {execution_result.message}")
                return {"response": error_msg}
                
        except Exception as e:
            self.logger.error(f"❌ [AGENT] Request processing failed: {str(e)}")
            return {"response": f"リクエストの処理中にエラーが発生しました: {str(e)}"}
    
    async def handle_user_selection_required(self, candidates: list, context: dict, task_chain_manager: TaskChainManager) -> dict:
        """Handle user selection required (delegates to SelectionHandler)"""
        return await self.selection_handler.handle_user_selection_required(candidates, context, task_chain_manager)
    
    async def process_user_selection(self, task_id: str, selection: int, sse_session_id: str, user_id: str, token: str, old_sse_session_id: str = None) -> dict:
        """Process user selection (delegates to SelectionHandler)"""
        # Set callback on first invocation (to avoid circular references)
        if self.selection_handler.process_request_callback is None:
            self._set_selection_handler_callbacks()
        return await self.selection_handler.process_user_selection(task_id, selection, sse_session_id, user_id, token, old_sse_session_id)
    
    def _is_help_keyword(self, user_request: str) -> bool:
        """ヘルプキーワードを検知（誤検知防止）"""
        help_keywords = [
            "使い方を教えて",
            "使い方を知りたい",
            "使い方を説明して",
            "ヘルプ",
            "help"
        ]
        
        user_request_lower = user_request.strip().lower()
        
        # 「使い方を教えて」などの明確な表現のみ検知
        # 「使い方」だけでは検知しない（誤検知防止）
        for keyword in help_keywords:
            if keyword in user_request_lower:
                # 「使い方」単独の場合は、前後に特定の文字がある場合のみ検知
                # ただし、現在のhelp_keywordsには「使い方」単独は含まれていないため、
                # この処理は将来の拡張に備えた実装
                if keyword == "使い方":
                    # 「使い方を」や「使い方は」などの完全一致を要求
                    patterns = ["使い方を", "使い方は", "使い方について", "使い方って", "使い方 教えて"]
                    if not any(pattern in user_request_lower for pattern in patterns):
                        continue
                return True
        
        return False
    
    async def _handle_help_mode(
        self,
        user_request: str,
        help_state: Optional[str],
        help_handler: HelpHandler,
        sse_session_id: Optional[str],
        user_id: str
    ) -> Optional[str]:
        """ヘルプモードの処理
        
        Args:
            user_request: ユーザーのリクエスト
            help_state: 現在のヘルプ状態（None, "overview", "detail_1-5"）
            help_handler: HelpHandlerインスタンス
            sse_session_id: SSEセッションID
            user_id: ユーザーID
        
        Returns:
            ヘルプ応答文字列（通常処理に進む場合はNone）
        """
        user_request_stripped = user_request.strip()
        self.logger.debug(f"🔍 [HELP] Processing help mode: request='{user_request}', state={help_state}")
        
        # 数字入力の検知（1-5）
        if user_request_stripped.isdigit():
            detail_number = int(user_request_stripped)
            if 1 <= detail_number <= 5:
                # 機能別詳細の表示
                detail_response = help_handler.generate_detail(detail_number)
                if detail_response:
                    # セッション状態を更新
                    if sse_session_id:
                        await self.session_service.set_help_state(
                            sse_session_id, user_id, f"detail_{detail_number}"
                        )
                    self.logger.info(f"📖 [HELP] Showing detail for feature {detail_number}")
                    return detail_response
        
        # ヘルプキーワードの検知（全体概要の表示）
        if self._is_help_keyword(user_request):
            # セッション状態を更新
            if sse_session_id:
                await self.session_service.set_help_state(
                    sse_session_id, user_id, "overview"
                )
            self.logger.info(f"📖 [HELP] Showing overview")
            return help_handler.generate_overview()
        
        # 既にヘルプモードの場合（help_stateが設定されている）
        if help_state:
            # 数字入力を再度チェック（セッションから復元した場合）
            if user_request_stripped.isdigit():
                detail_number = int(user_request_stripped)
                if 1 <= detail_number <= 5:
                    detail_response = help_handler.generate_detail(detail_number)
                    if detail_response:
                        if sse_session_id:
                            await self.session_service.set_help_state(
                                sse_session_id, user_id, f"detail_{detail_number}"
                            )
                        self.logger.info(f"📖 [HELP] Showing detail for feature {detail_number}")
                        return detail_response
            
            # ヘルプモード中に通常のチャット入力があった場合
            # ヘルプモードを終了して通常処理に進む
            self.logger.info(f"🔄 [HELP] Exiting help mode for normal chat")
            if sse_session_id:
                await self.session_service.clear_help_state(sse_session_id, user_id)
            # Noneを返すと、通常のタスク処理に進む
            return None
        
        # デフォルト: ヘルプモードを開始
        if sse_session_id:
            await self.session_service.set_help_state(
                sse_session_id, user_id, "overview"
            )
        self.logger.info(f"📖 [HELP] Starting help mode")
        return help_handler.generate_overview()
    