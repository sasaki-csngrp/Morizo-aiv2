"""
DynamicTaskBuilder: ユーザー反応に応じた動的タスク構築
"""
from typing import List, Dict, Any, Optional
from .models import Task, TaskStatus, TaskChainManager
from config.loggers import GenericLogger


class DynamicTaskBuilder:
    """動的タスク構築クラス"""
    
    def __init__(self, task_chain_manager: TaskChainManager):
        self.task_chain_manager = task_chain_manager
        self.context = {}  # コンテキスト管理
        self.logger = GenericLogger("core", "dynamic_task_builder")
    
    def set_context(self, key: str, value: Any) -> None:
        """コンテキストを設定"""
        self.context[key] = value
        self.logger.debug(f"📝 [DynamicTaskBuilder] Context set: {key} = {value}")
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """コンテキストを取得"""
        return self.context.get(key, default)
    
    def add_main_dish_proposal_task(
        self, 
        inventory_items: List[str], 
        user_id: str,
        main_ingredient: Optional[str] = None,
        menu_type: str = "",
        excluded_recipes: Optional[List[str]] = None,
        sse_session_id: Optional[str] = None
    ) -> Task:
        """主菜提案タスクを追加"""
        
        # 主要食材をコンテキストに保存
        if main_ingredient:
            self.set_context("main_ingredient", main_ingredient)
        
        task = Task(
            id=f"main_dish_proposal_{len(self.task_chain_manager.tasks)}",
            service="recipe_service",
            method="generate_proposals",
            parameters={
                "inventory_items": inventory_items,
                "user_id": user_id,
                "main_ingredient": main_ingredient,
                "menu_type": menu_type,
                "category": "main",
                "excluded_recipes": excluded_recipes or [],
                "sse_session_id": sse_session_id
            },
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        self.logger.debug(f"➕ [DynamicTaskBuilder] Added main dish proposal task: {task.id}")
        return task
    
    def add_inventory_task(self, user_id: str) -> Task:
        """在庫取得タスクを追加"""
        task = Task(
            id=f"inventory_get_{len(self.task_chain_manager.tasks)}",
            service="inventory_service",
            method="get_inventory",
            parameters={"user_id": user_id},
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        self.logger.debug(f"➕ [DynamicTaskBuilder] Added inventory task: {task.id}")
        return task
    
    def add_history_task(self, user_id: str, category: str = "main", days: int = 14) -> Task:
        """履歴取得タスクを追加"""
        task = Task(
            id=f"history_get_{len(self.task_chain_manager.tasks)}",
            service="history_service",
            method="history_get_recent_titles",
            parameters={
                "user_id": user_id,
                "category": category,
                "days": days
            },
            dependencies=[],
            status=TaskStatus.PENDING
        )
        
        self.logger.debug(f"➕ [DynamicTaskBuilder] Added history task: {task.id}")
        return task
