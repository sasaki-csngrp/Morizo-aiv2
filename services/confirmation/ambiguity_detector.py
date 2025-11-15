#!/usr/bin/env python3
"""
AmbiguityDetector - 曖昧性検出

在庫やその他のリソースで曖昧性があるかをチェックするロジックを提供
ConfirmationServiceから分離された責任
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from config.loggers import GenericLogger
from .models import AmbiguityInfo, AmbiguityResult

if TYPE_CHECKING:
    from core.models import Task


class AmbiguityDetector:
    """曖昧性検出クラス"""
    
    def __init__(self, tool_router=None):
        """初期化"""
        self.tool_router = tool_router
        self.logger = GenericLogger("service", "ambiguity_detector")
    
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
        try:
            self.logger.debug(f"🔧 [AmbiguityDetector] Detecting ambiguity for user: {user_id}")
            
            ambiguous_tasks = []
            
            # 各タスクの曖昧性チェック
            for task in tasks:
                # Taskオブジェクトの場合のみ処理
                if hasattr(task, 'service') and hasattr(task, 'method'):
                    tool_name = f"{task.service}_{task.method}"
                    
                    if tool_name.startswith("inventory_"):
                        # 在庫操作の曖昧性チェック
                        ambiguity_info = await self.check_inventory_ambiguity(task, user_id, token)
                        if ambiguity_info and ambiguity_info.is_ambiguous:
                            ambiguous_tasks.append(ambiguity_info)
                    
                    if tool_name.startswith("recipe_service_generate_proposals"):
                        # 主菜提案の曖昧性チェック
                        ambiguity_info = await self.check_main_dish_ambiguity(task, user_id, token)
                        if ambiguity_info and ambiguity_info.is_ambiguous:
                            ambiguous_tasks.append(ambiguity_info)
            
            requires_confirmation = len(ambiguous_tasks) > 0
            
            result = AmbiguityResult(
                requires_confirmation=requires_confirmation,
                ambiguous_tasks=ambiguous_tasks
            )
            
            self.logger.debug(f"✅ [AmbiguityDetector] Ambiguity detection completed: {len(ambiguous_tasks)} ambiguous tasks")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ [AmbiguityDetector] Error in detect_ambiguity: {e}")
            return AmbiguityResult(requires_confirmation=False, ambiguous_tasks=[])
    
    async def check_inventory_ambiguity(
        self, 
        task: Any, 
        user_id: str,
        token: str = ""
    ) -> Optional[AmbiguityInfo]:
        """
        在庫操作の曖昧性チェック（MCPツール経由）
        
        Args:
            task: タスク（Taskオブジェクト）
            user_id: ユーザーID
        
        Returns:
            曖昧性情報（曖昧でない場合はNone）
        """
        try:
            # Taskオブジェクトの場合のみ処理
            if hasattr(task, 'service') and hasattr(task, 'method'):
                tool_name = f"{task.service}_{task.method}"
                parameters = task.parameters.copy()  # コピーを作成
                
                # 【重要】user_idパラメータを確実に含める
                if "user_id" not in parameters:
                    parameters["user_id"] = user_id
                task_id = task.id
                
                # 在庫更新・削除で名前指定の場合の曖昧性チェック
                if task.service == "inventory_service" and task.method in ["update_inventory", "delete_inventory"]:
                    item_name = parameters.get("item_identifier", "")
                    strategy = parameters.get("strategy", "")
                    
                    # by_name戦略（曖昧性あり）の場合のみ曖昧性チェック
                    if item_name and strategy == "by_name" and self.tool_router:
                        # MCPツール経由でデータを取得
                        result = await self.tool_router.route_tool(
                            "inventory_list_by_name",
                            {"item_name": item_name, "user_id": user_id},
                            token
                        )
                        
                        # Service層で曖昧性を判定
                        self.logger.debug(f"🔍 [AmbiguityDetector] Checking ambiguity for {item_name}: result={result}")
                        if result.get("success") and len(result.get("result", {}).get("data", [])) > 1:
                            items = result.get("result", {}).get("data", [])
                            self.logger.info(f"⚠️ [AmbiguityDetector] Ambiguity detected: {len(items)} items found")
                            return AmbiguityInfo(
                                task_id=task_id,
                                tool_name=tool_name,
                                ambiguity_type="multiple_items",
                                details={
                                    "item_name": item_name,
                                    "items": items,
                                    "count": len(items),
                                    "message": self._generate_confirmation_message(item_name, items)
                                },
                                original_parameters=parameters  # user_idを含むパラメータ
                            )
                        else:
                            self.logger.debug(f"✅ [AmbiguityDetector] No ambiguity: success={result.get('success')}, data_count={len(result.get('result', {}).get('data', []))}")
                    elif item_name and strategy not in ["by_name"]:
                        # 明確な戦略の場合は曖昧性チェックをスキップ
                        self.logger.info(f"✅ [AmbiguityDetector] Skipping ambiguity check for strategy: {strategy}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ [AmbiguityDetector] Error in check_inventory_ambiguity: {e}")
            return None
    
    async def check_main_dish_ambiguity(
        self, 
        task: Any, 
        user_id: str,
        token: str = ""
    ) -> Optional[AmbiguityInfo]:
        """主菜提案の曖昧性チェック（主要食材未指定時）"""
        
        if task.method == "generate_proposals" and task.parameters.get("category") == "main":
            # 主要食材が指定されていない場合
            main_ingredient = task.parameters.get("main_ingredient")
            if not main_ingredient:
                return AmbiguityInfo(
                    task_id=task.id,
                    tool_name=f"{task.service}_{task.method}",
                    ambiguity_type="main_ingredient_optional_selection",
                    details={
                        "message": "なにか主な食材を指定しますか？それとも今の在庫から作れる主菜を提案しましょうか？",
                        "type": "main_ingredient_optional_selection",
                        "options": [
                            {"value": "specify", "label": "食材を指定する"},
                            {"value": "proceed", "label": "指定せずに提案してもらう"}
                        ],
                        "task_type": "main_dish_proposal"
                    },
                    original_parameters=task.parameters
                )
        
        return None
    
    def _generate_confirmation_message(self, item_name: str, items: List[Dict[str, Any]]) -> str:
        """確認メッセージを生成"""
        message = f"「{item_name}」が{len(items)}件見つかりました。\n\n"
        
        for i, item in enumerate(items, 1):
            message += f"アイテム{i}:\n"
            message += f"  数量: {item['quantity']} {item['unit']}\n"
            message += f"  保存場所: {item['storage_location']}\n"
            if item.get('expiry_date'):
                message += f"  期限: {item['expiry_date']}\n"
            message += f"  追加日: {item['created_at']}\n\n"
        
        message += "以下のいずれかを選択してください：\n"
        message += "- 「最新の」または「新しい」: 最も最近追加されたもの\n"
        message += "- 「古い」または「古いの」: 最も古いもの\n"
        message += "- 「全部」または「すべて」: 全てのアイテム\n"
        message += "- 「キャンセル」: 操作を中止"
        
        return message
