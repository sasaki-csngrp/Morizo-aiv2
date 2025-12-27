#!/usr/bin/env python3
"""
ServiceHandlers - サービス別レスポンス処理ハンドラー

在庫サービス、レシピサービス、汎用サービスのレスポンス処理を担当
"""

from typing import Dict, Any, List, Optional
from config.loggers import GenericLogger


class InventoryServiceHandler:
    """在庫サービス処理ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.inventory_handler")
    
    async def handle(self, service_method: str, data: Any, is_menu_scenario: bool, sse_session_id: Optional[str] = None, formatters = None, session_service = None) -> tuple[List[str], Optional[Dict[str, Any]]]:
        """
        在庫サービス関連の処理
        
        Args:
            service_method: サービス・メソッド名
            data: 処理データ
            is_menu_scenario: 献立提案シナリオかどうか
            sse_session_id: SSEセッションID
            formatters: ResponseFormattersインスタンス
            session_service: セッションサービスインスタンス
        
        Returns:
            (レスポンスパーツリスト, JSON形式のレシピデータ)
        """
        response_parts = []
        
        try:
            if service_method == "inventory_service.get_inventory":
                response_parts.extend(formatters.format_inventory_list(data, is_menu_scenario))
                
                # Phase 1F: 在庫情報をセッションに保存（追加提案時の再利用用）
                if data.get("success") and sse_session_id and session_service:
                    inventory_items = data.get("data", [])
                    item_names = [item.get("item_name") for item in inventory_items if item.get("item_name")]
                    
                    await session_service.set_session_context(sse_session_id, "inventory_items", item_names)
                    self.logger.debug(f"💾 [InventoryServiceHandler] セッションに{len(item_names)}件の在庫アイテムを保存しました")
                
            elif service_method == "inventory_service.add_inventory":
                response_parts.extend(formatters.format_inventory_add(data))
                
            elif service_method == "inventory_service.update_inventory":
                response_parts.extend(formatters.format_inventory_update(data))
                
            elif service_method == "inventory_service.delete_inventory":
                response_parts.extend(formatters.format_inventory_delete(data))
        
        except Exception as e:
            self.logger.error(f"❌ [InventoryServiceHandler] 在庫サービス{service_method}の処理でエラー: {e}")
            response_parts.append(f"データの処理中にエラーが発生しました: {str(e)}")
        
        return response_parts, None


class RecipeServiceHandler:
    """レシピサービス処理ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.recipe_handler")
    
    async def handle(self, service_method: str, data: Any, is_menu_scenario: bool, task_id: str, results: Optional[Dict[str, Any]] = None, sse_session_id: Optional[str] = None, formatters = None, menu_generator = None, session_service = None, stage_info_handler = None, web_integrator = None, utils = None) -> tuple[List[str], Optional[Dict[str, Any]]]:
        """
        レシピサービス関連の処理
        
        Args:
            service_method: サービス・メソッド名
            data: 処理データ
            is_menu_scenario: 献立提案シナリオかどうか
            task_id: タスクID
            results: 全タスクの実行結果
            sse_session_id: SSEセッションID
            formatters: ResponseFormattersインスタンス
            menu_generator: MenuDataGeneratorインスタンス
            session_service: セッションサービスインスタンス
            stage_info_handler: SessionInfoHandlerインスタンス
            web_integrator: WebSearchResultIntegratorインスタンス
            utils: ResponseProcessorUtilsインスタンス
        
        Returns:
            (レスポンスパーツリスト, JSON形式のレシピデータ)
        """
        response_parts = []
        menu_data = None
        
        try:
            if service_method == "recipe_service.generate_menu_plan":
                # LLM献立提案を表示（斬新な提案）
                try:
                    llm_menu = data.get("data", data)
                    if isinstance(llm_menu, dict):
                        response_parts.extend(formatters.format_llm_menu(llm_menu))
                except Exception as e:
                    self.logger.error(f"❌ [RecipeServiceHandler] LLMメニューの整形に失敗: {e}")
                
            elif service_method == "recipe_service.search_menu_from_rag":
                # RAG献立提案を表示（伝統的な提案）
                try:
                    rag_menu = data.get("data", data)
                    if isinstance(rag_menu, dict):
                        response_parts.extend(formatters.format_rag_menu(rag_menu))
                except Exception as e:
                    self.logger.error(f"❌ [RecipeServiceHandler] RAGメニューの整形に失敗: {e}")
                
            elif service_method == "recipe_service.search_recipes_from_web":
                # 献立一括提案の場合、task4とtask5の結果を統合する必要がある
                # task4が完了した時点では、まだtask5が完了していないため、統合処理は実行しない
                # task5が完了した時点で統合処理を実行する
                if is_menu_scenario and task_id == "task4":
                    # task4が完了した時点では、まだtask5が完了していないため、何も返さない
                    self.logger.debug(f"🔍 [RecipeServiceHandler] メニューシナリオでTask4が完了、Task5を待機中")
                    return [], None
                
                # task4完了時にtask3とtask4の結果を統合して選択UIを表示（段階的提案の場合）
                self.logger.debug(f"🔍 [RecipeServiceHandler] Task4が完了、Task3の結果と統合中")
                
                # resultsからtask3の結果を直接取得
                task3_result = None
                if results:
                    for task_key, task_data in results.items():
                        if task_key == "task3" and task_data.get("success"):
                            task3_result = task_data.get("result", {})
                            break
                
                if task3_result and task3_result.get("success") and task3_result.get("data", {}).get("candidates"):
                    candidates = task3_result["data"]["candidates"]
                    
                    # task3の結果からカテゴリを取得（main/sub/soup/other）
                    task3_data = task3_result.get("data", {})
                    category = task3_data.get("category", "main")
                    
                    # task4のWeb検索結果を統合
                    candidates_with_urls = web_integrator.integrate(candidates, task_id, data, utils)
                    
                    # Phase 1F: 提案済みタイトルをセッションに保存
                    if sse_session_id and session_service:
                        titles = [c.get("title") for c in candidates_with_urls if c.get("title")]
                        
                        await session_service.add_proposed_recipes(sse_session_id, category, titles)
                        self.logger.debug(f"💾 [RecipeServiceHandler] セッションに{len(titles)}件の提案タイトルを保存しました (category: {category})")
                    
                    # Phase 3C-3: 候補情報をセッションに保存（詳細情報）
                    if sse_session_id and session_service:
                        session = await session_service.get_session(sse_session_id, user_id=None)
                        if session:
                            # task3の結果から取得したcategoryを使用（main/sub/soup/other）
                            await session_service.set_candidates(sse_session_id, category, candidates_with_urls)
                            # otherカテゴリの場合はcurrent_stageを"other"に設定
                            if category == "other":
                                session.set_current_stage("other")
                                self.logger.debug(f"✅ [RecipeServiceHandler] otherカテゴリ提案のためcurrent_stageを'other'に設定")
                            # デバッグログ: 保存する候補のsourceとingredientsを確認
                            for i, candidate in enumerate(candidates_with_urls):
                                ingredients = candidate.get('ingredients', [])
                                has_ingredients = 'ingredients' in candidate and ingredients
                                if has_ingredients:
                                    self.logger.debug(f"✅ [RecipeServiceHandler] 候補{i+1}を保存中: title='{candidate.get('title', 'N/A')}', source='{candidate.get('source', 'N/A')}', ingredients={ingredients} ({len(ingredients)}件)")
                                else:
                                    self.logger.warning(f"⚠️ [RecipeServiceHandler] 候補{i+1}を保存中: title='{candidate.get('title', 'N/A')}', source='{candidate.get('source', 'N/A')}', ingredientsが欠落または空 (ingredients={ingredients})")
                            self.logger.debug(f"💾 [RecipeServiceHandler] セッションに{len(candidates_with_urls)}件の{category}候補を保存しました")
                    
                    # Phase 3D: セッションから段階情報を取得
                    stage_info = await stage_info_handler.get_stage_info(sse_session_id, session_service)
                    
                    # 選択UI用のデータを返す
                    return [], {
                        "requires_selection": True,
                        "candidates": candidates_with_urls,
                        "task_id": task_id,
                        "message": "以下の5件から選択してください:",
                        **stage_info  # Phase 3D: 段階情報を統合
                    }
                else:
                    # task3の結果が取得できない場合
                    # 献立提案ではtask3（候補生成）が無い構成もあるため、エラーにしない
                    if is_menu_scenario:
                        self.logger.info(f"ℹ️ [RecipeServiceHandler] Task3の結果が見つかりませんでした（メニューシナリオ）。重複テキストを避けるためメニューJSONのみ生成します。")
                        if results:
                            self.logger.debug(f"🔍 [RecipeServiceHandler] 結果内の利用可能なタスクキー: {list(results.keys())}")
                        
                        # task2とtask3の結果から各レシピごとの食材情報を取得
                        llm_ingredients_used = None
                        llm_main_dish_ingredients = None
                        llm_side_dish_ingredients = None
                        llm_soup_ingredients = None
                        
                        rag_ingredients_used = None
                        rag_main_dish_ingredients = None
                        rag_side_dish_ingredients = None
                        rag_soup_ingredients = None
                        
                        # task4とtask5の結果を統合（献立一括提案の場合）
                        integrated_web_data = None
                        if task_id == "task5":
                            # task5の場合、task4の結果と統合
                            task4_result = None
                            task5_result = data
                            
                            if results:
                                for task_key, task_data in results.items():
                                    if task_key == "task4" and task_data.get("success"):
                                        task4_result = task_data.get("result", {})
                                        break
                            
                            self.logger.debug(f"🔍 [RecipeServiceHandler] Task5が完了、Task4とTask5の結果を確認中")
                            self.logger.debug(f"🔍 [RecipeServiceHandler] Task4結果: {task4_result is not None}, Task5結果: {task5_result is not None}")
                            
                            if task4_result and task4_result.get("success") and task5_result and task5_result.get("success"):
                                # task4とtask5の結果を統合
                                task4_data = task4_result.get("data", {})
                                task5_data = task5_result.get("data", {})
                                
                                self.logger.debug(f"🔍 [RecipeServiceHandler] Task4データキー: {list(task4_data.keys()) if isinstance(task4_data, dict) else 'not dict'}")
                                self.logger.debug(f"🔍 [RecipeServiceHandler] Task5データキー: {list(task5_data.keys()) if isinstance(task5_data, dict) else 'not dict'}")
                                
                                # task4の結果からllm_menuを取得（menu_source="llm"なのでllm_menuのみ）
                                task4_llm_menu = task4_data.get("llm_menu", {})
                                if not task4_llm_menu:
                                    # llm_menuが直接ない場合、data全体がllm_menuの可能性
                                    if "main_dish" in task4_data or "side_dish" in task4_data or "soup" in task4_data:
                                        # 単一カテゴリ提案の形式の場合
                                        task4_llm_menu = {
                                            "main_dish": task4_data.get("main_dish", {"title": "", "recipes": []}),
                                            "side_dish": task4_data.get("side_dish", {"title": "", "recipes": []}),
                                            "soup": task4_data.get("soup", {"title": "", "recipes": []})
                                        }
                                
                                # task5の結果からrag_menuを取得（menu_source="rag"なのでrag_menuのみ）
                                task5_rag_menu = task5_data.get("rag_menu", {})
                                if not task5_rag_menu:
                                    # rag_menuが直接ない場合、data全体がrag_menuの可能性
                                    if "main_dish" in task5_data or "side_dish" in task5_data or "soup" in task5_data:
                                        # 単一カテゴリ提案の形式の場合
                                        task5_rag_menu = {
                                            "main_dish": task5_data.get("main_dish", {"title": "", "recipes": []}),
                                            "side_dish": task5_data.get("side_dish", {"title": "", "recipes": []}),
                                            "soup": task5_data.get("soup", {"title": "", "recipes": []})
                                        }
                                
                                # llm_menuとrag_menuを統合
                                integrated_web_data = {
                                    "success": True,
                                    "data": {
                                        "llm_menu": task4_llm_menu if task4_llm_menu else {
                                            "main_dish": {"title": "", "recipes": []},
                                            "side_dish": {"title": "", "recipes": []},
                                            "soup": {"title": "", "recipes": []}
                                        },
                                        "rag_menu": task5_rag_menu if task5_rag_menu else {
                                            "main_dish": {"title": "", "recipes": []},
                                            "side_dish": {"title": "", "recipes": []},
                                            "soup": {"title": "", "recipes": []}
                                        }
                                    }
                                }
                                self.logger.debug(f"✅ [RecipeServiceHandler] メニューシナリオでTask4とTask5の結果を統合しました")
                                self.logger.debug(f"🔍 [RecipeServiceHandler] LLMメニュー主菜レシピ: {len(integrated_web_data['data']['llm_menu'].get('main_dish', {}).get('recipes', []))}件")
                                self.logger.debug(f"🔍 [RecipeServiceHandler] RAGメニュー主菜レシピ: {len(integrated_web_data['data']['rag_menu'].get('main_dish', {}).get('recipes', []))}件")
                            else:
                                self.logger.warning(f"⚠️ [RecipeServiceHandler] Task4またはTask5の結果が成功していません、統合できません")
                                if not task4_result:
                                    self.logger.warning(f"⚠️ [RecipeServiceHandler] Task4の結果が見つかりませんでした")
                                if not task5_result:
                                    self.logger.warning(f"⚠️ [RecipeServiceHandler] Task5の結果が見つかりませんでした")
                        
                        if results:
                            for task_key, task_data in results.items():
                                if task_key == "task2" and task_data.get("success"):
                                    task2_result = task_data.get("result", {})
                                    if task2_result.get("success"):
                                        task2_data = task2_result.get("data", {})
                                        llm_ingredients_used = task2_data.get("ingredients_used", [])
                                        llm_main_dish_ingredients = task2_data.get("main_dish_ingredients", [])
                                        llm_side_dish_ingredients = task2_data.get("side_dish_ingredients", [])
                                        llm_soup_ingredients = task2_data.get("soup_ingredients", [])
                                        if llm_ingredients_used or llm_main_dish_ingredients or llm_side_dish_ingredients or llm_soup_ingredients:
                                            self.logger.debug(f"✅ [RecipeServiceHandler] Task2 (LLM)から食材を発見:")
                                            self.logger.debug(f"   - ingredients_used: {llm_ingredients_used}")
                                            self.logger.debug(f"   - main_dish_ingredients: {llm_main_dish_ingredients}")
                                            self.logger.debug(f"   - side_dish_ingredients: {llm_side_dish_ingredients}")
                                            self.logger.debug(f"   - soup_ingredients: {llm_soup_ingredients}")
                                
                                elif task_key == "task3" and task_data.get("success"):
                                    task3_result = task_data.get("result", {})
                                    if task3_result.get("success"):
                                        task3_data = task3_result.get("data", {})
                                        rag_ingredients_used = task3_data.get("ingredients_used", [])
                                        rag_main_dish_ingredients = task3_data.get("main_dish_ingredients", [])
                                        rag_side_dish_ingredients = task3_data.get("side_dish_ingredients", [])
                                        rag_soup_ingredients = task3_data.get("soup_ingredients", [])
                                        if rag_ingredients_used or rag_main_dish_ingredients or rag_side_dish_ingredients or rag_soup_ingredients:
                                            self.logger.debug(f"✅ [RecipeServiceHandler] Task3 (RAG)から食材を発見:")
                                            self.logger.debug(f"   - ingredients_used: {rag_ingredients_used}")
                                            self.logger.debug(f"   - main_dish_ingredients: {rag_main_dish_ingredients}")
                                            self.logger.debug(f"   - side_dish_ingredients: {rag_side_dish_ingredients}")
                                            self.logger.debug(f"   - soup_ingredients: {rag_soup_ingredients}")
                        
                        # 統合されたWebデータを使用（task5の場合）または元のデータを使用（task4の場合）
                        web_data_for_json = integrated_web_data if integrated_web_data else data
                        
                        # 献立提案ではテキスト重複を避けるため、Web整形テキストは追加しない
                        # （generate_menu_plan/search_menu_from_rag で既に表示済み）
                        menu_data = menu_generator.generate_menu_data_json(
                            web_data_for_json, 
                            ingredients_used=llm_ingredients_used,
                            main_dish_ingredients=llm_main_dish_ingredients,
                            side_dish_ingredients=llm_side_dish_ingredients,
                            soup_ingredients=llm_soup_ingredients,
                            rag_ingredients_used=rag_ingredients_used,
                            rag_main_dish_ingredients=rag_main_dish_ingredients,
                            rag_side_dish_ingredients=rag_side_dish_ingredients,
                            rag_soup_ingredients=rag_soup_ingredients
                        )
                    else:
                        # デバッグ: results辞書の内容を確認
                        self.logger.error(f"❌ [RecipeServiceHandler] Task3の結果が見つかりませんでした")
                        self.logger.debug(f"🔍 [RecipeServiceHandler] 結果内の利用可能なタスクキー: {list(results.keys()) if results else 'results is None or empty'}")
                        if results:
                            for task_key, task_data in results.items():
                                self.logger.debug(f"🔍 [RecipeServiceHandler] タスクキー: {task_key}, success: {task_data.get('success')}, has result: {'result' in task_data}")
                                if task_key == "task3":
                                    task_data_result = task_data.get("result", {})
                                    self.logger.debug(f"🔍 [RecipeServiceHandler] Task3結果構造: success={task_data_result.get('success')}, has_data={'data' in task_data_result}, data_keys={list(task_data_result.get('data', {}).keys()) if isinstance(task_data_result.get('data'), dict) else 'data is not dict'}")
                        # 副菜・汁物提案では致命的
                        self.logger.error(f"❌ [RecipeServiceHandler] 致命的: カテゴリ提案でTask3の結果が見つかりませんでした")
                        response_parts.append("レシピ提案の結果を取得できませんでした。")
                
            elif service_method == "recipe_service.generate_proposals":
                # task3完了時は進捗のみ（選択UIは表示しない）
                # task4完了後に統合処理を行う
                self.logger.debug(f"🔍 [RecipeServiceHandler] Task3が完了、Task4の統合を待機中")
                
                # Phase 1F: 提案済みタイトルをセッションに保存
                if data.get("success") and sse_session_id and session_service:
                    data_obj = data.get("data", {})
                    candidates = data_obj.get("candidates", [])
                    titles = [c.get("title") for c in candidates if c.get("title")]
                    
                    # カテゴリを取得（main/sub/soup）。デフォルトは"main"
                    category = data_obj.get("category", "main")
                    
                    await session_service.add_proposed_recipes(sse_session_id, category, titles)
                    self.logger.debug(f"💾 [RecipeServiceHandler] セッションに{len(titles)}件の提案タイトルを保存しました (category: {category})")
                
                # 何も返さない（進捗状態のみ）
                pass
        
        except Exception as e:
            self.logger.error(f"❌ [RecipeServiceHandler] タスク{task_id}のレシピサービス{service_method}の処理でエラー: {e}")
            response_parts.append(f"データの処理中にエラーが発生しました: {str(e)}")
        
        return response_parts, menu_data


class GenericServiceHandler:
    """汎用サービス処理ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.generic_handler")
    
    def handle(self, service_method: str, data: Any, formatters = None) -> tuple[List[str], Optional[Dict[str, Any]]]:
        """
        汎用サービス処理
        
        Args:
            service_method: サービス・メソッド名
            data: 処理データ
            formatters: ResponseFormattersインスタンス
        
        Returns:
            (レスポンスパーツリスト, JSON形式のレシピデータ)
        """
        response_parts = formatters.format_generic_result(service_method, data)
        return response_parts, None

