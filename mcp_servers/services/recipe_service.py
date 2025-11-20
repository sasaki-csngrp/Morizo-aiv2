#!/usr/bin/env python3
"""
RecipeService - レシピ関連のビジネスロジックを扱うサービス層

MCPツール層からビジネスロジックを分離し、再利用性とテスト容易性を向上
"""

import asyncio
import traceback
from typing import Dict, Any, List, Optional
from supabase import Client

from mcp_servers.recipe_llm import RecipeLLM
from mcp_servers.recipe_rag import RecipeRAGClient
from mcp_servers.recipe_web import get_search_client, prioritize_recipes, filter_recipe_results
from mcp_servers.models.recipe_models import RecipeProposal, MenuResult, WebSearchResult
from config.loggers import GenericLogger


class RecipeService:
    """レシピ関連のビジネスロジックを扱うサービス層"""
    
    def __init__(self):
        """初期化"""
        self.llm_client = RecipeLLM()
        self.rag_client = RecipeRAGClient()
        self.logger = GenericLogger("mcp", "recipe_service", initialize_logging=False)
    
    # ============================================================================
    # ヘルパー関数
    # ============================================================================
    
    def _format_rag_menu_result(
        self,
        menu_result: Dict[str, Any],
        inventory_items: List[str]
    ) -> MenuResult:
        """
        RAG検索結果をMenuResultに変換
        
        Args:
            menu_result: RAG検索結果（selectedキーを含む）
            inventory_items: 在庫食材リスト
        
        Returns:
            MenuResult: 変換済みデータモデル
        """
        selected_menu = menu_result.get("selected", {})
        
        main_dish_data = selected_menu.get("main_dish", {})
        side_dish_data = selected_menu.get("side_dish", {})
        soup_data = selected_menu.get("soup", {})
        
        main_dish_ingredients = main_dish_data.get("ingredients", []) if isinstance(main_dish_data, dict) else []
        side_dish_ingredients = side_dish_data.get("ingredients", []) if isinstance(side_dish_data, dict) else []
        soup_ingredients = soup_data.get("ingredients", []) if isinstance(soup_data, dict) else []
        
        ingredients_used = []
        ingredients_used.extend(main_dish_ingredients)
        ingredients_used.extend(side_dish_ingredients)
        ingredients_used.extend(soup_ingredients)
        ingredients_used = list(set(ingredients_used))
        
        return MenuResult(
            main_dish=main_dish_data.get("title", "") if isinstance(main_dish_data, dict) else str(main_dish_data),
            side_dish=side_dish_data.get("title", "") if isinstance(side_dish_data, dict) else str(side_dish_data),
            soup=soup_data.get("title", "") if isinstance(soup_data, dict) else str(soup_data),
            main_dish_ingredients=main_dish_ingredients,
            side_dish_ingredients=side_dish_ingredients,
            soup_ingredients=soup_ingredients,
            ingredients_used=ingredients_used
        )
    
    def _categorize_web_search_results(
        self,
        results: List[Dict[str, Any]],
        recipe_titles: List[str],
        menu_categories: List[str],
        menu_source: str
    ) -> Dict[str, Any]:
        """
        Web検索結果をllm_menu/rag_menu構造に分類
        
        Args:
            results: 検索結果のリスト
            recipe_titles: レシピタイトルのリスト
            menu_categories: カテゴリのリスト
            menu_source: 検索元（llm, rag, mixed）
        
        Returns:
            Dict[str, Any]: 分類済み結果
        """
        categorized_results = {
            "llm_menu": {
                "main_dish": {"title": "", "recipes": []},
                "side_dish": {"title": "", "recipes": []},
                "soup": {"title": "", "recipes": []}
            },
            "rag_menu": {
                "main_dish": {"title": "", "recipes": []},
                "side_dish": {"title": "", "recipes": []},
                "soup": {"title": "", "recipes": []}
            }
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception) or not result.get("success"):
                continue
            
            recipes = result.get("data", [])
            category = menu_categories[i] if menu_categories and i < len(menu_categories) else "main_dish"
            source = "rag_menu" if (menu_source == "rag" or (menu_source == "mixed" and i >= len(recipe_titles) // 2)) else "llm_menu"
            
            categorized_results[source][category] = {
                "title": recipe_titles[i],
                "recipes": recipes
            }
        
        return categorized_results
    
    async def _search_single_recipe_with_rag_fallback(
        self,
        title: str,
        index: int,
        rag_results: Dict[str, Dict[str, Any]],
        menu_source: str,
        recipe_titles: List[str],
        num_results: int,
        use_perplexity: bool = None
    ) -> Dict[str, Any]:
        """
        単一の料理名でレシピ検索（RAG検索結果のURLを優先）
        
        Args:
            title: レシピタイトル
            index: インデックス（menu_source判定に使用）
            rag_results: RAG検索結果の辞書
            menu_source: 検索元（llm, rag, mixed）
            recipe_titles: レシピタイトルのリスト（menu_source判定に使用）
            num_results: 取得結果数
            use_perplexity: 強制的にPerplexityを使用するか（Noneの場合はmenu_sourceに基づいて決定）
        
        Returns:
            Dict[str, Any]: 検索結果
        """
        web_search_results = []
        
        # RAG検索結果からURLを取得（既に取得済みの場合）
        if rag_results and title in rag_results:
            rag_result = rag_results[title]
            rag_url = rag_result.get('url', '')
            if rag_url:
                web_search_result = WebSearchResult(
                    title=title,
                    url=rag_url,
                    source="vector_db",
                    description=rag_result.get('category_detail', ''),
                    site="cookpad.com" if "cookpad.com" in rag_url else "other"
                )
                web_search_results.append(web_search_result.to_dict())
                
                # RAG結果からURLを1件取得した場合、残りをPerplexityで検索
                # num_resultsが1より大きい場合のみ追加検索を実行
                if num_results > 1:
                    remaining_count = num_results - 1
                    
                    # use_perplexityがTrueの場合、またはmenu_source="rag"でuse_perplexityがNoneの場合、Perplexityを使用
                    should_use_perplexity = use_perplexity is True or (use_perplexity is None and menu_source == "rag")
                    
                    if should_use_perplexity:
                        effective_source = "rag"  # menu_source="rag"として扱う
                        client = get_search_client(menu_source=effective_source, use_perplexity=True)
                    else:
                        # 通常の判定ロジック
                        effective_source = menu_source
                        if menu_source == "mixed":
                            total_count = len(recipe_titles)
                            if index < total_count / 2:
                                effective_source = "llm"
                            else:
                                effective_source = "rag"
                        client = get_search_client(menu_source=effective_source, use_perplexity=use_perplexity)
                    
                    additional_recipes = await client.search_recipes(title, remaining_count)
                    
                    # レシピを優先順位でソート
                    prioritized_recipes = prioritize_recipes(additional_recipes)
                    # 結果をフィルタリング
                    filtered_recipes = filter_recipe_results(prioritized_recipes)
                    
                    # WebSearchResultに変換して追加
                    for recipe in filtered_recipes:
                        web_search_result = WebSearchResult(
                            title=recipe.get("title", ""),
                            url=recipe.get("url", ""),
                            source=recipe.get("source", "web"),
                            description=recipe.get("description"),
                            site=recipe.get("site")
                        )
                        web_search_results.append(web_search_result.to_dict())
                
                return {
                    "success": True,
                    "data": web_search_results,
                    "title": title,
                    "count": len(web_search_results)
                }
        
        # URLがない場合のみWeb検索APIを呼び出す
        effective_source = menu_source
        if menu_source == "mixed":
            total_count = len(recipe_titles)
            if index < total_count / 2:
                effective_source = "llm"
            else:
                effective_source = "rag"
        
        client = get_search_client(menu_source=effective_source, use_perplexity=use_perplexity)
        recipes = await client.search_recipes(title, num_results)
        
        # レシピを優先順位でソート
        prioritized_recipes = prioritize_recipes(recipes)
        
        # 結果をフィルタリング
        filtered_recipes = filter_recipe_results(prioritized_recipes)
        
        # WebSearchResultに変換
        for recipe in filtered_recipes:
            web_search_result = WebSearchResult(
                title=recipe.get("title", ""),
                url=recipe.get("url", ""),
                source=recipe.get("source", "web"),
                description=recipe.get("description"),
                site=recipe.get("site")
            )
            web_search_results.append(web_search_result.to_dict())
        
        return {
            "success": True,
            "data": web_search_results,
            "title": title,
            "count": len(web_search_results)
        }
    
    # ============================================================================
    # ビジネスロジックメソッド
    # ============================================================================
    
    async def generate_proposals(
        self,
        client: Client,
        inventory_items: List[str],
        category: str,
        menu_type: str = "",
        main_ingredient: Optional[str] = None,
        used_ingredients: List[str] = None,
        excluded_recipes: List[str] = None,
        category_detail_keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        汎用提案メソッド（主菜・副菜・汁物・その他対応）
        
        Args:
            client: 認証済みSupabaseクライアント
            inventory_items: 在庫食材リスト
            category: "main", "sub", "soup", "other"
            menu_type: 献立タイプ
            main_ingredient: 主食材
            used_ingredients: 使用済み食材
            excluded_recipes: 除外レシピ
            category_detail_keyword: カテゴリ詳細キーワード
        
        Returns:
            Dict[str, Any]: 提案結果
        """
        # Phase 3A: セッション内の提案済みレシピは、呼び出し元でexcluded_recipesとして渡されるため
        # MCPサーバー内では追加処理は不要（プロセス分離のため）
        all_excluded = (excluded_recipes or []).copy()
        
        # otherカテゴリの場合はused_ingredientsを使用しない（単体動作のため）
        if category == "other":
            used_ingredients = None
        
        # LLMとRAGを並列実行（汎用メソッドを使用）
        try:
            llm_task = self.llm_client.generate_candidates(
                inventory_items=inventory_items,
                menu_type=menu_type,
                category=category,
                main_ingredient=main_ingredient,
                used_ingredients=used_ingredients,
                excluded_recipes=all_excluded,
                count=2,
                category_detail_keyword=category_detail_keyword
            )
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] Failed to create LLM task: {e}")
            self.logger.error(f"❌ [RECIPE] LLM task creation error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] LLM task creation traceback: {traceback.format_exc()}")
            raise
        
        try:
            rag_task = self.rag_client.search_candidates(
                ingredients=inventory_items,
                menu_type=menu_type,
                category=category,
                main_ingredient=main_ingredient,
                used_ingredients=used_ingredients,
                excluded_recipes=all_excluded,
                limit=3,
                category_detail_keyword=category_detail_keyword
            )
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] Failed to create RAG task: {e}")
            self.logger.error(f"❌ [RECIPE] RAG task creation error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] RAG task creation traceback: {traceback.format_exc()}")
            raise
        
        # 両方の結果を待つ（並列実行）
        try:
            llm_result, rag_result = await asyncio.gather(llm_task, rag_task)
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] asyncio.gather failed: {e}")
            self.logger.error(f"❌ [RECIPE] asyncio.gather error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] asyncio.gather traceback: {traceback.format_exc()}")
            raise
        
        # 統合（sourceフィールドを追加）
        recipe_proposals = []
        
        # LLM結果の処理
        if llm_result.get("success"):
            try:
                llm_candidates = llm_result["data"]["candidates"]
                # LLM候補をRecipeProposalに変換
                for candidate in llm_candidates:
                    proposal = RecipeProposal(
                        title=candidate.get("title", ""),
                        ingredients=candidate.get("ingredients", []),
                        source="llm",
                        url=candidate.get("url"),
                        description=candidate.get("description")
                    )
                    recipe_proposals.append(proposal)
            except Exception as e:
                self.logger.error(f"❌ [RECIPE] Error processing LLM results: {e}")
                self.logger.error(f"❌ [RECIPE] LLM result processing error type: {type(e).__name__}")
                self.logger.error(f"❌ [RECIPE] LLM result processing traceback: {traceback.format_exc()}")
        else:
            self.logger.warning(f"⚠️ [RECIPE] LLM result indicates failure: {llm_result.get('error', 'Unknown error')}")
        
        # RAG結果の処理
        if rag_result:
            try:
                # RAG候補をRecipeProposalに変換
                for r in rag_result:
                    proposal = RecipeProposal(
                        title=r.get("title", ""),
                        ingredients=r.get("ingredients", []),
                        source="rag",
                        url=r.get("url"),
                        description=r.get("description")
                    )
                    recipe_proposals.append(proposal)
            except Exception as e:
                self.logger.error(f"❌ [RECIPE] Error processing RAG results: {e}")
                self.logger.error(f"❌ [RECIPE] RAG result processing error type: {type(e).__name__}")
                self.logger.error(f"❌ [RECIPE] RAG result processing traceback: {traceback.format_exc()}")
        else:
            self.logger.warning(f"⚠️ [RECIPE] RAG result is empty or falsy")
        
        # RecipeProposalを辞書に変換
        candidates = [proposal.to_dict() for proposal in recipe_proposals]
        
        self.logger.info(f"✅ [RECIPE] generate_proposals completed")
        
        return {
            "success": True,
            "data": {
                "candidates": candidates,
                "category": category,
                "total": len(candidates),
                "main_ingredient": main_ingredient,
                "excluded_count": len(all_excluded),
                "llm_count": len(llm_result.get("data", {}).get("candidates", [])) if llm_result.get("success") else 0,
                "rag_count": len(rag_result) if rag_result else 0
            }
        }
    
    async def search_recipes_from_web(
        self,
        recipe_titles: List[str],
        num_results: int = 5,
        menu_categories: List[str] = None,
        menu_source: str = "mixed",
        rag_results: Dict[str, Dict[str, Any]] = None,
        use_perplexity: bool = None
    ) -> Dict[str, Any]:
        """
        Web検索によるレシピ検索
        
        Args:
            recipe_titles: 検索するレシピタイトルのリスト
            num_results: 各料理名あたりの取得結果数
            menu_categories: 料理名の分類リスト
            menu_source: 検索元（llm, rag, mixed）
            rag_results: RAG検索結果の辞書
            use_perplexity: 強制的にPerplexityを使用するか（Noneの場合はmenu_sourceに基づいて決定）
        
        Returns:
            Dict[str, Any]: 分類された検索結果
        """
        async def search_single_recipe(title: str, index: int) -> Dict[str, Any]:
            """単一の料理名でレシピ検索（RAG検索結果のURLを優先）"""
            try:
                return await self._search_single_recipe_with_rag_fallback(
                    title=title,
                    index=index,
                    rag_results=rag_results,
                    menu_source=menu_source,
                    recipe_titles=recipe_titles,
                    num_results=num_results,
                    use_perplexity=use_perplexity
                )
            except Exception as e:
                self.logger.error(f"❌ [RECIPE] Error searching for '{title}': {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "title": title,
                    "count": 0
                }
        
        # 並列実行（インデックスを渡す）
        tasks = [search_single_recipe(title, index) for index, title in enumerate(recipe_titles)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 単一カテゴリ提案かどうかを判定（主菜・副菜・汁物のいずれか1つのみ）
        # menu_categoriesがNone、空、または単一カテゴリのみの場合
        single_category = None
        if not menu_categories or len(menu_categories) == 0:
            # menu_categoriesが指定されていない場合は、デフォルトでmain_dishとみなす
            single_category = "main_dish"
        elif len(set(menu_categories)) == 1:
            # すべて同じカテゴリの場合
            single_category = menu_categories[0]
        
        is_single_category = single_category in ["main_dish", "side_dish", "soup"]
        
        successful_searches = 0
        # 単一カテゴリ提案の場合は、候補リストの順序に合わせてレシピを配置
        single_category_recipes = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"❌ [RECIPE] Search failed for '{recipe_titles[i]}': {result}")
                continue
            elif result.get("success"):
                recipes = result.get("data", [])
                successful_searches += 1
                # 単一カテゴリ提案の場合は、各レシピタイトルに対応する最初のレシピを取得
                # （候補リストの順序と一致させるため）
                if is_single_category:
                    if recipes:
                        single_category_recipes.append(recipes[0])
            else:
                self.logger.error(f"❌ [RECIPE] Search failed for '{recipe_titles[i]}': {result.get('error')}")
        
        # 単一カテゴリ提案の場合はシンプルな構造を返す
        if is_single_category:
            result = {
                "success": True,
                "data": {
                    single_category: {
                        "title": recipe_titles[0] if recipe_titles else "",
                        "recipes": single_category_recipes
                    }
                },
                "total_count": len(single_category_recipes),
                "searches_completed": successful_searches,
                "total_searches": len(recipe_titles)
            }
        else:
            # 一括提案の場合はllm_menu/rag_menu構造を返す
            categorized_results = self._categorize_web_search_results(
                results=results,
                recipe_titles=recipe_titles,
                menu_categories=menu_categories,
                menu_source=menu_source
            )
            
            result = {
                "success": True,
                "data": categorized_results,
                "total_count": sum(len(cat["recipes"]) for menu in categorized_results.values() for cat in menu.values()),
                "searches_completed": successful_searches,
                "total_searches": len(recipe_titles)
            }
        
        return result
    
    async def search_menu_from_rag(
        self,
        inventory_items: List[str],
        menu_type: str = "",
        excluded_recipes: List[str] = None
    ) -> Dict[str, Any]:
        """
        RAG検索による伝統的な献立タイトル生成
        
        Args:
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
            excluded_recipes: 除外するレシピタイトル
        
        Returns:
            Dict[str, Any]: 献立結果
        """
        # RAG検索を実行（3ベクトルDB対応）
        categorized_results = await self.rag_client.search_recipes_by_category(
            ingredients=inventory_items,
            menu_type=menu_type,
            excluded_recipes=excluded_recipes,
            limit=10  # 多めに取得して献立構成に使用
        )
        
        # RAG検索結果を献立形式に変換（3ベクトルDB対応）
        menu_result = await self.rag_client.convert_categorized_results_to_menu_format(
            categorized_results=categorized_results,
            inventory_items=inventory_items,
            menu_type=menu_type
        )
        
        # 選択されたレシピのURL情報を取得して保持
        selected_menu = menu_result.get("selected", {})
        url_map = {}  # タイトルをキーとしてURLを保持
        
        # categorized_resultsから選択されたレシピのURLを取得
        category_mapping = {
            "main_dish": "main",
            "side_dish": "sub",
            "soup": "soup"
        }
        
        for category_key, category_value in category_mapping.items():
            selected_title = selected_menu.get(category_key, {}).get("title", "")
            if selected_title:
                # categorized_resultsから該当するレシピを検索
                recipes = categorized_results.get(category_value, [])
                for recipe in recipes:
                    if recipe.get("title") == selected_title:
                        url = recipe.get("url", "")
                        if url:
                            url_map[selected_title] = {
                                "url": url,
                                "category_detail": recipe.get("category_detail", ""),
                                "category": recipe.get("category", "")
                            }
                            break
        
        # RAG検索結果をMenuResultに変換
        menu_result_model = self._format_rag_menu_result(menu_result, inventory_items)
        
        # URL情報を結果に含める（executor.pyで使用するため）
        result_data = menu_result_model.to_dict()
        result_data["_rag_urls"] = url_map  # 内部使用のため_プレフィックス
        
        return {
            "success": True,
            "data": result_data
        }

