#!/usr/bin/env python3
"""
Session Base - セッション基本クラス

セッションデータモデルの基本クラス
コンポーネントを統合してSessionクラスを構成
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from config.loggers import GenericLogger

from .components.confirmation import ConfirmationComponent
from .components.proposal import ProposalComponent
from .components.candidate import CandidateComponent
from .components.context import ContextComponent
from .components.stage import StageComponent
from .components.ingredient_mapper import IngredientMapperComponent


class Session:
    """セッションクラス"""
    
    def __init__(self, session_id: str, user_id: str):
        """初期化"""
        # 基本情報の初期化
        self.id = session_id
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.data: Dict[str, Any] = {}
        
        # ロガー設定
        self.logger = GenericLogger("service", "session")
        
        # コンポーネントの初期化
        self._ingredient_mapper = IngredientMapperComponent(self.logger)
        self.confirmation = ConfirmationComponent(self.logger)
        self.proposal = ProposalComponent(self.logger)
        self.candidate = CandidateComponent(self.logger)
        self.context = ContextComponent(self.logger)
        self.stage = StageComponent(self._ingredient_mapper, self.logger)
    
    # ============================================================================
    # 確認管理メソッド（ConfirmationComponentへの委譲）
    # ============================================================================
    
    def is_waiting_for_confirmation(self) -> bool:
        """確認待ち状態かどうか"""
        return self.confirmation.is_waiting()
    
    def set_ambiguity_confirmation(
        self, 
        original_request: str, 
        question: str,
        ambiguity_details: Dict[str, Any]
    ):
        """曖昧性解消の確認状態を設定"""
        self.confirmation.set_ambiguity_confirmation(original_request, question, ambiguity_details)
    
    def clear_confirmation_context(self):
        """確認コンテキストをクリア"""
        self.confirmation.clear()
    
    def get_confirmation_type(self) -> Optional[str]:
        """確認タイプを取得"""
        return self.confirmation.get_type()
    
    # ============================================================================
    # 提案レシピ管理メソッド（ProposalComponentへの委譲）
    # ============================================================================
    
    def add_proposed_recipes(self, category: str, titles: list) -> None:
        """提案済みレシピタイトルを追加"""
        self.proposal.add(category, titles)
    
    def get_proposed_recipes(self, category: str) -> list:
        """提案済みレシピタイトルを取得"""
        return self.proposal.get(category)
    
    def clear_proposed_recipes(self, category: str) -> None:
        """提案済みレシピをクリア"""
        self.proposal.clear(category)
    
    # ============================================================================
    # 候補管理メソッド（CandidateComponentへの委譲）
    # ============================================================================
    
    def set_candidates(self, category: str, candidates: list) -> None:
        """候補情報を保存（Phase 3C-3）"""
        self.candidate.set(category, candidates)
    
    def get_candidates(self, category: str) -> list:
        """候補情報を取得"""
        return self.candidate.get(category)
    
    # ============================================================================
    # コンテキスト管理メソッド（ContextComponentへの委譲）
    # ============================================================================
    
    def set_context(self, key: str, value: Any) -> None:
        """セッションコンテキストを設定"""
        self.context.set(key, value)
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """セッションコンテキストを取得"""
        return self.context.get(key, default)
    
    # ============================================================================
    # 段階管理メソッド（StageComponentへの委譲）
    # ============================================================================
    
    def get_current_stage(self) -> str:
        """現在の段階を取得"""
        return self.stage.get_current_stage()
    
    def set_current_stage(self, stage: str) -> None:
        """現在の段階を設定"""
        self.stage.set_current_stage(stage)
    
    def set_selected_recipe(self, category: str, recipe: Dict[str, Any]) -> None:
        """選択したレシピを保存"""
        inventory_items = self.context.get("inventory_items", [])
        self.stage.set_selected_recipe(category, recipe, inventory_items)
    
    def get_selected_recipes(self) -> Dict[str, Any]:
        """選択済みレシピを取得"""
        return self.stage.get_selected_recipes()
    
    def get_used_ingredients(self) -> list:
        """使用済み食材を取得"""
        return self.stage.get_used_ingredients()
    
    def get_menu_category(self) -> str:
        """献立カテゴリを取得"""
        return self.stage.get_menu_category()
    
    # ============================================================================
    # 後方互換性のためのメソッド（プライベートメソッドへのアクセス）
    # ============================================================================
    
    def _normalize_ingredient_name(self, name: str) -> str:
        """食材名を正規化（比較用）- 後方互換性のための委譲メソッド
        
        Args:
            name: 食材名
            
        Returns:
            str: 正規化された食材名
        """
        return self._ingredient_mapper.normalize_ingredient_name(name)
    
    def _map_recipe_ingredients_to_inventory(self, recipe_ingredients: List[str], inventory_items: List[str]) -> List[str]:
        """レシピの材料名を在庫名にマッピング - 後方互換性のための委譲メソッド
        
        Args:
            recipe_ingredients: レシピの材料名リスト（ベクトルDB由来）
            inventory_items: 在庫食材名リスト（ユーザーの在庫）
            
        Returns:
            List[str]: マッピングされた在庫名リスト
        """
        return self._ingredient_mapper.map_recipe_ingredients_to_inventory(recipe_ingredients, inventory_items)
    
    def _record_used_ingredients(self, recipe: Dict[str, Any]) -> None:
        """使用済み食材を記録（在庫名にマッピング）- 後方互換性のための委譲メソッド
        
        Args:
            recipe: レシピ情報
        """
        inventory_items = self.context.get("inventory_items", [])
        self.stage.used_ingredients = self._ingredient_mapper.record_used_ingredients(
            recipe, inventory_items, self.stage.used_ingredients
        )
    
    # ============================================================================
    # 後方互換性のためのプロパティ（属性アクセス）
    # ============================================================================
    
    @property
    def confirmation_context(self) -> Dict[str, Any]:
        """確認コンテキスト（後方互換性）"""
        return self.confirmation.confirmation_context
    
    @confirmation_context.setter
    def confirmation_context(self, value: Dict[str, Any]):
        """確認コンテキストの設定（後方互換性）"""
        self.confirmation.confirmation_context = value
    
    @property
    def proposed_recipes(self) -> Dict[str, list]:
        """提案レシピ（後方互換性）"""
        return self.proposal.proposed_recipes
    
    @property
    def candidates(self) -> Dict[str, list]:
        """候補（後方互換性）"""
        return self.candidate.candidates
    
    @property
    def current_stage(self) -> str:
        """現在の段階（後方互換性）"""
        return self.stage.current_stage
    
    @current_stage.setter
    def current_stage(self, value: str):
        """現在の段階の設定（後方互換性）"""
        self.stage.current_stage = value
    
    @property
    def selected_main_dish(self) -> Optional[Dict[str, Any]]:
        """選択された主菜（後方互換性）"""
        return self.stage.selected_main_dish
    
    @selected_main_dish.setter
    def selected_main_dish(self, value: Optional[Dict[str, Any]]):
        """選択された主菜の設定（後方互換性）"""
        self.stage.selected_main_dish = value
    
    @property
    def selected_sub_dish(self) -> Optional[Dict[str, Any]]:
        """選択された副菜（後方互換性）"""
        return self.stage.selected_sub_dish
    
    @selected_sub_dish.setter
    def selected_sub_dish(self, value: Optional[Dict[str, Any]]):
        """選択された副菜の設定（後方互換性）"""
        self.stage.selected_sub_dish = value
    
    @property
    def selected_soup(self) -> Optional[Dict[str, Any]]:
        """選択された汁物（後方互換性）"""
        return self.stage.selected_soup
    
    @selected_soup.setter
    def selected_soup(self, value: Optional[Dict[str, Any]]):
        """選択された汁物の設定（後方互換性）"""
        self.stage.selected_soup = value
    
    @property
    def used_ingredients(self) -> list:
        """使用済み食材（後方互換性）"""
        return self.stage.used_ingredients
    
    @used_ingredients.setter
    def used_ingredients(self, value: list):
        """使用済み食材の設定（後方互換性）"""
        self.stage.used_ingredients = value
    
    @property
    def menu_category(self) -> str:
        """献立カテゴリ（後方互換性）"""
        return self.stage.menu_category
    
    @menu_category.setter
    def menu_category(self, value: str):
        """献立カテゴリの設定（後方互換性）"""
        self.stage.menu_category = value

