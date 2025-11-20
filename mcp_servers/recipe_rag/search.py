#!/usr/bin/env python3
"""
レシピ検索機能

ChromaDBを使用したレシピの類似検索と部分マッチング機能を提供
"""

from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from config.loggers import GenericLogger
import unicodedata

logger = GenericLogger("mcp", "recipe_rag", initialize_logging=False)


def normalize_ingredient(ingredient):
    """食材名を正規化（カタカナに統一）"""
    if not ingredient:
        return ""
    
    # ひらがなをカタカナに変換
    result = ""
    for char in ingredient:
        if 'ぁ' <= char <= 'ん':
            # ひらがなをカタカナに変換
            katakana_char = chr(ord(char) - ord('ぁ') + ord('ァ'))
            result += katakana_char
        else:
            result += char
    return result


class RecipeSearchEngine:
    """レシピ検索エンジン"""
    
    def __init__(self, vectorstore: Chroma):
        """初期化"""
        self.vectorstore = vectorstore
    
    async def search_similar_recipes(
        self,
        ingredients: List[str],
        menu_type: str,
        excluded_recipes: List[str] = None,
        limit: int = 5,
        main_ingredient: str = None,
        category_detail_keyword: str = None
    ) -> List[Dict[str, Any]]:
        """
        在庫食材に基づく類似レシピ検索（部分マッチング機能付き）
        
        Args:
            ingredients: 在庫食材リスト
            menu_type: メニュータイプ
            excluded_recipes: 除外するレシピタイトル
            limit: 検索結果の最大件数
            main_ingredient: 主要食材
            category_detail_keyword: category_detailのキーワード（otherカテゴリ用）
        
        Returns:
            検索結果のリスト
        """
        try:
            # 部分マッチング機能を使用
            results = await self.search_recipes_by_partial_match(
                ingredients=ingredients,
                menu_type=menu_type,
                excluded_recipes=excluded_recipes,
                limit=limit,
                min_match_score=0.05,  # 低い閾値で幅広く検索
                main_ingredient=main_ingredient,
                category_detail_keyword=category_detail_keyword
            )
            
            # 既存のAPIとの互換性のため、不要なフィールドを削除
            formatted_results = []
            for result in results:
                formatted_result = {
                    "title": result["title"],
                    "category": result["category"],
                    "category_detail": result.get("category_detail", ""),
                    "main_ingredients": result["main_ingredients"],
                    "original_index": result["original_index"],
                    "content": result["content"],
                    "url": result.get("url", "")  # メタデータからURLを取得（Google Search削減のため）
                }
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"類似レシピ検索エラー: {e}")
            raise
    
    async def search_recipes_by_partial_match(
        self,
        ingredients: List[str],
        menu_type: str,
        excluded_recipes: List[str] = None,
        limit: int = 5,
        min_match_score: float = 0.1,
        main_ingredient: str = None,
        category_detail_keyword: str = None
    ) -> List[Dict[str, Any]]:
        """
        在庫食材の部分マッチングでレシピを検索
        
        Args:
            ingredients: 在庫食材リスト
            menu_type: メニュータイプ
            excluded_recipes: 除外するレシピタイトル
            limit: 検索結果の最大件数
            min_match_score: 最小マッチングスコア
            main_ingredient: 主要食材
            category_detail_keyword: category_detailのキーワード（otherカテゴリ用）
        
        Returns:
            検索結果のリスト（マッチングスコア付き）
        """
        try:
            # 在庫食材の重複を除去して正規化
            normalized_ingredients = list(set(ingredients))
            
            # category_detail_keywordがある場合、検索クエリに追加
            category_query_part = ""
            if category_detail_keyword:
                category_query_part = f"{category_detail_keyword} "
            
            # 主要食材がある場合は2段階検索を実行
            if main_ingredient:
                # 主要食材を正規化
                normalized_main = normalize_ingredient(main_ingredient)
                
                # 第1段階: 主要食材のみでの検索（多めに取得）
                main_query = f"{category_query_part}{normalized_main} {normalized_main} {normalized_main} {menu_type}"
                main_results = self.vectorstore.similarity_search(main_query, k=limit * 15)
                
                # 第2段階: 在庫食材込みでの検索
                inventory_query = f"{category_query_part}{normalized_main} {normalized_main} {' '.join(normalized_ingredients)} {menu_type}"
                inventory_results = self.vectorstore.similarity_search(inventory_query, k=limit * 10)
                
                # 結果をマージ（重複除去）
                all_results = main_results + inventory_results
                seen_titles = set()
                results = []
                for result in all_results:
                    title = result.metadata.get('title', '')
                    if title not in seen_titles:
                        seen_titles.add(title)
                        results.append(result)
                        if len(results) >= limit * 20:  # 十分な数を確保
                            break
            else:
                # 主要食材指定なしの場合は従来通り
                query = f"{category_query_part}{' '.join(normalized_ingredients)} {menu_type}"
                results = self.vectorstore.similarity_search(query, k=limit * 4)
            
            # 部分マッチングでフィルタリングとスコアリング
            scored_results = []
            
            for i, result in enumerate(results):
                try:
                    metadata = result.metadata
                    content = result.page_content
                    
                    # タイトルを取得
                    title = metadata.get('title', '')
                    if not title:
                        # page_contentからタイトルを抽出
                        parts = content.split(' | ')
                        if len(parts) >= 1:
                            title = parts[0].strip()
                    
                    # 除外レシピチェック
                    if excluded_recipes:
                        # タイトルを正規化（大文字小文字を無視、空白を除去）
                        normalized_title = title.strip().lower()
                        is_excluded = False
                        for excluded in excluded_recipes:
                            # プレフィックスを除去して正規化
                            normalized_excluded = excluded.replace("主菜: ", "").replace("副菜: ", "").replace("汁物: ", "").strip().lower()
                            # 完全一致のみで判定（部分一致は使用しない）
                            if normalized_title == normalized_excluded:
                                is_excluded = True
                                break
                        if is_excluded:
                            continue
                    
                    # レシピの食材部分を抽出
                    parts = content.split(' | ')
                    recipe_ingredients = parts[0] if len(parts) > 0 else ""
                    
                    # 部分マッチングスコアを計算
                    match_score, matched_ingredients = self._calculate_match_score(
                        recipe_ingredients, normalized_ingredients, main_ingredient
                    )
                    
                    # category_detail_keywordがある場合、category_detailでフィルタリング
                    if category_detail_keyword:
                        category_detail = metadata.get('category_detail', '')
                        if category_detail_keyword not in category_detail:
                            continue
                    
                    # 最小スコア以上のレシピのみを追加
                    if match_score >= min_match_score:
                        formatted_result = {
                            "title": title,
                            "category": metadata.get('recipe_category', ''),
                            "category_detail": metadata.get('category_detail', ''),
                            "main_ingredients": metadata.get('main_ingredients', ''),
                            "original_index": metadata.get('original_index', 0),
                            "content": content,
                            "url": metadata.get('url', ''),  # メタデータからURLを取得（Google Search削減のため）
                            "match_score": match_score,
                            "matched_ingredients": matched_ingredients,
                            "recipe_ingredients": recipe_ingredients
                        }
                        scored_results.append(formatted_result)
                        
                except Exception as e:
                    logger.warning(f"結果処理エラー: {e}")
                    continue
            
            # マッチングスコア順にソート（タイトルで二次ソートして安定化）
            scored_results.sort(key=lambda x: (-x['match_score'], x['title']))
            
            # 主要食材がある場合は、主要食材を含むレシピを優先
            if main_ingredient:
                # 主要食材を含むレシピと含まないレシピに分類
                recipes_with_main = []
                recipes_without_main = []
                
                for result in scored_results:
                    # 主要食材のマッチング判定
                    recipe_ingredients = result.get('recipe_ingredients', '')
                    matched_ingredients = result.get('matched_ingredients', [])
                    
                    # 正規化による主要食材判定
                    has_main_ingredient = self._has_main_ingredient_normalized(
                        main_ingredient, recipe_ingredients, matched_ingredients
                    )
                    
                    if has_main_ingredient:
                        recipes_with_main.append(result)
                    else:
                        recipes_without_main.append(result)
                
                # 主要食材ありのレシピのみを返す（主要食材なしは除外）
                final_results = recipes_with_main[:limit]
            else:
                # 主要食材指定なしの場合は従来通り
                final_results = scored_results[:limit]
            
            return final_results
            
        except Exception as e:
            logger.error(f"部分マッチング検索エラー: {e}")
            raise
    
    def _has_main_ingredient_normalized(self, main_ingredient, recipe_ingredients, matched_ingredients):
        """正規化による主要食材判定"""
        normalized_main = normalize_ingredient(main_ingredient)
        
        # レシピ食材を正規化してチェック
        recipe_words = recipe_ingredients.split()
        for word in recipe_words:
            normalized_word = normalize_ingredient(word)
            # 完全一致または部分一致
            if normalized_main == normalized_word or normalized_main in normalized_word:
                return True
        
        # マッチした食材を正規化してチェック
        for matched in matched_ingredients:
            if normalized_main in normalize_ingredient(matched):
                return True
        
        return False
    
    def _calculate_match_score(
        self, 
        recipe_ingredients: str, 
        normalized_ingredients: List[str],
        main_ingredient: str = None
    ) -> tuple[float, List[str]]:
        """
        マッチングスコアを計算
        
        Args:
            recipe_ingredients: レシピの食材文字列
            normalized_ingredients: 正規化された在庫食材リスト
            main_ingredient: 主要食材
        
        Returns:
            (マッチングスコア, マッチした食材リスト)
        """
        if not recipe_ingredients or not normalized_ingredients:
            return 0.0, []
        
        recipe_words = recipe_ingredients.split()
        matched_count = 0
        total_inventory = len(normalized_ingredients)
        matched_items = []
        
        # 主要食材の重み付け
        main_ingredient_weight = 5.0  # 主要食材の重み
        
        for inventory_item in normalized_ingredients:
            normalized_inventory = normalize_ingredient(inventory_item)
            is_main_ingredient = main_ingredient and normalize_ingredient(inventory_item) == normalize_ingredient(main_ingredient)
            
            # 完全マッチ（正規化後）
            matched = False
            for word in recipe_words:
                normalized_word = normalize_ingredient(word)
                if normalized_inventory == normalized_word:
                    weight = main_ingredient_weight if is_main_ingredient else 1.0
                    matched_count += weight
                    matched_items.append(inventory_item)
                    matched = True
                    break
            
            # 部分マッチ（正規化後）
            if not matched:
                for word in recipe_words:
                    normalized_word = normalize_ingredient(word)
                    if normalized_inventory in normalized_word or normalized_word in normalized_inventory:
                        weight = main_ingredient_weight * 0.5 if is_main_ingredient else 0.5
                        matched_count += weight
                        matched_items.append(inventory_item)
                        break
        
        # スコア計算: マッチした食材数 / 在庫食材数
        # 主要食材がある場合は、主要食材の重みを考慮した正規化
        if main_ingredient and main_ingredient in normalized_ingredients:
            # 主要食材がある場合: (主要食材の重み + その他の食材数) / (主要食材の重み + その他の食材数)
            other_ingredients_count = len(normalized_ingredients) - 1
            max_possible_score = main_ingredient_weight + other_ingredients_count
            match_score = matched_count / max_possible_score if max_possible_score > 0 else 0.0
        else:
            # 主要食材がない場合: 従来の計算
            match_score = matched_count / total_inventory if total_inventory > 0 else 0.0
        
        return match_score, matched_items
