"""
ContextManager: セッション内コンテキスト管理
"""
from typing import Dict, List, Any, Optional
from config.loggers import GenericLogger


class ContextManager:
    """コンテキスト管理クラス"""
    
    def __init__(self, sse_session_id: str):
        self.sse_session_id = sse_session_id
        self.context = {}
        self.logger = GenericLogger("core", "context_manager")
        
        # ユーザー選択用の一時停止コンテキスト
        self.paused_contexts: Dict[str, Dict[str, Any]] = {}
        self.context_ttl = 3600  # 1時間でタイムアウト
    
    def set_main_ingredient(self, ingredient: str) -> None:
        """主要食材を設定"""
        self.context["main_ingredient"] = ingredient
        self.logger.debug(f"🥬 [ContextManager] Main ingredient set: {ingredient}")
    
    def get_main_ingredient(self) -> Optional[str]:
        """主要食材を取得"""
        return self.context.get("main_ingredient")
    
    def set_inventory_items(self, items: List[str]) -> None:
        """在庫食材を設定"""
        self.context["inventory_items"] = items
        self.logger.debug(f"📦 [ContextManager] Inventory items set: {len(items)} items")
    
    def get_inventory_items(self) -> List[str]:
        """在庫食材を取得"""
        return self.context.get("inventory_items", [])
    
    def set_excluded_recipes(self, recipes: List[str]) -> None:
        """除外レシピを設定"""
        self.context["excluded_recipes"] = recipes
        self.logger.debug(f"🚫 [ContextManager] Excluded recipes set: {len(recipes)} recipes")
    
    def get_excluded_recipes(self) -> List[str]:
        """除外レシピを取得"""
        return self.context.get("excluded_recipes", [])
    
    def clear_context(self) -> None:
        """コンテキストをクリア"""
        self.context.clear()
        self.logger.info("🧹 [ContextManager] コンテキストをクリアしました")
    
    def get_context(self) -> Dict[str, Any]:
        """全コンテキストを取得"""
        return self.context.copy()
    
    def save_context_for_resume(self, task_id: str, context: dict) -> dict:
        """
        再開用にコンテキストを保存
        
        Args:
            task_id (str): タスクID
            context (dict): 保存するコンテキスト
            
        Returns:
            dict: 成功フラグとエラー情報
        """
        try:
            import time
            import copy
            
            # タイムスタンプを追加
            context['paused_at'] = time.time()
            
            # コンテキストを保存（深いコピーを作成）
            self.paused_contexts[task_id] = copy.deepcopy(context)
            
            self.logger.info(f"💾 [ContextManager] Context saved for task {task_id}")
            self.logger.debug(f"💾 [ContextManager] Saved context keys: {list(context.keys())}")
            
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"❌ [ContextManager] タスク {task_id} のコンテキスト保存に失敗しました: {e}")
            return {"success": False, "error": str(e)}
    
    def load_context_for_resume(self, task_id: str) -> Optional[dict]:
        """
        再開用のコンテキストを読み込み
        
        Args:
            task_id (str): タスクID
            
        Returns:
            Optional[dict]: 保存されたコンテキスト（存在しない場合やタイムアウトの場合はNone）
        """
        try:
            import time
            
            # コンテキストが存在するかチェック
            if task_id not in self.paused_contexts:
                self.logger.warning(f"⚠️ [ContextManager] No context found for task {task_id}")
                return None
            
            # コンテキストを取得（popで削除しながら取得）
            context = self.paused_contexts.pop(task_id)
            
            # タイムアウトチェック
            paused_at = context.get('paused_at', 0)
            elapsed_time = time.time() - paused_at
            
            if elapsed_time > self.context_ttl:
                self.logger.warning(
                    f"⚠️ [ContextManager] Context for task {task_id} has expired "
                    f"(elapsed: {elapsed_time:.0f}s, TTL: {self.context_ttl}s)"
                )
                return None
            
            self.logger.info(f"📂 [ContextManager] Context loaded for task {task_id}")
            self.logger.debug(f"📂 [ContextManager] Loaded context keys: {list(context.keys())}")
            
            return context
            
        except Exception as e:
            self.logger.error(f"❌ [ContextManager] タスク {task_id} のコンテキスト読み込みに失敗しました: {e}")
            return None
