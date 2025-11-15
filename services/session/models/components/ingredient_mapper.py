#!/usr/bin/env python3
"""
IngredientMapperComponent - 食材マッピングコンポーネント

食材名の正規化と在庫へのマッピングを担当
"""

from typing import Dict, Any, List
import re
from config.loggers import GenericLogger


class IngredientMapperComponent:
    """食材マッピングコンポーネント"""
    
    def __init__(self, logger: GenericLogger):
        """初期化
        
        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
    
    def normalize_ingredient_name(self, name: str) -> str:
        """食材名を正規化（比較用）
        
        Args:
            name: 食材名
            
        Returns:
            str: 正規化された食材名
        """
        # 全角・半角英数字を半角に統一
        normalized = name.translate(str.maketrans('０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'))
        # 全角カタカナをひらがなに変換（Unicode範囲を使用）
        def katakana_to_hiragana(text):
            result = []
            for char in text:
                if '\u30A1' <= char <= '\u30F6':  # カタカナ範囲
                    hiragana = chr(ord(char) - 0x60)
                    result.append(hiragana)
                else:
                    result.append(char)
            return ''.join(result)
        normalized = katakana_to_hiragana(normalized)
        # 空白と記号を除去
        normalized = re.sub(r'[\s　\-－\(\)（）・，、。．]+', '', normalized)
        # 小文字に統一
        normalized = normalized.lower()
        return normalized
    
    def map_recipe_ingredients_to_inventory(self, recipe_ingredients: List[str], inventory_items: List[str]) -> List[str]:
        """レシピの材料名を在庫名にマッピング
        
        Args:
            recipe_ingredients: レシピの材料名リスト（ベクトルDB由来）
            inventory_items: 在庫食材名リスト（ユーザーの在庫）
            
        Returns:
            List[str]: マッピングされた在庫名リスト
        """
        if not recipe_ingredients or not inventory_items:
            return []
        
        mapped = []
        
        # 在庫名を正規化してインデックスを作成
        inventory_normalized = {}
        for inv_name in inventory_items:
            normalized = self.normalize_ingredient_name(inv_name)
            if normalized not in inventory_normalized:
                inventory_normalized[normalized] = []
            inventory_normalized[normalized].append(inv_name)
        
        # レシピ材料を在庫名にマッピング
        for recipe_ingredient in recipe_ingredients:
            normalized_recipe = self.normalize_ingredient_name(recipe_ingredient)
            
            # 完全一致を優先
            matched = False
            if normalized_recipe in inventory_normalized:
                # 複数の在庫名が同じ正規化結果を持つ場合は最初のものを使用
                mapped.append(inventory_normalized[normalized_recipe][0])
                matched = True
            else:
                # 部分一致を試行（在庫名にレシピ材料が含まれる場合）
                for inv_name in inventory_items:
                    normalized_inv = self.normalize_ingredient_name(inv_name)
                    if normalized_recipe in normalized_inv or normalized_inv in normalized_recipe:
                        mapped.append(inv_name)
                        matched = True
                        break
            
            # マッチしない場合もログに記録（デバッグ用）
            if not matched:
                self.logger.debug(f"⚠️ [SESSION] Could not map recipe ingredient '{recipe_ingredient}' to inventory")
        
        # 重複除去
        mapped = list(dict.fromkeys(mapped))  # 順序を保持しつつ重複除去
        
        return mapped
    
    def record_used_ingredients(self, recipe: Dict[str, Any], inventory_items: List[str], used_ingredients: List[str]) -> List[str]:
        """使用済み食材を記録（在庫名にマッピング）
        
        Args:
            recipe: レシピ情報
            inventory_items: 在庫食材名リスト
            used_ingredients: 既存の使用済み食材リスト
            
        Returns:
            List[str]: 更新された使用済み食材リスト
        """
        if "ingredients" not in recipe:
            return used_ingredients
        
        recipe_ingredients = recipe["ingredients"]
        
        self.logger.debug(f"🔍 [SESSION] Mapping recipe ingredients: {recipe_ingredients}")
        self.logger.debug(f"🔍 [SESSION] Available inventory items: {inventory_items}")
        
        # レシピ材料を在庫名にマッピング
        mapped_ingredients = self.map_recipe_ingredients_to_inventory(
            recipe_ingredients, inventory_items
        )
        
        updated_ingredients = used_ingredients + mapped_ingredients
        self.logger.debug(f"📝 [SESSION] Mapped recipe ingredients to inventory: {recipe_ingredients} -> {mapped_ingredients}")
        
        return updated_ingredients

