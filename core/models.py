"""
Data models for the core layer.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from config.loggers import GenericLogger


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_USER = "waiting_for_user"


@dataclass
class Task:
    """Represents a single task to be executed."""
    
    id: str
    service: str  # "RecipeService", "InventoryService", etc.
    method: str    # "generate_menu_plan", "add_inventory", etc.
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of task execution."""
    
    status: str  # "success", "needs_confirmation", "error"
    outputs: Dict[str, Any] = field(default_factory=dict)
    confirmation_context: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class TaskChainManager:
    """Manages task chain state and SSE communication."""
    
    def __init__(self, sse_session_id: Optional[str] = None):
        self.sse_session_id = sse_session_id
        self.tasks: List[Task] = []
        self.results: Dict[str, Any] = {}
        self.is_paused = False
        self.current_step = 0
        self.total_steps = 0
        self.logger = GenericLogger("core", "task_manager")
    
    def set_tasks(self, tasks: List[Task]) -> None:
        """Set the task list for execution."""
        self.tasks = tasks
        self.total_steps = len(tasks)
        self.current_step = 0
        self.results = {}
        
        # 初期進捗送信（0/タスク数完了）
        if self.sse_session_id and self.total_steps > 0:
            # 最初のタスクの情報を使用
            first_task = tasks[0]
            task_name = self._get_task_display_name(first_task)
            self.send_progress(first_task.id, "開始", f"{task_name}を開始します")
    
    def _get_task_display_name(self, task: Task) -> str:
        """Get a user-friendly display name for a task."""
        # サービス名を正規化（小文字を大文字に変換）
        normalized_service = self._normalize_service_name(task.service)
        
        service_method_map = {
            "InventoryService": {
                "get_inventory": "在庫リスト取得",
                "add_inventory": "在庫追加",
                "update_inventory": "在庫更新",
                "delete_inventory": "在庫削除"
            },
            "RecipeService": {
                "generate_menu_plan": "献立生成",
                "generate_proposals": "レシピ提案",
                "search_recipes": "レシピ検索",
                "search_recipes_from_web": "レシピ検索",
                "search_menu_from_rag": "献立検索",
                "get_recipe_details": "レシピ詳細取得"
            },
            "LLMService": {
                "process_request": "AI処理",
                "generate_response": "レスポンス生成"
            },
            "HistoryService": {
                "history_get_recent_titles": "履歴取得"
            }
        }
        
        service_name = service_method_map.get(normalized_service, {}).get(task.method, f"{normalized_service}.{task.method}")
        return service_name
    
    def _normalize_service_name(self, service_name: str) -> str:
        """Normalize service name from lowercase to proper case."""
        service_mapping = {
            "inventory_service": "InventoryService",
            "recipe_service": "RecipeService",
            "llm_service": "LLMService",
            "session_service": "SessionService",
            "history_service": "HistoryService"
        }
        return service_mapping.get(service_name, service_name)
    
    def resume_execution(self) -> None:
        """Resume execution after confirmation."""
        self.is_paused = False
    
    def pause_for_confirmation(self) -> None:
        """Pause execution for user confirmation."""
        self.is_paused = True
        self.logger.info(f"⏸️ [TaskChainManager] Execution paused for confirmation")
    
    def send_progress(self, task_id: str, status: str, message: str = "") -> None:
        """Send progress update via SSE."""
        if self.sse_session_id:
            try:
                # SSE送信者を取得して進捗を送信
                from api.utils.sse_manager import get_sse_sender
                sse_sender = get_sse_sender()
                
                # 詳細な進捗データを構築
                progress_percentage = int((self.current_step / self.total_steps) * 100) if self.total_steps > 0 else 0
                
                # タスク名を取得（task_idが実際のタスクIDの場合）
                task_display_name = task_id
                if task_id in [task.id for task in self.tasks]:
                    # 実際のタスクが見つかった場合
                    actual_task = next(task for task in self.tasks if task.id == task_id)
                    task_display_name = self._get_task_display_name(actual_task)
                
                progress_data = {
                    "completed_tasks": self.current_step,
                    "total_tasks": self.total_steps,
                    "progress_percentage": progress_percentage,
                    "current_task": f"{task_display_name}: {status}",
                    "remaining_tasks": self.total_steps - self.current_step,
                    "is_complete": self.current_step >= self.total_steps,
                    "message": f"タスク {self.current_step}/{self.total_steps} 完了 - 進捗{progress_percentage}%"
                }
                
                # デバッグ用ログ
                self.logger.debug(f"📊 [TaskChainManager] Sending progress: {task_display_name}: {status}")
                self.logger.debug(f"📊 [TaskChainManager] Progress data: {progress_data}")
                
                # 進捗メッセージを送信
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 既にイベントループが実行中の場合は、タスクを作成
                    asyncio.create_task(sse_sender.send_progress(
                        self.sse_session_id, 
                        progress_data
                    ))
                else:
                    # イベントループが実行されていない場合は、同期的に実行
                    loop.run_until_complete(sse_sender.send_progress(
                        self.sse_session_id, 
                        progress_data
                    ))
            except Exception as e:
                # SSE送信エラーはログに記録するが、処理は継続
                import logging
                logger = logging.getLogger("core.models")
                logger.error(f"❌ [TaskChainManager] SSE progress send failed: {e}")
    
    def send_complete(self, final_response: str, menu_data: Optional[Dict[str, Any]] = None, confirmation_data: Optional[Dict[str, Any]] = None) -> None:
        """Send completion notification via SSE."""
        self.logger.debug(f"🔍 [TaskChainManager] send_complete method called")
        self.logger.debug(f"🔍 [TaskChainManager] Menu data received: {menu_data is not None}")
        if menu_data:
            self.logger.debug(f"📊 [TaskChainManager] Menu data size: {len(str(menu_data))} characters")
        
        self.logger.debug(f"🔍 [TaskChainManager] sse_session_id: {self.sse_session_id}")
        
        if self.sse_session_id:
            try:
                # SSE送信者を取得して完了通知を送信
                from api.utils.sse_manager import get_sse_sender
                sse_sender = get_sse_sender()
                
                import asyncio
                loop = asyncio.get_event_loop()
                
                # デバッグログ: SSEマネージャーに渡すmenu_dataの値を確認
                self.logger.debug(f"🔍 [TaskChainManager] About to call SSE send_complete with menu_data: {menu_data is not None}")
                if menu_data:
                    self.logger.debug(f"📊 [TaskChainManager] Menu data content preview: {str(menu_data)[:200]}...")
                
                # デバッグログ: confirmation_dataの値を確認
                self.logger.debug(f"🔍 [TaskChainManager] About to call SSE send_complete with confirmation_data: {confirmation_data is not None}")
                if confirmation_data:
                    self.logger.debug(f"🔍 [TaskChainManager] Confirmation data: {confirmation_data}")
                
                # SSE送信を同期的に実行（イベントループの状態に関係なく）
                try:
                    # 現在のイベントループで同期的に実行
                    loop.run_until_complete(sse_sender.send_complete(
                        self.sse_session_id, 
                        final_response,
                        menu_data,
                        confirmation_data
                    ))
                    self.logger.info(f"✅ [TaskChainManager] SSE send_complete completed successfully")
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e) or "this event loop is already running" in str(e):
                        # イベントループが実行中の場合は、タスクとしてスケジュール
                        import asyncio
                        try:
                            # 現在のタスクとして実行
                            asyncio.create_task(sse_sender.send_complete(
                                self.sse_session_id, 
                                final_response,
                                menu_data,
                                confirmation_data
                            ))
                            self.logger.info(f"✅ [TaskChainManager] SSE send_complete scheduled as task")
                        except Exception as task_error:
                            self.logger.error(f"❌ [TaskChainManager] SSE send_complete task creation failed: {task_error}")
                    else:
                        self.logger.error(f"❌ [TaskChainManager] SSE send_complete runtime error: {e}")
                except Exception as e:
                    self.logger.error(f"❌ [TaskChainManager] SSE send_complete failed: {e}")
                
            except Exception as e:
                # SSE送信エラーはログに記録するが、処理は継続
                self.logger.error(f"❌ [TaskChainManager] SSE complete send failed: {e}")
    
    def send_error(self, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """Send error message via SSE."""
        if self.sse_session_id:
            try:
                # SSE送信者を取得してエラーを送信
                from api.utils.sse_manager import get_sse_sender
                sse_sender = get_sse_sender()
                
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 既にイベントループが実行中の場合は、タスクを作成
                    asyncio.create_task(sse_sender.send_error(
                        self.sse_session_id, 
                        error_message
                    ))
                else:
                    # イベントループが実行されていない場合は、同期的に実行
                    loop.run_until_complete(sse_sender.send_error(
                        self.sse_session_id, 
                        error_message
                    ))
                self.logger.error(f"❌ [TaskChainManager] Sent error to SSE: {error_message}")
            except Exception as e:
                # SSE送信エラーはログに記録するが、処理は継続
                self.logger.error(f"❌ [TaskChainManager] SSE error send failed: {e}")
    
    def update_task_status(self, task_id: str, status: TaskStatus, result: Any = None, error: str = None) -> None:
        """Update task status and result."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                task.result = result
                task.error = error
                if status == TaskStatus.COMPLETED:
                    self.results[task_id] = result
                break
