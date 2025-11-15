#!/usr/bin/env python3
"""
MenuDataGenerator - メニューデータ生成処理

レシピデータのJSON形式変換とメニューデータ生成を担当
"""

import json
from typing import Dict, Any, List, Optional
from config.loggers import GenericLogger
from .utils import ResponseProcessorUtils, DISH_TO_CATEGORY_MAPPING, CATEGORY_LABELS, EMOJI_MAP


class MenuDataGenerator:
    """メニューデータ生成クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.menu_generator")
        self.utils = ResponseProcessorUtils()
    
    def generate_menu_data_json(
        self, 
        web_data: Any, 
        ingredients_used: Optional[List[str]] = None,
        main_dish_ingredients: Optional[List[str]] = None,
        side_dish_ingredients: Optional[List[str]] = None,
        soup_ingredients: Optional[List[str]] = None,
        rag_ingredients_used: Optional[List[str]] = None,
        rag_main_dish_ingredients: Optional[List[str]] = None,
        rag_side_dish_ingredients: Optional[List[str]] = None,
        rag_soup_ingredients: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        レシピデータをJSON形式に変換
        
        Args:
            web_data: Web検索結果データ
            ingredients_used: LLMで生成された献立全体で使用された食材リスト（task2の結果から取得）
            main_dish_ingredients: 主菜で使用された食材リスト（task2の結果から取得）
            side_dish_ingredients: 副菜で使用された食材リスト（task2の結果から取得）
            soup_ingredients: 汁物で使用された食材リスト（task2の結果から取得）
            rag_ingredients_used: RAG検索で生成された献立全体で使用された食材リスト（task3の結果から取得）
            rag_main_dish_ingredients: RAG検索の主菜で使用された食材リスト（task3の結果から取得）
            rag_side_dish_ingredients: RAG検索の副菜で使用された食材リスト（task3の結果から取得）
            rag_soup_ingredients: RAG検索の汁物で使用された食材リスト（task3の結果から取得）
        
        Returns:
            仕様書に準拠したJSON形式のレシピデータ
        """
        try:
            # Web検索結果の詳細ログを追加
            self.logger.debug(f"🔍 [MenuDataGenerator] Web data type: {type(web_data)}")
            self.logger.debug(f"📊 [MenuDataGenerator] Web data content: {json.dumps(web_data, ensure_ascii=False, indent=2)}")
            
            # 修正: success判定を追加
            if not isinstance(web_data, dict) or not web_data.get("success"):
                self.logger.warning("⚠️ [MenuDataGenerator] web_data is not successful, skipping JSON generation")
                return None
            
            # 成功時: dataからllm_menuとrag_menuを取得
            data = web_data.get("data", {})
            
            # メニュー構造を構築
            menu_data = self.build_menu_structure()
            
            # llm_menu と rag_menu からレシピを抽出
            for menu_type in ['llm_menu', 'rag_menu']:
                if menu_type not in data:
                    continue
                    
                menu = data[menu_type]
                # 各レシピごとの食材情報を設定
                if menu_type == 'llm_menu':
                    self.extract_recipes_by_type(
                        menu, 
                        menu_type, 
                        menu_data, 
                        data, 
                        main_dish_ingredients=main_dish_ingredients,
                        side_dish_ingredients=side_dish_ingredients,
                        soup_ingredients=soup_ingredients,
                        ingredients_used=ingredients_used
                    )
                else:
                    # rag_menuの場合はRAG検索結果から食材情報を取得
                    self.extract_recipes_by_type(
                        menu, 
                        menu_type, 
                        menu_data, 
                        data, 
                        main_dish_ingredients=rag_main_dish_ingredients,
                        side_dish_ingredients=rag_side_dish_ingredients,
                        soup_ingredients=rag_soup_ingredients,
                        ingredients_used=rag_ingredients_used
                    )
            
            # 空のセクションをチェック
            if not self.has_menu_data(menu_data):
                self.logger.warning("⚠️ [MenuDataGenerator] No recipe data found for JSON generation")
                return None
            
            # 生成されたmenu_dataの全文ログを追加
            self.logger.debug(f"📋 [MenuDataGenerator] Generated menu_data: {json.dumps(menu_data, ensure_ascii=False, indent=2)}")
            self.logger.info(f"✅ [MenuDataGenerator] Menu data JSON generated successfully")
            return menu_data
            
        except Exception as e:
            self.logger.error(f"❌ [MenuDataGenerator] Error generating menu data JSON: {e}")
            return None
    
    def build_menu_structure(self) -> Dict[str, Any]:
        """
        メニュー構造を構築
        
        Returns:
            初期化されたメニューデータ構造
        """
        return {
            "innovative": {
                "title": "📝 斬新な提案",
                "recipes": {
                    "main": [],
                    "side": [],
                    "soup": []
                }
            },
            "traditional": {
                "title": "📚 伝統的な提案",
                "recipes": {
                    "main": [],
                    "side": [],
                    "soup": []
                }
            }
        }
    
    def extract_recipes_by_type(
        self, 
        menu: Dict[str, Any], 
        menu_type: str, 
        menu_data: Dict[str, Any], 
        web_data: Dict[str, Any], 
        main_dish_ingredients: Optional[List[str]] = None,
        side_dish_ingredients: Optional[List[str]] = None,
        soup_ingredients: Optional[List[str]] = None,
        ingredients_used: Optional[List[str]] = None
    ) -> None:
        """
        タイプ別レシピ抽出
        
        Args:
            menu: メニューデータ
            menu_type: メニュータイプ（llm_menu または rag_menu）
            menu_data: 構築中のメニューデータ
            web_data: 元のWebデータ
            main_dish_ingredients: 主菜で使用された食材リスト（llm_menuの場合のみ）
            side_dish_ingredients: 副菜で使用された食材リスト（llm_menuの場合のみ）
            soup_ingredients: 汁物で使用された食材リスト（llm_menuの場合のみ）
            ingredients_used: 献立全体で使用された食材リスト（llm_menuの場合のみ、後方互換性のため）
        """
        # カテゴリ別に処理
        for dish_type in ['main_dish', 'side_dish', 'soup']:
            if dish_type not in menu or 'recipes' not in menu[dish_type]:
                continue
                
            recipes = menu[dish_type]['recipes']
            if not recipes:
                continue
            
            # カテゴリマッピング
            category = DISH_TO_CATEGORY_MAPPING.get(dish_type, 'main')
            
            # 絵文字マッピング
            emoji = EMOJI_MAP.get(category, '🍽️')
            
            # レシピを変換（カテゴリ統合処理）
            category_urls = []  # カテゴリ全体のURLリスト
            
            for recipe in recipes[:3]:  # 最大3件まで
                urls = self.extract_recipe_urls(recipe)
                category_urls.extend(urls)  # 全URLを統合
            
            # カテゴリに応じた食材を取得
            category_ingredients = None
            if dish_type == 'main_dish':
                category_ingredients = main_dish_ingredients
            elif dish_type == 'side_dish':
                category_ingredients = side_dish_ingredients
            elif dish_type == 'soup':
                category_ingredients = soup_ingredients
            
            # カテゴリにURLがある場合は1つのレシピオブジェクトとして追加
            if category_urls:
                self.classify_and_add_recipe(
                    category_urls, 
                    category, 
                    emoji, 
                    menu_type, 
                    web_data, 
                    menu_data, 
                    category_ingredients
                )
    
    def classify_and_add_recipe(
        self, 
        category_urls: List[Dict[str, str]], 
        category: str, 
        emoji: str, 
        menu_type: str, 
        web_data: Dict[str, Any], 
        menu_data: Dict[str, Any], 
        category_ingredients: Optional[List[str]] = None
    ) -> None:
        """
        レシピ分類・追加
        
        Args:
            category_urls: カテゴリのURLリスト
            category: カテゴリ名（'main', 'side', 'soup'）
            emoji: 絵文字
            menu_type: メニュータイプ（llm_menu または rag_menu）
            web_data: 元のWebデータ
            menu_data: 構築中のメニューデータ
            category_ingredients: このカテゴリで使用された食材リスト（llm_menuの場合のみ）
        """
        # 実際の献立提案からタイトルを生成
        actual_menu_type = 'llm' if menu_type == 'llm_menu' else 'rag'
        actual_title = self.utils.extract_actual_menu_title(web_data, category, actual_menu_type)
        category_label = CATEGORY_LABELS.get(category, category)
        combined_title = f"{category_label}: {actual_title}" if actual_title else f"{category_label}:"
        
        combined_recipe = {
            "title": combined_title,
            "emoji": emoji,
            "category": category,
            "urls": category_urls
        }
        
        # category_ingredientsがある場合はingredientsフィールドを追加（llm_menuとrag_menuの両方）
        if category_ingredients:
            combined_recipe["ingredients"] = category_ingredients
            self.logger.debug(f"✅ [MenuDataGenerator] Added ingredients to recipe '{combined_title}' (category: {category}, menu_type: {menu_type}): {category_ingredients}")
        
        # innovative または traditional に分類
        target_section = self.classify_recipe(combined_recipe, menu_type)
        menu_data[target_section]["recipes"][category].append(combined_recipe)
    
    def has_menu_data(self, menu_data: Dict[str, Any]) -> bool:
        """
        メニューデータが存在するかチェック
        
        Args:
            menu_data: メニューデータ
        
        Returns:
            データが存在する場合True
        """
        for section in ['innovative', 'traditional']:
            for category in ['main', 'side', 'soup']:
                if menu_data[section]["recipes"][category]:
                    return True
        return False
    
    def extract_recipe_urls(self, recipe: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        レシピからURL情報を抽出
        
        Args:
            recipe: レシピデータ
        
        Returns:
            URL情報のリスト
        """
        urls = []
        
        try:
            # レシピのURL情報を抽出（実際の構造に応じて調整が必要）
            if 'url' in recipe:
                url = str(recipe['url'])
                title = str(recipe.get('title', 'レシピ詳細'))
                domain = self.utils.extract_domain(url)
                
                urls.append({
                    "title": title,
                    "url": url,
                    "domain": domain
                })
            
            # 複数URLがある場合の処理（必要に応じて拡張）
            
        except Exception as e:
            self.logger.error(f"❌ [MenuDataGenerator] Error extracting recipe URLs: {e}")
        
        return urls
    
    def classify_recipe(self, recipe: Dict[str, Any], menu_type: str) -> str:
        """
        レシピをinnovativeまたはtraditionalに分類
        
        Args:
            recipe: レシピデータ
            menu_type: メニュータイプ（llm_menu または rag_menu）
        
        Returns:
            'innovative' または 'traditional'
        """
        # 簡易的な分類ロジック
        # llm_menu = innovative, rag_menu = traditional
        if menu_type == 'llm_menu':
            return 'innovative'
        else:
            return 'traditional'
