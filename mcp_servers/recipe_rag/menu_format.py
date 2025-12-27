#!/usr/bin/env python3
"""
献立変換機能

RAG検索結果を献立形式（主菜・副菜・汁物）に変換する機能を提供
"""

from typing import List, Dict, Any
from config.loggers import GenericLogger

logger = GenericLogger("mcp", "recipe_rag", initialize_logging=False)


class MenuFormatter:
    """献立フォーマッター"""
    
    def __init__(self, llm_solver):
        """初期化"""
        self.llm_solver = llm_solver
    
    async def convert_rag_results_to_menu_format(
        self,
        rag_results: List[Dict[str, Any]],
        inventory_items: List[str],
        menu_type: str
    ) -> Dict[str, Any]:
        """
        RAG検索結果を献立形式（主菜・副菜・汁物）に変換
        
        Args:
            rag_results: RAG検索結果のリスト
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
        
        Returns:
            献立形式の辞書
        """
        try:
            logger.info(f"🔄 [RAG] 結果を献立形式に変換中")
            logger.debug(f"📊 [RAG] 結果数: {len(rag_results)}")
            logger.debug(f"📊 [RAG] RAG結果: {rag_results}")
            logger.debug(f"📊 [RAG] 在庫食材: {inventory_items}")
            logger.debug(f"📊 [RAG] 献立タイプ: {menu_type}")
            
            # レシピをカテゴリ別に分類
            categorized_recipes = self._categorize_recipes(rag_results)
            
            # 各カテゴリから最適なレシピを選択して献立を構成
            selected_menu = {
                "main_dish": {"title": "", "ingredients": []},
                "side_dish": {"title": "", "ingredients": []},
                "soup": {"title": "", "ingredients": []}
            }
            
            used_ingredients = set()
            
            # 各カテゴリから最適なレシピを選択
            for category in ["main_dish", "side_dish", "soup"]:
                recipes = categorized_recipes.get(category, [])
                
                if recipes:
                    # 食材重複を避けながら最適なレシピを選択
                    best_recipe = self._select_best_recipe(
                        recipes, used_ingredients, inventory_items
                    )
                    
                    if best_recipe:
                        title = best_recipe.get("title", "")
                        recipe_ingredients = self._extract_recipe_ingredients(best_recipe)
                        
                        selected_menu[category] = {
                            "title": title,
                            "ingredients": recipe_ingredients
                        }
                        
                        # 使用済み食材を記録
                        used_ingredients.update(recipe_ingredients)
            
            # 候補も生成（複数提案用）
            candidates = self._generate_menu_candidates(categorized_recipes)
            
            # LLMによる制約解決で最適な献立を選択
            if candidates and len(candidates) >= 1:
                llm_selected_menu = await self.llm_solver.solve_menu_constraints_with_llm(
                    candidates, inventory_items, menu_type
                )
                # LLMが有効な結果を返した場合はそれを使用
                if llm_selected_menu and any(llm_selected_menu.get(field, {}).get("title") for field in ["main_dish", "side_dish", "soup"]):
                    selected_menu = llm_selected_menu
            
            result = {
                "candidates": candidates,
                "selected": selected_menu
            }
            
            logger.debug(f"📊 [RAG] 選択された献立: {selected_menu}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [RAG] 献立形式変換エラー: {e}")
            logger.error(f"❌ [RAG] RAG結果: {rag_results}")
            logger.error(f"❌ [RAG] 在庫食材: {inventory_items}")
            logger.error(f"❌ [RAG] 献立タイプ: {menu_type}")
            raise
    
    def _categorize_recipes(self, rag_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        レシピをカテゴリ別に分類
        
        Args:
            rag_results: RAG検索結果
        
        Returns:
            カテゴリ別に分類されたレシピ辞書
        """
        categorized = {
            "main_dish": [],
            "side_dish": [],
            "soup": [],
            "other": []
        }
        
        for i, recipe in enumerate(rag_results):
            category = recipe.get("category", "").lower()
            title = recipe.get("title", "").lower()
            
            # カテゴリベースの分類
            if "主菜" in category or "メイン" in category:
                categorized["main_dish"].append(recipe)
            elif "副菜" in category or "サイド" in category:
                categorized["side_dish"].append(recipe)
            elif "汁物" in category or "スープ" in category or "味噌汁" in category:
                categorized["soup"].append(recipe)
            else:
                # タイトルベースの分類（フォールバック）
                if any(keyword in title for keyword in ["スープ", "味噌汁", "汁"]):
                    categorized["soup"].append(recipe)
                elif any(keyword in title for keyword in ["サラダ", "和え物", "漬物", "副菜"]):
                    categorized["side_dish"].append(recipe)
                else:
                    categorized["main_dish"].append(recipe)
        
        return categorized
    
    def _select_best_recipe(
        self, 
        recipes: List[Dict[str, Any]], 
        used_ingredients: set, 
        inventory_items: List[str]
    ) -> Dict[str, Any]:
        """
        最適なレシピを選択
        
        Args:
            recipes: レシピリスト
            used_ingredients: 使用済み食材セット
            inventory_items: 在庫食材リスト
        
        Returns:
            最適なレシピ
        """
        best_recipe = None
        best_score = -1
        
        for recipe in recipes:
            # レシピの食材を抽出
            recipe_ingredients = self._extract_recipe_ingredients(recipe)
            
            # 重複スコアを計算（重複が少ないほど高スコア）
            overlap_count = len(set(recipe_ingredients) & used_ingredients)
            inventory_match_count = len(set(recipe_ingredients) & set(inventory_items))
            
            # スコア計算: 在庫マッチ数 - 重複数
            score = inventory_match_count - overlap_count
            
            if score > best_score:
                best_score = score
                best_recipe = recipe
        
        return best_recipe
    
    def _extract_recipe_ingredients(self, recipe: Dict[str, Any]) -> List[str]:
        """
        レシピから食材を抽出
        
        Args:
            recipe: レシピ辞書
        
        Returns:
            食材リスト
        """
        # 段階提案と同じ方法でcontentフィールドから抽出（正規化済みの食材リスト）
        content = recipe.get("content", "")
        if content:
            # contentは食材をスペースで結合した文字列（例: "鶏もも肉 しいたけ 玉ねぎ"）
            # 段階提案と同じ方法で抽出
            ingredients = content.split()
            # 空文字列を除去
            ingredients = [ingredient.strip() for ingredient in ingredients if ingredient.strip()]
            if ingredients:
                return ingredients
        
        # contentがない場合のみ、main_ingredientsから抽出（フォールバック）
        # ただし、main_ingredientsにはタグ形式が含まれる可能性があるため、優先度は低い
        main_ingredients = recipe.get("main_ingredients", "")
        if main_ingredients:
            # タグ形式を除去して抽出
            import re
            raw_ingredients = main_ingredients.split()
            cleaned_ingredients = []
            for raw_ingredient in raw_ingredients:
                # カンマを除去
                raw_ingredient = raw_ingredient.rstrip(',')
                # タグ形式を除去
                ingredient = re.sub(r'^お肉', '', raw_ingredient)
                ingredient = re.sub(r'^野菜', '', ingredient)
                ingredient = re.sub(r'^お', '', ingredient)
                ingredient = re.sub(r'^＊', '', ingredient)
                ingredient = re.sub(r'＊[^＊]*＊', '', ingredient)
                ingredient = ingredient.strip()
                if ingredient:
                    cleaned_ingredients.append(ingredient)
            if cleaned_ingredients:
                return cleaned_ingredients
        
        return []
    
    def _generate_menu_candidates(
        self, 
        categorized_recipes: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        献立候補を生成
        
        Args:
            categorized_recipes: カテゴリ別レシピ辞書
        
        Returns:
            献立候補リスト
        """
        candidates = []
        
        # 最大3つの候補を生成
        for i in range(min(3, len(categorized_recipes.get("main_dish", [])))):
            candidate = {
                "main_dish": {"title": "", "ingredients": []},
                "side_dish": {"title": "", "ingredients": []},
                "soup": {"title": "", "ingredients": []}
            }
            
            used_ingredients = set()
            
            # 各カテゴリからレシピを選択
            for category in ["main_dish", "side_dish", "soup"]:
                recipes = categorized_recipes.get(category, [])
                if recipes and i < len(recipes):
                    recipe = recipes[i]
                    title = recipe.get("title", "")
                    
                    # レシピの食材を抽出
                    ingredients = self._extract_recipe_ingredients(recipe)
                    
                    candidate[category] = {
                        "title": title,
                        "ingredients": ingredients
                    }
                    
                    used_ingredients.update(ingredients)
            
            candidates.append(candidate)
        
        return candidates
    
    async def convert_categorized_results_to_menu_format(
        self,
        categorized_results: Dict[str, List[Dict[str, Any]]],
        inventory_items: List[str],
        menu_type: str
    ) -> Dict[str, Any]:
        """
        3ベクトルDB検索結果を献立形式に変換（最適化版）
        
        Args:
            categorized_results: カテゴリ別検索結果
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
        
        Returns:
            献立形式の辞書
        """
        try:
            logger.info(f"🔄 [RAG] カテゴリ別結果を献立形式に変換中")
            logger.debug(f"📊 [RAG] 主菜: {len(categorized_results.get('main', []))}件")
            logger.debug(f"📊 [RAG] 副菜: {len(categorized_results.get('sub', []))}件")
            logger.debug(f"📊 [RAG] 汁物: {len(categorized_results.get('soup', []))}件")
            logger.debug(f"📊 [RAG] 在庫食材: {inventory_items}")
            logger.debug(f"📊 [RAG] 献立タイプ: {menu_type}")
            
            # カテゴリ別レシピを献立形式に変換
            categorized_recipes = {
                "main_dish": categorized_results.get("main", []),
                "side_dish": categorized_results.get("sub", []),
                "soup": categorized_results.get("soup", [])
            }
            
            # 各カテゴリから最適なレシピを選択して献立を構成
            selected_menu = {
                "main_dish": {"title": "", "ingredients": []},
                "side_dish": {"title": "", "ingredients": []},
                "soup": {"title": "", "ingredients": []}
            }
            
            used_ingredients = set()
            
            # 各カテゴリから最適なレシピを選択
            for category in ["main_dish", "side_dish", "soup"]:
                recipes = categorized_recipes.get(category, [])
                
                if recipes:
                    # 食材重複を避けながら最適なレシピを選択
                    best_recipe = self._select_best_recipe(
                        recipes, used_ingredients, inventory_items
                    )
                    
                    if best_recipe:
                        title = best_recipe.get("title", "")
                        recipe_ingredients = self._extract_recipe_ingredients(best_recipe)
                        
                        selected_menu[category] = {
                            "title": title,
                            "ingredients": recipe_ingredients
                        }
                        
                        # 使用済み食材を記録
                        used_ingredients.update(recipe_ingredients)
            
            # 候補も生成（複数提案用）
            candidates = self._generate_menu_candidates(categorized_recipes)
            
            # 3ベクトルDBなら事前分類済みなので、LLM制約解決は簡素化
            # 必要に応じてLLMによる最終調整のみ実行
            if candidates and len(candidates) >= 1:
                # シンプルな選択ロジック（LLM呼び出しを削減）
                if not self._is_menu_balanced(selected_menu):
                    llm_selected_menu = await self.llm_solver.solve_menu_constraints_with_llm(
                        candidates, inventory_items, menu_type
                    )
                    # LLMが有効な結果を返した場合はそれを使用
                    if llm_selected_menu and any(llm_selected_menu.get(field, {}).get("title") for field in ["main_dish", "side_dish", "soup"]):
                        selected_menu = llm_selected_menu
            
            result = {
                "candidates": candidates,
                "selected": selected_menu
            }
            
            logger.debug(f"📊 [RAG] 選択された献立: {selected_menu}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [RAG] カテゴリ別献立形式変換エラー: {e}")
            logger.error(f"❌ [RAG] カテゴリ別結果: {categorized_results}")
            logger.error(f"❌ [RAG] 在庫食材: {inventory_items}")
            logger.error(f"❌ [RAG] 献立タイプ: {menu_type}")
            raise
    
    def _is_menu_balanced(self, menu: Dict[str, Any]) -> bool:
        """
        献立がバランス良く構成されているかチェック
        
        Args:
            menu: 献立辞書
        
        Returns:
            バランスが取れているかどうか
        """
        # 各カテゴリにレシピが存在するかチェック
        has_main = bool(menu.get("main_dish", {}).get("title"))
        has_side = bool(menu.get("side_dish", {}).get("title"))
        has_soup = bool(menu.get("soup", {}).get("title"))
        
        # 最低2つのカテゴリがあればバランス良好とみなす
        return sum([has_main, has_side, has_soup]) >= 2