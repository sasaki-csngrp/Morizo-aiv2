#!/usr/bin/env python3
"""
StageComponent - 段階管理コンポーネント

段階的選択管理を担当
"""

from typing import Dict, Any, Optional, List
from config.loggers import GenericLogger
from .ingredient_mapper import IngredientMapperComponent


class StageComponent:
    """段階管理コンポーネント"""
    
    def __init__(self, ingredient_mapper: IngredientMapperComponent, logger: GenericLogger):
        """初期化
        
        Args:
            ingredient_mapper: 食材マッピングコンポーネント
            logger: ロガーインスタンス
        """
        self.ingredient_mapper = ingredient_mapper
        self.logger = logger
        
        # Phase 2.5D: 段階的選択管理
        self.current_stage: str = "main"  # "main", "sub", "soup", "completed"
        self.selected_main_dish: Optional[Dict[str, Any]] = None
        self.selected_sub_dish: Optional[Dict[str, Any]] = None
        self.selected_soup: Optional[Dict[str, Any]] = None
        self.used_ingredients: list = []
        self.menu_category: str = "japanese"  # "japanese", "western", "chinese"
    
    def get_current_stage(self) -> str:
        """現在の段階を取得
        
        Returns:
            str: 現在の段階（"main", "sub", "soup", "completed"）
        """
        return self.current_stage
    
    def _determine_menu_category(self, menu_type: str) -> str:
        """献立カテゴリを判定
        
        Args:
            menu_type: メニュータイプ文字列
            
        Returns:
            str: 献立カテゴリ（"japanese", "western", "chinese"）
        """
        if any(x in menu_type for x in ["洋食", "western", "西洋"]):
            return "western"
        elif any(x in menu_type for x in ["中華", "chinese"]):
            return "chinese"
        else:
            return "japanese"
    
    def set_selected_recipe(self, category: str, recipe: Dict[str, Any], inventory_items: List[str]) -> None:
        """選択したレシピを保存
        
        Args:
            category: カテゴリ（"main", "sub", "soup"）
            recipe: レシピ情報
            inventory_items: 在庫食材名リスト
        """
        if category == "main":
            self.selected_main_dish = recipe
            self.current_stage = "sub"
            # 使用済み食材を記録（在庫名にマッピング）
            self.used_ingredients = self.ingredient_mapper.record_used_ingredients(
                recipe, inventory_items, self.used_ingredients
            )
            # カテゴリ判定
            menu_type = recipe.get("menu_type", "")
            self.menu_category = self._determine_menu_category(menu_type)
        elif category == "sub":
            self.selected_sub_dish = recipe
            self.current_stage = "soup"
            # 使用済み食材を記録（在庫名にマッピング）
            self.used_ingredients = self.ingredient_mapper.record_used_ingredients(
                recipe, inventory_items, self.used_ingredients
            )
        elif category == "soup":
            self.selected_soup = recipe
            self.current_stage = "completed"
        
        # デバッグログ: 選択されたレシピのsourceを確認
        self.logger.debug(f"✅ [SESSION] Recipe selected for {category}: title='{recipe.get('title', 'N/A')}', source='{recipe.get('source', 'N/A')}'")
    
    def get_selected_recipes(self) -> Dict[str, Any]:
        """選択済みレシピを取得
        
        Returns:
            Dict[str, Any]: 選択済みレシピの辞書
        """
        return {
            "main": self.selected_main_dish,
            "sub": self.selected_sub_dish,
            "soup": self.selected_soup
        }
    
    def get_used_ingredients(self) -> list:
        """使用済み食材を取得
        
        Returns:
            list: 使用済み食材のリスト
        """
        return self.used_ingredients
    
    def get_menu_category(self) -> str:
        """献立カテゴリを取得
        
        Returns:
            str: 献立カテゴリ（"japanese", "western", "chinese"）
        """
        return self.menu_category

