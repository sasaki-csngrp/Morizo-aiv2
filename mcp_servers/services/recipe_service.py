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
        num_results: int
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
        
        Returns:
            Dict[str, Any]: 検索結果
        """
        # RAG検索結果からURLを取得（既に取得済みの場合）
        if rag_results and title in rag_results:
            rag_result = rag_results[title]
            rag_url = rag_result.get('url', '')
            if rag_url:
                self.logger.debug(f"🔍 [RECIPE] Found URL from RAG search for '{title}': {rag_url}")
                web_search_result = WebSearchResult(
                    title=title,
                    url=rag_url,
                    source="vector_db",
                    description=rag_result.get('category_detail', ''),
                    site="cookpad.com" if "cookpad.com" in rag_url else "other"
                )
                return {
                    "success": True,
                    "data": [web_search_result.to_dict()],
                    "title": title,
                    "count": 1
                }
        
        # URLがない場合のみWeb検索APIを呼び出す
        effective_source = menu_source
        if menu_source == "mixed":
            total_count = len(recipe_titles)
            if index < total_count / 2:
                effective_source = "llm"
                self.logger.debug(f"🔍 [RECIPE] Index {index} < {total_count}/2, treating as LLM proposal")
            else:
                effective_source = "rag"
                self.logger.debug(f"🔍 [RECIPE] Index {index} >= {total_count}/2, treating as RAG proposal")
        
        self.logger.debug(f"🔍 [RECIPE] Getting search client for menu_source='{menu_source}' (effective: '{effective_source}')")
        client = get_search_client(menu_source=effective_source)
        client_type = type(client).__name__
        self.logger.debug(f"🔍 [RECIPE] Using search client: {client_type}")
        recipes = await client.search_recipes(title, num_results)
        self.logger.debug(f"🔍 [RECIPE] Web search completed")
        self.logger.debug(f"📊 [RECIPE] Title: '{title}', found {len(recipes)} recipes")
        
        # レシピを優先順位でソート
        prioritized_recipes = prioritize_recipes(recipes)
        self.logger.debug(f"📊 [RECIPE] Recipes prioritized for '{title}'")
        
        # 結果をフィルタリング
        filtered_recipes = filter_recipe_results(prioritized_recipes)
        self.logger.debug(f"📊 [RECIPE] Recipes filtered for '{title}', final count: {len(filtered_recipes)}")
        
        # WebSearchResultに変換
        web_search_results = []
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
        self.logger.debug(f"🔐 [RECIPE] Client type: {type(client).__name__ if client else 'None'}")
        
        # Phase 3A: セッション内の提案済みレシピは、呼び出し元でexcluded_recipesとして渡されるため
        # MCPサーバー内では追加処理は不要（プロセス分離のため）
        self.logger.debug(f"📊 [RECIPE] Step 2: Processing excluded recipes")
        all_excluded = (excluded_recipes or []).copy()
        self.logger.debug(f"📊 [RECIPE] Total excluded: {len(all_excluded)} recipes")
        if all_excluded:
            self.logger.debug(f"📊 [RECIPE] Excluded recipe titles (first 5): {all_excluded[:5]}")
        
        # otherカテゴリの場合はused_ingredientsを使用しない（単体動作のため）
        self.logger.debug(f"📊 [RECIPE] Step 3: Processing category-specific logic")
        if category == "other":
            self.logger.debug(f"📊 [RECIPE] Category is 'other', setting used_ingredients to None")
            used_ingredients = None
        else:
            self.logger.debug(f"📊 [RECIPE] Category is '{category}', keeping used_ingredients: {used_ingredients}")
        
        # LLMとRAGを並列実行（汎用メソッドを使用）
        self.logger.debug(f"📊 [RECIPE] Step 4: Creating LLM and RAG tasks")
        self.logger.debug(f"📊 [RECIPE] LLM task parameters:")
        self.logger.debug(f"  - inventory_items: {inventory_items}")
        self.logger.debug(f"  - menu_type: {menu_type}")
        self.logger.debug(f"  - category: {category}")
        self.logger.debug(f"  - main_ingredient: {main_ingredient}")
        self.logger.debug(f"  - used_ingredients: {used_ingredients}")
        self.logger.debug(f"  - excluded_recipes count: {len(all_excluded)}")
        self.logger.debug(f"  - count: 2")
        self.logger.debug(f"  - category_detail_keyword: {category_detail_keyword}")
        
        self.logger.debug(f"📊 [RECIPE] RAG task parameters:")
        self.logger.debug(f"  - ingredients: {inventory_items}")
        self.logger.debug(f"  - menu_type: {menu_type}")
        self.logger.debug(f"  - category: {category}")
        self.logger.debug(f"  - main_ingredient: {main_ingredient}")
        self.logger.debug(f"  - used_ingredients: {used_ingredients}")
        self.logger.debug(f"  - excluded_recipes count: {len(all_excluded)}")
        self.logger.debug(f"  - limit: 3")
        self.logger.debug(f"  - category_detail_keyword: {category_detail_keyword}")
        
        try:
            self.logger.debug(f"📊 [RECIPE] Creating LLM task...")
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
            self.logger.debug(f"✅ [RECIPE] LLM task created successfully (type: {type(llm_task).__name__})")
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] Failed to create LLM task: {e}")
            self.logger.error(f"❌ [RECIPE] LLM task creation error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] LLM task creation traceback: {traceback.format_exc()}")
            raise
        
        try:
            self.logger.debug(f"📊 [RECIPE] Creating RAG task...")
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
            self.logger.debug(f"✅ [RECIPE] RAG task created successfully (type: {type(rag_task).__name__})")
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] Failed to create RAG task: {e}")
            self.logger.error(f"❌ [RECIPE] RAG task creation error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] RAG task creation traceback: {traceback.format_exc()}")
            raise
        
        # 両方の結果を待つ（並列実行）
        self.logger.debug(f"📊 [RECIPE] Step 5: Executing asyncio.gather for LLM and RAG tasks")
        self.logger.debug(f"📊 [RECIPE] LLM task type: {type(llm_task).__name__}")
        self.logger.debug(f"📊 [RECIPE] RAG task type: {type(rag_task).__name__}")
        
        try:
            self.logger.debug(f"📊 [RECIPE] Awaiting asyncio.gather...")
            llm_result, rag_result = await asyncio.gather(llm_task, rag_task)
            self.logger.debug(f"✅ [RECIPE] asyncio.gather completed successfully")
            self.logger.debug(f"📊 [RECIPE] LLM result type: {type(llm_result).__name__}")
            self.logger.debug(f"📊 [RECIPE] RAG result type: {type(rag_result).__name__}")
        except Exception as e:
            self.logger.error(f"❌ [RECIPE] asyncio.gather failed: {e}")
            self.logger.error(f"❌ [RECIPE] asyncio.gather error type: {type(e).__name__}")
            self.logger.error(f"❌ [RECIPE] asyncio.gather traceback: {traceback.format_exc()}")
            raise
        
        # 統合（sourceフィールドを追加）
        self.logger.debug(f"📊 [RECIPE] Step 6: Processing and integrating results")
        self.logger.debug(f"📊 [RECIPE] LLM result structure:")
        self.logger.debug(f"  - Type: {type(llm_result).__name__}")
        self.logger.debug(f"  - Keys: {list(llm_result.keys()) if isinstance(llm_result, dict) else 'N/A'}")
        self.logger.debug(f"  - Success: {llm_result.get('success') if isinstance(llm_result, dict) else 'N/A'}")
        if isinstance(llm_result, dict) and llm_result.get("success"):
            llm_data = llm_result.get("data", {})
            self.logger.debug(f"  - Data keys: {list(llm_data.keys()) if isinstance(llm_data, dict) else 'N/A'}")
            llm_candidates_list = llm_data.get("candidates", [])
            self.logger.debug(f"  - Candidates count: {len(llm_candidates_list)}")
            self.logger.debug(f"  - Candidates type: {type(llm_candidates_list).__name__}")
        
        self.logger.debug(f"📊 [RECIPE] RAG result structure:")
        self.logger.debug(f"  - Type: {type(rag_result).__name__}")
        if isinstance(rag_result, list):
            self.logger.debug(f"  - List length: {len(rag_result)}")
            if rag_result:
                self.logger.debug(f"  - First item keys: {list(rag_result[0].keys()) if isinstance(rag_result[0], dict) else 'N/A'}")
        elif isinstance(rag_result, dict):
            self.logger.debug(f"  - Dict keys: {list(rag_result.keys())}")
        
        recipe_proposals = []
        
        # LLM結果の処理
        self.logger.debug(f"📊 [RECIPE] Processing LLM results...")
        if llm_result.get("success"):
            try:
                llm_candidates = llm_result["data"]["candidates"]
                self.logger.debug(f"📊 [RECIPE] LLM candidates extracted: {len(llm_candidates)} items")
                # LLM候補をRecipeProposalに変換
                for i, candidate in enumerate(llm_candidates):
                    proposal = RecipeProposal(
                        title=candidate.get("title", ""),
                        ingredients=candidate.get("ingredients", []),
                        source="llm",
                        url=candidate.get("url"),
                        description=candidate.get("description")
                    )
                    recipe_proposals.append(proposal)
                    self.logger.debug(f"📊 [RECIPE] LLM candidate {i+1}: title='{proposal.title}', source='{proposal.source}'")
                self.logger.debug(f"✅ [RECIPE] Added {len(llm_candidates)} LLM candidates")
            except Exception as e:
                self.logger.error(f"❌ [RECIPE] Error processing LLM results: {e}")
                self.logger.error(f"❌ [RECIPE] LLM result processing error type: {type(e).__name__}")
                self.logger.error(f"❌ [RECIPE] LLM result processing traceback: {traceback.format_exc()}")
        else:
            self.logger.warning(f"⚠️ [RECIPE] LLM result indicates failure: {llm_result.get('error', 'Unknown error')}")
        
        # RAG結果の処理
        self.logger.debug(f"📊 [RECIPE] Processing RAG results...")
        if rag_result:
            try:
                self.logger.debug(f"📊 [RECIPE] RAG result is truthy, processing...")
                # RAG候補をRecipeProposalに変換
                for i, r in enumerate(rag_result):
                    self.logger.debug(f"📊 [RECIPE] Processing RAG result {i+1}: type={type(r).__name__}, keys={list(r.keys()) if isinstance(r, dict) else 'N/A'}")
                    proposal = RecipeProposal(
                        title=r.get("title", ""),
                        ingredients=r.get("ingredients", []),
                        source="rag",
                        url=r.get("url"),
                        description=r.get("description")
                    )
                    recipe_proposals.append(proposal)
                    self.logger.debug(f"📊 [RECIPE] RAG candidate {i+1}: title='{proposal.title}', source='{proposal.source}', has_url={bool(proposal.url)}")
                self.logger.debug(f"✅ [RECIPE] Added {len(rag_result)} RAG candidates")
            except Exception as e:
                self.logger.error(f"❌ [RECIPE] Error processing RAG results: {e}")
                self.logger.error(f"❌ [RECIPE] RAG result processing error type: {type(e).__name__}")
                self.logger.error(f"❌ [RECIPE] RAG result processing traceback: {traceback.format_exc()}")
        else:
            self.logger.warning(f"⚠️ [RECIPE] RAG result is empty or falsy")
        
        # デバッグログ: 各候補のsourceを確認
        self.logger.debug(f"📊 [RECIPE] Final candidates summary:")
        self.logger.debug(f"  - Total candidates: {len(recipe_proposals)}")
        for i, proposal in enumerate(recipe_proposals):
            self.logger.debug(f"🔍 [RECIPE] Candidate {i+1}: title='{proposal.title}', source='{proposal.source}', has_url={bool(proposal.url)}")
        
        # RecipeProposalを辞書に変換
        candidates = [proposal.to_dict() for proposal in recipe_proposals]
        
        self.logger.info(f"✅ [RECIPE] generate_proposals completed")
        llm_count = len(llm_result.get('data', {}).get('candidates', [])) if llm_result.get('success') else 0
        rag_count = len(rag_result) if rag_result else 0
        self.logger.debug(f"📊 [RECIPE] Final counts - Total: {len(candidates)}, LLM: {llm_count}, RAG: {rag_count}")
        
        self.logger.debug(f"📊 [RECIPE] Step 7: Building return value")
        return_value = {
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
        self.logger.debug(f"📊 [RECIPE] Return value structure:")
        self.logger.debug(f"  - success: {return_value['success']}")
        self.logger.debug(f"  - data keys: {list(return_value['data'].keys())}")
        self.logger.debug(f"  - candidates count: {len(return_value['data']['candidates'])}")
        return return_value
    
    async def search_recipes_from_web(
        self,
        recipe_titles: List[str],
        num_results: int = 5,
        menu_categories: List[str] = None,
        menu_source: str = "mixed",
        rag_results: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Web検索によるレシピ検索
        
        Args:
            recipe_titles: 検索するレシピタイトルのリスト
            num_results: 各料理名あたりの取得結果数
            menu_categories: 料理名の分類リスト
            menu_source: 検索元（llm, rag, mixed）
            rag_results: RAG検索結果の辞書
        
        Returns:
            Dict[str, Any]: 分類された検索結果
        """
        self.logger.debug(f"🔍 [RECIPE] Titles count: {len(recipe_titles)}, titles: {recipe_titles}, num_results: {num_results}")
        self.logger.debug(f"📊 [RECIPE] Menu categories: {menu_categories}, source: {menu_source}")
        
        async def search_single_recipe(title: str, index: int) -> Dict[str, Any]:
            """単一の料理名でレシピ検索（RAG検索結果のURLを優先）"""
            try:
                return await self._search_single_recipe_with_rag_fallback(
                    title=title,
                    index=index,
                    rag_results=rag_results,
                    menu_source=menu_source,
                    recipe_titles=recipe_titles,
                    num_results=num_results
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
                self.logger.debug(f"✅ [RECIPE] Found recipes")
                self.logger.debug(f"📊 [RECIPE] Found {len(recipes)} recipes for '{recipe_titles[i]}'")
                # 単一カテゴリ提案の場合は、各レシピタイトルに対応する最初のレシピを取得
                # （候補リストの順序と一致させるため）
                if is_single_category:
                    if recipes:
                        single_category_recipes.append(recipes[0])
            else:
                self.logger.error(f"❌ [RECIPE] Search failed for '{recipe_titles[i]}': {result.get('error')}")
        
        self.logger.debug(f"📊 [RECIPE] Successful searches: {successful_searches}/{len(recipe_titles)}")
        
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
        
        self.logger.debug(f"📊 [RECIPE] Web search result: {result}")
        
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
        
        self.logger.debug(f"📊 [RECIPE] Main: {len(categorized_results.get('main', []))} recipes")
        self.logger.debug(f"📊 [RECIPE] Sub: {len(categorized_results.get('sub', []))} recipes")
        self.logger.debug(f"📊 [RECIPE] Soup: {len(categorized_results.get('soup', []))} recipes")
        
        # RAG検索結果を献立形式に変換（3ベクトルDB対応）
        menu_result = await self.rag_client.convert_categorized_results_to_menu_format(
            categorized_results=categorized_results,
            inventory_items=inventory_items,
            menu_type=menu_type
        )
        
        self.logger.debug(f"📊 [RECIPE] RAG menu result: {menu_result}")
        
        # RAG検索結果をMenuResultに変換
        menu_result_model = self._format_rag_menu_result(menu_result, inventory_items)
        
        return {
            "success": True,
            "data": menu_result_model.to_dict()
        }

