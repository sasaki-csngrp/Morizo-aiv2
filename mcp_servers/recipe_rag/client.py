#!/usr/bin/env python3
"""
Recipe RAG クライアント

レシピRAG検索のメインクライアント
各機能モジュールを統合して提供
"""

import os
from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logging

# ロガーの設定
from config.loggers import GenericLogger
logger = GenericLogger("mcp", "recipe_rag", initialize_logging=False)

# ルートロガーを取得してハンドラーを設定
root_logger = logging.getLogger('morizo_ai')
if not root_logger.handlers:
    from config.logging import setup_logging
    setup_logging(initialize=False)  # ローテーションなし

# 機能モジュールのインポート
from .search import RecipeSearchEngine
from .menu_format import MenuFormatter
from .llm_solver import LLMConstraintSolver


class RecipeRAGClient:
    """レシピRAG検索クライアント"""
    
    def __init__(self):
        """初期化"""
        load_dotenv()
        
        # 環境変数から4つのChromaDBのパスを取得
        self.vector_db_path_main = os.getenv("CHROMA_PERSIST_DIRECTORY_MAIN", "./recipe_vector_db_main")
        self.vector_db_path_sub = os.getenv("CHROMA_PERSIST_DIRECTORY_SUB", "./recipe_vector_db_sub")
        self.vector_db_path_soup = os.getenv("CHROMA_PERSIST_DIRECTORY_SOUP", "./recipe_vector_db_soup")
        self.vector_db_path_other = os.getenv("CHROMA_PERSIST_DIRECTORY_OTHER", "./recipe_vector_db_other_2")
        
        # 環境変数から埋め込みモデルを取得
        embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self._vectorstores = None
        
        # LLMクライアントの初期化
        self.llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm_client = AsyncOpenAI()
        
        # 機能モジュールの初期化
        self._search_engine = None
        self._menu_formatter = None
        self._llm_solver = None
    
    def _get_vectorstores(self) -> Dict[str, Chroma]:
        """4つのベクトルストアの取得（遅延初期化）"""
        if self._vectorstores is None:
            try:
                self._vectorstores = {
                    "main": Chroma(
                        persist_directory=self.vector_db_path_main,
                        embedding_function=self.embeddings
                    ),
                    "sub": Chroma(
                        persist_directory=self.vector_db_path_sub,
                        embedding_function=self.embeddings
                    ),
                    "soup": Chroma(
                        persist_directory=self.vector_db_path_soup,
                        embedding_function=self.embeddings
                    ),
                    "other": Chroma(
                        persist_directory=self.vector_db_path_other,
                        embedding_function=self.embeddings
                    )
                }
                logger.debug(f"4つのベクトルストアを読み込みました")
                logger.debug(f"🔍 [RAG] 主菜: {self.vector_db_path_main}")
                logger.debug(f"🔍 [RAG] 副菜: {self.vector_db_path_sub}")
                logger.debug(f"🔍 [RAG] 汁物: {self.vector_db_path_soup}")
                logger.debug(f"🔍 [RAG] その他: {self.vector_db_path_other}")
            except Exception as e:
                logger.error(f"ベクトルストア読み込みエラー: {e}")
                raise
        return self._vectorstores
    
    def _get_search_engines(self) -> Dict[str, RecipeSearchEngine]:
        """4つの検索エンジンの取得（遅延初期化）"""
        if not hasattr(self, '_search_engines') or self._search_engines is None:
            vectorstores = self._get_vectorstores()
            self._search_engines = {
                "main": RecipeSearchEngine(vectorstores["main"]),
                "sub": RecipeSearchEngine(vectorstores["sub"]),
                "soup": RecipeSearchEngine(vectorstores["soup"]),
                "other": RecipeSearchEngine(vectorstores["other"])
            }
        return self._search_engines
    
    def _get_menu_formatter(self) -> MenuFormatter:
        """メニューフォーマッターの取得（遅延初期化）"""
        if self._menu_formatter is None:
            llm_solver = self._get_llm_solver()
            self._menu_formatter = MenuFormatter(llm_solver)
        return self._menu_formatter
    
    def _get_llm_solver(self) -> LLMConstraintSolver:
        """LLM制約解決エンジンの取得（遅延初期化）"""
        if self._llm_solver is None:
            self._llm_solver = LLMConstraintSolver(self.llm_client, self.llm_model)
        return self._llm_solver
    
    async def search_recipes_by_category(
        self,
        ingredients: List[str],
        menu_type: str,
        excluded_recipes: List[str] = None,
        limit: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        3つのベクトルDBで並列検索（主菜・副菜・汁物別）
        
        Args:
            ingredients: 在庫食材リスト
            menu_type: メニュータイプ
            excluded_recipes: 除外するレシピタイトル
            limit: 各カテゴリの検索結果の最大件数
        
        Returns:
            カテゴリ別検索結果の辞書
        """
        try:
            import asyncio
            
            search_engines = self._get_search_engines()
            
            # 3つのベクトルDBで並列検索
            async def search_category(category: str, search_engine: RecipeSearchEngine):
                try:
                    results = await search_engine.search_similar_recipes(
                        ingredients, menu_type, excluded_recipes, limit
                    )
                    return category, results
                except Exception as e:
                    logger.error(f"❌ [RAG] {category}検索エラー: {e}")
                    return category, []
            
            # 並列実行
            tasks = [
                search_category("main", search_engines["main"]),
                search_category("sub", search_engines["sub"]),
                search_category("soup", search_engines["soup"])
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 結果を整理
            categorized_results = {
                "main": [],
                "sub": [],
                "soup": []
            }
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"❌ [RAG] 検索エラー: {result}")
                    continue
                elif isinstance(result, tuple) and len(result) == 2:
                    category, recipes = result
                    categorized_results[category] = recipes
            
            logger.info(f"🔍 [RAG] カテゴリ別検索完了")
            logger.debug(f"📊 [RAG] 主菜: {len(categorized_results['main'])}件")
            logger.debug(f"📊 [RAG] 副菜: {len(categorized_results['sub'])}件")
            logger.debug(f"📊 [RAG] 汁物: {len(categorized_results['soup'])}件")
            
            return categorized_results
            
        except Exception as e:
            logger.error(f"❌ [RAG] カテゴリ別検索エラー: {e}")
            raise
    
    async def convert_rag_results_to_menu_format(
        self,
        rag_results: List[Dict[str, Any]],
        inventory_items: List[str],
        menu_type: str
    ) -> Dict[str, Any]:
        """
        RAG検索結果を献立形式に変換
        
        Args:
            rag_results: RAG検索結果のリスト
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
        
        Returns:
            献立形式の辞書
        """
        menu_formatter = self._get_menu_formatter()
        return await menu_formatter.convert_rag_results_to_menu_format(
            rag_results, inventory_items, menu_type
        )
    
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
        menu_formatter = self._get_menu_formatter()
        return await menu_formatter.convert_categorized_results_to_menu_format(
            categorized_results, inventory_items, menu_type
        )
    
    async def search_main_dish_candidates(
        self,
        ingredients: List[str],
        menu_type: str,
        main_ingredient: str = None,  # 主要食材
        excluded_recipes: List[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        主菜候補を検索（主要食材考慮）
        
        後方互換性のため、汎用メソッド `search_candidates()` を内部で呼び出します。
        """
        return await self.search_candidates(
            ingredients=ingredients,
            menu_type=menu_type,
            category="main",
            main_ingredient=main_ingredient,
            used_ingredients=None,
            excluded_recipes=excluded_recipes,
            limit=limit
        )
    
    def _extract_ingredients_from_content(self, content: str) -> List[str]:
        """contentフィールドから食材を抽出"""
        if not content:
            return []
        
        # スペースで分割して食材リストを作成
        ingredients = content.split()
        
        # 空文字列を除去
        ingredients = [ingredient.strip() for ingredient in ingredients if ingredient.strip()]
        
        return ingredients

    async def search_candidates(
        self,
        ingredients: List[str],
        menu_type: str,
        category: str,  # "main", "sub", "soup", "other"
        main_ingredient: str = None,
        used_ingredients: List[str] = None,
        excluded_recipes: List[str] = None,
        limit: int = 3,
        category_detail_keyword: str = None
    ) -> List[Dict[str, Any]]:
        """
        汎用候補検索メソッド（主菜・副菜・汁物・その他対応）
        
        categoryに応じて適切なベクトルストアを選択：
        - "main" → main ベクトルストア
        - "sub" → sub ベクトルストア
        - "soup" → soup ベクトルストア
        - "other" → other ベクトルストア
        
        Args:
            ingredients: 在庫食材リスト
            menu_type: 献立タイプ
            category: "main", "sub", "soup", "other"
            main_ingredient: 主要食材
            used_ingredients: すでに使った食材（除外する）
            excluded_recipes: 除外レシピ
            limit: 検索件数
            category_detail_keyword: category_detailのキーワード（otherカテゴリ用）
        
        Returns:
            検索結果のリスト
        """
        try:
            logger.debug(f"🔍 [RAG] {category}候補を検索中")
            logger.debug(f"🔍 [RAG] 検索上限: {limit}")
            
            # 適切なベクトルストアを選択
            if category not in ["main", "sub", "soup", "other"]:
                raise ValueError(f"Invalid category: {category}")
            
            search_engine = self._get_search_engines()[category]
            
            # 検索クエリを構築
            search_query = ingredients.copy()
            
            # 副菜・汁物の場合、主菜で使った食材を除外
            if category in ["sub", "soup"] and used_ingredients:
                search_query = [ing for ing in search_query if ing not in used_ingredients]
                logger.debug(f"🔍 [RAG] 検索クエリから使用済み食材{len(used_ingredients)}件を除外")
            
            # 主要食材の処理（主菜の場合のみ有効）
            rag_main_ingredient = None
            if main_ingredient and category == "main":
                search_query.insert(0, main_ingredient)  # 主要食材を優先
                rag_main_ingredient = main_ingredient
            elif main_ingredient and category in ["sub", "soup"]:
                # 副菜・汁物ではmain_ingredientは使用しない（プランナーの誤認識を無視）
                logger.info(f"⚠️ [RAG] {category}カテゴリでは主要食材'{main_ingredient}'を無視します")
                rag_main_ingredient = None
            
            # RAG検索（除外レシピを渡す）
            results = await search_engine.search_similar_recipes(
                search_query, menu_type, excluded_recipes, limit, rag_main_ingredient, category_detail_keyword
            )
            
            # 各結果に使用食材リストを含める
            for result in results:
                if "ingredients" not in result:
                    # contentフィールドから食材を抽出
                    content = result.get("content", "")
                    ingredients = self._extract_ingredients_from_content(content)
                    result["ingredients"] = ingredients
            
            logger.debug(f"✅ [RAG] {category}候補を発見")
            logger.debug(f"📊 [RAG] {category}候補{len(results)}件を発見")
            return results
            
        except Exception as e:
            logger.error(f"❌ [RAG] {category}候補の検索に失敗: {e}")
            return []