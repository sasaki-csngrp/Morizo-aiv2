"""
StageManager: Manages stage progression (main/sub/soup).

This handler manages:
- Current stage retrieval
- Stage advancement
- Recipe selection from tasks
- Next stage request generation
- Selected recipe retrieval
"""

from typing import Optional, Dict, Any
from services.session_service import SessionService
from config.loggers import GenericLogger


class StageManager:
    """Manages stage progression (main/sub/soup)."""
    
    def __init__(self, session_service: SessionService):
        self.logger = GenericLogger("core", "stage_manager")
        self.session_service = session_service
    
    async def get_current_stage(self, sse_session_id: str, user_id: str) -> str:
        """現在の段階を取得
        
        Args:
            sse_session_id: SSEセッションID
            user_id: ユーザーID
        
        Returns:
            str: 現在の段階（"main", "sub", "soup", "completed"）
        """
        try:
            session = await self.session_service.get_session(sse_session_id, user_id)
            if not session:
                self.logger.warning(f"⚠️ [STAGE] Session not found, returning default stage 'main'")
                return "main"
            
            stage = session.get_current_stage()
            self.logger.debug(f"✅ [STAGE] Current stage: {stage}")
            return stage
            
        except Exception as e:
            self.logger.error(f"❌ [STAGE] 現在の段階の取得に失敗しました: {e}")
            return "main"
    
    async def get_selected_recipe_from_task(self, task_id: str, selection: int, sse_session_id: str) -> Dict[str, Any]:
        """選択されたレシピをタスクから取得
        
        Args:
            task_id: タスクID
            selection: 選択されたインデックス
            sse_session_id: SSEセッションID
        
        Returns:
            Dict[str, Any]: 選択されたレシピ情報
        """
        try:
            self.logger.debug(f"🔍 [STAGE] Getting selected recipe: task_id={task_id}, selection={selection}")
            
            # セッションから候補情報を取得
            session = await self.session_service.get_session(sse_session_id, user_id=None)
            if not session:
                self.logger.error(f"❌ [STAGE] セッションが見つかりませんでした: {sse_session_id}")
                return {}
            
            # 現在の段階を取得
            current_stage = session.get_current_stage()
            category = current_stage  # "main", "sub", "soup", "other"
            
            # セッションから候補情報を取得
            candidates = session.get_candidates(category)
            if not candidates or len(candidates) < selection:
                self.logger.error(f"❌ [STAGE] 無効な選択です: {selection} (候補数: {len(candidates)})")
                return {}
            
            # 選択されたレシピを取得
            selected_recipe = candidates[selection - 1]  # インデックスは1ベース
            ingredients = selected_recipe.get('ingredients', [])
            has_ingredients = 'ingredients' in selected_recipe and ingredients
            self.logger.debug(f"✅ [STAGE] Selected recipe: title='{selected_recipe.get('title', 'Unknown')}', source='{selected_recipe.get('source', 'N/A')}'")
            if has_ingredients:
                self.logger.debug(f"✅ [STAGE] Selected recipe has {len(ingredients)} ingredients: {ingredients}")
            else:
                self.logger.warning(f"⚠️ [STAGE] Selected recipe missing or empty 'ingredients' field (ingredients={ingredients})")
            
            return selected_recipe
            
        except Exception as e:
            self.logger.error(f"❌ [STAGE] 選択されたレシピの取得に失敗しました: {e}")
            return {}
    
    async def advance_stage(self, sse_session_id: str, user_id: str, selected_recipe: Dict[str, Any]) -> str:
        """段階を進める
        
        Args:
            sse_session_id: SSEセッションID
            user_id: ユーザーID
            selected_recipe: 選択されたレシピ情報
        
        Returns:
            str: 次の段階の名前
        """
        try:
            # セッションを取得
            session = await self.session_service.get_session(sse_session_id, user_id)
            if not session:
                self.logger.error(f"❌ [STAGE] セッションが見つかりませんでした")
                return "main"
            
            # 現在の段階を取得
            current_stage = session.get_current_stage()
            self.logger.debug(f"🔍 [STAGE] Current stage: {current_stage}")
            
            # 段階に応じて処理
            # 注意: Session.set_selected_recipe()は2つの引数（category, recipe）のみを受け取る
            # inventory_itemsはセッションコンテキストから自動的に取得される
            if current_stage == "main":
                # 主菜を選択した場合、副菜段階に進む
                session.set_selected_recipe("main", selected_recipe)
                next_stage = "sub"
                self.logger.debug(f"✅ [STAGE] Advanced to stage: sub")
                
            elif current_stage == "sub":
                # 副菜を選択した場合、汁物段階に進む
                session.set_selected_recipe("sub", selected_recipe)
                next_stage = "soup"
                self.logger.debug(f"✅ [STAGE] Advanced to stage: soup")
                
            elif current_stage == "soup":
                # 汁物を選択した場合、完了
                session.set_selected_recipe("soup", selected_recipe)
                next_stage = "completed"
                self.logger.info(f"✅ [STAGE] すべての段階が完了しました")
                
            elif current_stage == "other":
                # otherカテゴリを選択した場合、完了（単体動作のため）
                session.set_selected_recipe("other", selected_recipe)
                next_stage = "completed"
                self.logger.info(f"✅ [STAGE] その他カテゴリの選択が完了しました")
                
            else:
                self.logger.warning(f"⚠️ [STAGE] Unexpected stage: {current_stage}")
                next_stage = current_stage
            
            return next_stage
            
        except Exception as e:
            self.logger.error(f"❌ [STAGE] 段階の進行に失敗しました: {e}")
            return "main"
    
    async def generate_sub_dish_request(
        self, main_dish: Dict, sse_session_id: str, user_id: str
    ) -> str:
        """
        副菜提案用のリクエストを生成
        
        例: "副菜を5件提案して"（主菜で使った食材を除外）
        """
        session = await self.session_service.get_session(sse_session_id, user_id)
        if not session:
            return "副菜を5件提案して"
        
        used_ingredients = session.get_used_ingredients()
        main_ingredient_text = f"（主菜で使った食材: {', '.join(used_ingredients)} は除外して）"
        
        return f"主菜で使っていない食材で副菜を5件提案して。{main_ingredient_text}"
    
    async def generate_soup_request(
        self, sub_dish: Dict, sse_session_id: str, user_id: str
    ) -> str:
        """
        汁物提案用のリクエストを生成
        
        例: "汁物を5件提案して"（和食なら味噌汁、洋食ならスープ）
        """
        session = await self.session_service.get_session(sse_session_id, user_id)
        if not session:
            return "汁物を5件提案して"
        
        used_ingredients = session.get_used_ingredients()
        menu_category = session.get_menu_category()
        
        soup_type = "味噌汁" if menu_category == "japanese" else "スープ"
        used_ingredients_text = f"（主菜・副菜で使った食材: {', '.join(used_ingredients)} は除外して）"
        
        return f"{soup_type}を5件提案して。{used_ingredients_text}"
    
    async def get_selected_sub_dish(self, sse_session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """選択済み副菜を取得"""
        try:
            session = await self.session_service.get_session(sse_session_id, user_id)
            if session:
                return session.selected_sub_dish
            return None
        except Exception as e:
            self.logger.error(f"❌ [STAGE] 選択された副菜の取得に失敗しました: {e}")
            return None
    
    async def get_selected_soup(self, sse_session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """選択済み汁物を取得"""
        try:
            session = await self.session_service.get_session(sse_session_id, user_id)
            if session:
                return session.selected_soup
            return None
        except Exception as e:
            self.logger.error(f"❌ [STAGE] 選択された汁物の取得に失敗しました: {e}")
            return None
    
    async def get_selected_recipes(self, sse_session_id: str) -> Dict[str, Any]:
        """選択済みレシピを取得（親セッションからも集約）
        
        Args:
            sse_session_id: SSEセッションID
        
        Returns:
            Dict[str, Any]: 選択済みレシピの辞書（親セッションからも集約）
        """
        # SessionService経由で取得（内部でservices/session/stage_manager.pyのStageManagerを使用）
        return await self.session_service.get_selected_recipes(sse_session_id)

