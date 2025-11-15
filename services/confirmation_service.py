#!/usr/bin/env python3
"""
ConfirmationService - 確認プロセスサービス

曖昧性検出と確認プロセスのビジネスロジックを提供
タスクチェーン保持機能を実装
"""

from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from config.loggers import GenericLogger
from .tool_name_converter import ToolNameConverter
from .confirmation.models import AmbiguityInfo, AmbiguityResult, ConfirmationResult
from .confirmation.response_parser import UserResponseParser
from .confirmation.ambiguity_detector import AmbiguityDetector

if TYPE_CHECKING:
    from core.models import Task


class ConfirmationService:
    """確認プロセスサービス"""
    
    def __init__(self, tool_router=None):
        """初期化"""
        self.tool_router = tool_router
        self.logger = GenericLogger("service", "confirmation")
        self.response_parser = UserResponseParser()
        self.ambiguity_detector = AmbiguityDetector(tool_router)
    
    async def detect_ambiguity(
        self, 
        tasks: List[Any], 
        user_id: str,
        token: str = ""
    ) -> AmbiguityResult:
        """
        曖昧性検出
        
        Args:
            tasks: タスクリスト（Taskオブジェクト）
            user_id: ユーザーID
        
        Returns:
            曖昧性検出結果
        """
        return await self.ambiguity_detector.detect_ambiguity(tasks, user_id, token)
    
    async def process_confirmation(
        self, 
        ambiguity_info: AmbiguityInfo,
        user_response: str,
        context: Dict[str, Any],
        original_tasks: List['Task'] = None
    ) -> ConfirmationResult:
        """
        確認プロセス処理
        
        Args:
            ambiguity_info: 曖昧性情報
            user_response: ユーザー応答
            context: コンテキスト
            original_tasks: 元のタスクリスト
        
        Returns:
            確認プロセス結果
        """
        try:
            self.logger.debug(f"🔧 [ConfirmationService] Processing confirmation for task: {ambiguity_info.task_id}")
            
            # ユーザー応答の解析
            parsed_response = self.response_parser.parse_response(user_response)
            
            # タスクの更新 - 元のタスク情報を渡す
            updated_tasks = await self._update_tasks([ambiguity_info], parsed_response, original_tasks)
            
            result = ConfirmationResult(
                is_cancelled=parsed_response.get("is_cancelled", False),
                updated_tasks=updated_tasks,
                confirmation_context=context
            )
            
            self.logger.info(f"✅ [ConfirmationService] Confirmation processed successfully")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ [ConfirmationService] Error in process_confirmation: {e}")
            return ConfirmationResult(is_cancelled=True, updated_tasks=[], confirmation_context={})
    
    async def maintain_task_chain(
        self, 
        original_tasks: List[Any],
        confirmation_result: ConfirmationResult
    ) -> List['Task']:
        """
        タスクチェーン維持（文脈補完実装）
        
        Args:
            original_tasks: 元のタスクリスト
            confirmation_result: 確認プロセス結果
        
        Returns:
            更新されたタスクリスト（Taskオブジェクトのリスト）
        """
        try:
            self.logger.debug(f"🔧 [ConfirmationService] Maintaining task chain for {len(original_tasks)} tasks")
            
            if confirmation_result.is_cancelled:
                self.logger.info(f"⚠️ [ConfirmationService] Task chain cancelled by user")
                return []
            
            # 文脈補完：元のタスク情報とユーザーの回答を統合
            updated_tasks = []
            
            # 循環インポートを避けるため、関数内でインポート
            from core.models import Task
            
            # 確認結果から更新されたタスクを取得
            confirmation_tasks = confirmation_result.updated_tasks
            
            for i, confirmation_task in enumerate(confirmation_tasks):
                # 元のタスク情報を取得
                original_task = None
                if i < len(original_tasks):
                    original_task = original_tasks[i]
                
                # 文脈補完：元のタスクのパラメータを保持しつつ、戦略を更新
                if original_task:
                    # 元のパラメータをコピー
                    updated_parameters = original_task.parameters.copy()
                    
                    # 確認結果の戦略を適用
                    if hasattr(confirmation_task, 'parameters') and confirmation_task.parameters:
                        strategy = confirmation_task.parameters.get('strategy')
                        if strategy:
                            updated_parameters['strategy'] = strategy
                    
                    # 文脈補完されたタスクを作成
                    updated_task = Task(
                        id=confirmation_task.id,
                        service=confirmation_task.service,
                        method=confirmation_task.method,
                        parameters=updated_parameters,
                        dependencies=confirmation_task.dependencies
                    )
                else:
                    # 元のタスクがない場合は確認結果をそのまま使用
                    updated_task = confirmation_task
                
                updated_tasks.append(updated_task)
            
            self.logger.debug(f"✅ [ConfirmationService] Task chain maintained successfully: {len(updated_tasks)} tasks")
            
            return updated_tasks
            
        except Exception as e:
            self.logger.error(f"❌ [ConfirmationService] Error in maintain_task_chain: {e}")
            return original_tasks
    
    async def _update_tasks(
        self, 
        ambiguous_tasks: List[AmbiguityInfo], 
        parsed_response: Dict[str, Any],
        original_tasks: List['Task'] = None
    ) -> List['Task']:
        """
        タスクの更新
        
        Args:
            ambiguous_tasks: 曖昧なタスクリスト
            parsed_response: 解析された応答
            original_tasks: 元のタスクリスト
        
        Returns:
            更新されたタスクリスト（Taskオブジェクトのリスト）
        """
        try:
            self.logger.info(f"🔧 [ConfirmationService] Updating tasks")
            
            # 循環インポートを避けるため、関数内でインポート
            from core.models import Task
            
            updated_tasks = []
            strategy = parsed_response.get("strategy", "by_id")
            
            for task_info in ambiguous_tasks:
                # 戦略に応じてツール名を変更
                original_tool = task_info.tool_name
                if strategy == "by_name_latest":
                    new_tool = original_tool.replace("_by_name", "_by_name_latest")
                elif strategy == "by_name_oldest":
                    new_tool = original_tool.replace("_by_name", "_by_name_oldest")
                elif strategy == "by_name_all":
                    new_tool = original_tool.replace("_by_name", "_by_name_all")
                elif strategy == "by_id":
                    new_tool = original_tool.replace("_by_name", "_by_id")
                else:
                    new_tool = original_tool
                
                # 元のタスクからパラメータを取得
                original_task = None
                if original_tasks:
                    for task in original_tasks:
                        if task.id == task_info.task_id:
                            original_task = task
                            break
                
                # 戦略を反映したパラメータを作成
                if original_task:
                    updated_parameters = original_task.parameters.copy()
                    updated_parameters["strategy"] = strategy
                else:
                    updated_parameters = task_info.original_parameters.copy()
                    updated_parameters["strategy"] = strategy
                
                # Taskオブジェクトを作成
                updated_task = Task(
                    id=task_info.task_id,
                    service=ToolNameConverter.get_service_from_tool(new_tool),
                    method=ToolNameConverter.get_method_from_tool(new_tool),
                    parameters=updated_parameters,
                    dependencies=[]
                )
                updated_tasks.append(updated_task)
            
            self.logger.debug(f"✅ [ConfirmationService] Tasks updated successfully: {len(updated_tasks)} tasks")
            
            return updated_tasks
            
        except Exception as e:
            self.logger.error(f"❌ [ConfirmationService] Error in _update_tasks: {e}")
            return []
