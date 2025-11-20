"""
SelectionHandler: Handles user selection processing.

This handler manages:
- User selection required notifications
- Processing user selections
- Handling additional proposal requests
"""

from typing import Optional, Dict, Any, Callable
from ..models import TaskChainManager
from services.session_service import SessionService
from config.loggers import GenericLogger
from .stage_manager import StageManager


class SelectionHandler:
    """Handles user selection processing."""
    
    def __init__(
        self,
        session_service: SessionService,
        process_request_callback: Callable = None,
        stage_manager: Optional[StageManager] = None,
    ):
        self.logger = GenericLogger("core", "selection_handler")
        self.session_service = session_service
        self.process_request_callback = process_request_callback
        self.stage_manager = stage_manager
    
    async def handle_user_selection_required(
        self,
        candidates: list,
        context: dict,
        task_chain_manager: TaskChainManager
    ) -> dict:
        """ユーザー選択が必要な場合の処理"""
        try:
            # タスクIDを取得
            task_id = context.get('current_task_id')
            if not task_id:
                raise ValueError("No task ID found in context")
            
            # タスクを一時停止
            pause_result = task_chain_manager.pause_task_for_user_selection(task_id, context)
            
            if not pause_result["success"]:
                raise Exception(f"Failed to pause task: {pause_result['error']}")
            
            self.logger.info(f"⏸️ [SELECTION] Task {task_id} paused for user selection")
            
            # フロントエンドに選択要求を送信
            response = {
                "success": True,
                "requires_selection": True,
                "candidates": candidates,
                "task_id": task_id,
                "message": "以下の5件から選択してください:"
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"❌ [SELECTION] Failed to handle user selection required: {e}")
            return {
                "success": False,
                "error": str(e),
                "requires_selection": False
            }
    
    async def process_user_selection(
        self,
        task_id: str,
        selection: int,
        sse_session_id: str,
        user_id: str,
        token: str,
        old_sse_session_id: str = None
    ) -> dict:
        """ユーザー選択結果の処理（自動遷移機能付き）"""
        try:
            self.logger.info(f"📥 [SELECTION] Processing user selection: task_id={task_id}, selection={selection}")
            
            # Phase 1F: selection=0 の場合は追加提案要求
            if selection == 0:
                self.logger.info(f"🔄 [SELECTION] Additional proposal request detected (selection=0)")
                return await self.handle_additional_proposal_request(
                    task_id, sse_session_id, user_id, token, old_sse_session_id
                )
            
            # Phase 3C-2: 段階判定と進行処理
            # 現在の段階を取得（StageManager経由）
            if not self.stage_manager:
                raise ValueError("stage_manager not set")
            current_stage = await self.stage_manager.get_current_stage(sse_session_id, user_id)
            self.logger.debug(f"🔍 [SELECTION] Current stage: {current_stage}")
            
            # セッションを取得
            session = await self.session_service.get_session(sse_session_id, user_id)
            if not session:
                self.logger.error(f"❌ [SELECTION] Session not found: {sse_session_id}")
                return {"success": False, "error": "Session not found"}
            
            # 選択されたレシピ情報を取得（StageManager経由）
            selected_recipe = await self.stage_manager.get_selected_recipe_from_task(task_id, selection, sse_session_id)
            ingredients = selected_recipe.get('ingredients', [])
            has_ingredients = 'ingredients' in selected_recipe and ingredients
            self.logger.info(f"✅ [SELECTION] Selected recipe: {selected_recipe.get('title', 'Unknown')}")
            if has_ingredients:
                self.logger.debug(f"✅ [SELECTION] Selected recipe has {len(ingredients)} ingredients: {ingredients}")
            else:
                self.logger.warning(f"⚠️ [SELECTION] Selected recipe missing or empty 'ingredients' field (ingredients={ingredients})")
            
            # Phase 3C-3: 段階を進める（StageManager経由）
            next_stage = await self.stage_manager.advance_stage(sse_session_id, user_id, selected_recipe)
            self.logger.info(f"🔄 [SELECTION] Advanced to stage: {next_stage}")
            
            # 次の段階に応じた処理
            if next_stage == "sub":
                # 副菜提案のリクエストを生成（確認待ち状態）
                self.logger.debug(f"🔄 [SELECTION] Preparing sub dish proposal confirmation")
                next_request = await self.stage_manager.generate_sub_dish_request(
                    selected_recipe, sse_session_id, user_id
                )
                self.logger.debug(f"📝 [SELECTION] Generated sub dish request: {next_request}")
                
                # セッションに次の提案リクエストを保存（フロントエンドが読み取る）
                session.set_context("next_stage_request", next_request)
                self.logger.debug(f"💾 [SELECTION] Saved next stage request to session")
                
                # 確認待ちフラグを返してフロントエンドに確認を要求
                return {
                    "success": True,
                    "message": "主菜が確定しました。",
                    "requires_stage_confirmation": True,  # 新規追加
                    "requires_next_stage": True,  # 後方互換性のため維持
                    "next_stage_name": "sub",  # 新規追加
                    "confirmation_message": "主菜が確定しました。副菜の選択に進みますか？",  # 新規追加
                    "selected_recipe": {  # Phase 5B-2: 選択したレシピ情報を追加
                        "category": "main",
                        "recipe": selected_recipe
                    }
                }
            
            elif next_stage == "soup":
                # 汁物提案のリクエストを生成（確認待ち状態）
                self.logger.debug(f"🔄 [SELECTION] Preparing soup proposal confirmation")
                next_request = await self.stage_manager.generate_soup_request(
                    selected_recipe, sse_session_id, user_id
                )
                self.logger.debug(f"📝 [SELECTION] Generated soup request: {next_request}")
                
                # セッションに次の提案リクエストを保存（フロントエンドが読み取る）
                session.set_context("next_stage_request", next_request)
                self.logger.debug(f"💾 [SELECTION] Saved next stage request to session")
                
                # 確認待ちフラグを返してフロントエンドに確認を要求
                return {
                    "success": True,
                    "message": "副菜が確定しました。",
                    "requires_stage_confirmation": True,  # 新規追加
                    "requires_next_stage": True,  # 後方互換性のため維持
                    "next_stage_name": "soup",  # 新規追加
                    "confirmation_message": "副菜が確定しました。汁物の選択に進みますか？",  # 新規追加
                    "selected_recipe": {  # Phase 5B-2: 選択したレシピ情報を追加
                        "category": "sub",
                        "recipe": selected_recipe
                    }
                }
            
            elif next_stage == "completed":
                # 完了
                self.logger.info(f"✅ [SELECTION] All stages completed")
                
                # otherカテゴリの場合は単体動作として完了
                if current_stage == "other":
                    # Phase 5B-3: すべての選択済みレシピを集約して取得（親セッションからも）
                    all_selected_recipes = await self.stage_manager.get_selected_recipes(sse_session_id)
                    other_recipe = all_selected_recipes.get("other") or selected_recipe
                    self.logger.debug(f"🔍 [SELECTION] Other category recipe selected: {other_recipe.get('title', 'N/A') if other_recipe else 'N/A'}")
                    
                    return {
                        "success": True,
                        "message": "レシピが確定しました。",
                        "menu": {
                            "other": other_recipe
                        },
                        "selected_recipe": {
                            "category": "other",
                            "recipe": selected_recipe
                        }
                    }
                
                # 主菜・副菜・汁物の献立完成の場合
                # Phase 5B-3: すべての選択済みレシピを集約して取得（親セッションからも）
                all_selected_recipes = await self.stage_manager.get_selected_recipes(sse_session_id)
                self.logger.debug(f"🔍 [SELECTION] All selected recipes (aggregated): main={all_selected_recipes.get('main') is not None}, sub={all_selected_recipes.get('sub') is not None}, soup={all_selected_recipes.get('soup') is not None}")
                
                # 集約された結果を使用（現在選択したレシピで上書き）
                main_dish = all_selected_recipes.get("main")
                sub_dish = all_selected_recipes.get("sub")
                soup_dish = all_selected_recipes.get("soup") or selected_recipe  # 今選択したレシピが汁物の場合
                
                return {
                    "success": True,
                    "message": "献立が完成しました。",
                    "menu": {
                        "main": main_dish,
                        "sub": sub_dish,
                        "soup": soup_dish
                    },
                    "selected_recipe": {  # Phase 5B-2: 選択したレシピ情報を追加
                        "category": "soup",
                        "recipe": selected_recipe
                    }
                }
            
            # その他の場合（通常の選択処理）
            self.logger.info(f"✅ [SELECTION] Selection {selection} processed for stage {current_stage}")
            
            return {
                "success": True,
                "task_id": task_id,
                "selection": selection,
                "current_stage": current_stage,
                "message": f"選択肢 {selection} を受け付けました。",
                "selected_recipe": {  # Phase 5B-2: 選択したレシピ情報を追加
                    "category": current_stage,
                    "recipe": selected_recipe
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ [SELECTION] Failed to process user selection: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_additional_proposal_request(
        self,
        task_id: str,
        sse_session_id: str,
        user_id: str,
        token: str,
        old_sse_session_id: str = None
    ) -> dict:
        """追加提案要求の処理（selection=0の場合）
        
        Args:
            task_id: タスクID
            sse_session_id: 新しいSSEセッションID
            user_id: ユーザーID
            token: 認証トークン
            old_sse_session_id: 旧SSEセッションID（コンテキスト復元用）
        
        Returns:
            dict: 処理結果
        """
        try:
            self.logger.info(f"🔄 [SELECTION] Handling additional proposal request")
            self.logger.debug(f"🔍 [SELECTION] New SSE session ID: {sse_session_id}")
            self.logger.debug(f"🔍 [SELECTION] Old SSE session ID: {old_sse_session_id}")
            
            # 旧セッションからコンテキストを取得（コンテキスト復元）
            main_ingredient = None
            current_stage = None  # "main" | "sub" | "soup" | "other"
            inventory_items = None
            menu_type = None
            category_detail_keyword = None
            if old_sse_session_id:
                old_session = await self.session_service.get_session(old_sse_session_id, user_id)
                if old_session:
                    main_ingredient = old_session.get_context("main_ingredient")
                    inventory_items = old_session.get_context("inventory_items")
                    menu_type = old_session.get_context("menu_type")
                    category_detail_keyword = old_session.get_context("category_detail_keyword")
                    # 現在の段階（main/sub/soup/other）を取得
                    try:
                        current_stage = old_session.get_current_stage()
                    except Exception:
                        current_stage = None
                    
                    # 旧セッションから提案済みタイトルを取得（現在段階に合わせる）
                    # otherカテゴリの判定（category_detail_keywordがある場合もotherカテゴリとして判定）
                    other_proposed = old_session.get_proposed_recipes("other")
                    if other_proposed or category_detail_keyword:
                        stage_for_titles = "other"
                        # otherカテゴリの提案済みレシピを取得
                        proposed_titles = old_session.get_proposed_recipes("other")
                        self.logger.debug(f"🔍 [SELECTION] Detected other category from old session: category_detail_keyword={category_detail_keyword}, other_proposed count={len(proposed_titles)}")
                    else:
                        stage_for_titles = current_stage if current_stage in ["main", "sub", "soup"] else "main"
                        proposed_titles = old_session.get_proposed_recipes(stage_for_titles)
                    self.logger.debug(f"🔍 [SELECTION] Retrieved from old session: main_ingredient={main_ingredient}, current_stage={current_stage}, category_detail_keyword={category_detail_keyword}, proposed_titles[{stage_for_titles}] count={len(proposed_titles)}")
                    
                    # 新しいセッションにコンテキストをコピー
                    new_session = await self.session_service.get_session(sse_session_id, user_id)
                    if not new_session:
                        new_session = await self.session_service.create_session(user_id, sse_session_id)
                    
                    new_session.set_context("main_ingredient", main_ingredient)
                    new_session.set_context("inventory_items", inventory_items)
                    new_session.set_context("menu_type", menu_type)
                    if category_detail_keyword:
                        new_session.set_context("category_detail_keyword", category_detail_keyword)
                    # Phase 5B-3: 親セッションIDを保存（選択済みレシピの集約に使用）
                    new_session.set_context("parent_session_id", old_sse_session_id)
                    self.logger.debug(f"✅ [SELECTION] Saved parent_session_id={old_sse_session_id} to new session")

                    # 現在段階・使用済み食材・選択済みレシピを引き継ぐ
                    try:
                        if current_stage in ["main", "sub", "soup"]:
                            new_session.current_stage = current_stage
                            # 設定後の確認（デバッグ用）
                            actual_stage = new_session.get_current_stage()
                            self.logger.debug(f"✅ [SELECTION] Copied current_stage='{current_stage}' to new session (verified: '{actual_stage}')")
                            if actual_stage != current_stage:
                                self.logger.warning(f"⚠️ [SELECTION] current_stage mismatch: expected '{current_stage}', got '{actual_stage}'")
                    except Exception as e:
                        self.logger.error(f"❌ [SELECTION] Failed to copy current_stage: {e}")
                        pass
                    try:
                        # used_ingredients（主菜→副菜、などの除外に必要）
                        if hasattr(old_session, 'used_ingredients'):
                            new_session.used_ingredients = list(old_session.used_ingredients or [])
                            self.logger.debug(f"✅ [SELECTION] Copied used_ingredients count={len(new_session.used_ingredients)}")
                    except Exception:
                        pass
                    try:
                        # Phase 5B-3: 既に選択済みのレシピを新しいセッションに引き継ぐ
                        # StageManager経由で選択済みレシピを取得し、新しいセッションに設定
                        if self.stage_manager:
                            old_selected_recipes = await self.stage_manager.get_selected_recipes(old_sse_session_id)
                            self.logger.debug(f"🔍 [SELECTION] Retrieving selected recipes from old session: {old_selected_recipes}")
                            
                            # 各カテゴリの選択済みレシピを新しいセッションに設定
                            for category in ["main", "sub", "soup"]:
                                recipe = old_selected_recipes.get(category)
                                if recipe:
                                    await self.stage_manager.set_selected_recipe(sse_session_id, category, recipe)
                                    self.logger.debug(f"✅ [SELECTION] Copied selected {category} recipe to new session: {recipe.get('title', 'N/A')}")
                        else:
                            self.logger.warning(f"⚠️ [SELECTION] stage_manager not available, skipping selected recipes copy")
                    except Exception as e:
                        self.logger.warning(f"⚠️ [SELECTION] Failed to copy selected recipes: {e}")
                        pass
                    
                    # 提案済みタイトルも新しいセッションにコピー（カテゴリ別）
                    if proposed_titles:
                        new_session.add_proposed_recipes(stage_for_titles, proposed_titles)
                        self.logger.debug(f"✅ [SELECTION] Copied {len(proposed_titles)} proposed titles to new session under category '{stage_for_titles}'")
                    
                    self.logger.debug(f"✅ [SELECTION] Copied context from old session to new session")
            
            # 現在の段階が未取得なら新しいセッションから補完
            if not current_stage:
                session = await self.session_service.get_session(sse_session_id, user_id)
                if session:
                    try:
                        current_stage = session.get_current_stage()
                    except Exception:
                        current_stage = None
            
            # otherカテゴリの判定（提案済みレシピとcategory_detail_keywordから判断）
            is_other_category = False
            category_detail_keyword = None
            session = await self.session_service.get_session(sse_session_id, user_id)
            if session:
                # セッションコンテキストからcategory_detail_keywordを取得
                category_detail_keyword = session.get_context("category_detail_keyword")
                # otherカテゴリの提案済みレシピがあるか確認
                other_proposed = session.get_proposed_recipes("other")
                if other_proposed or category_detail_keyword:
                    is_other_category = True
                    self.logger.debug(f"🔍 [SELECTION] Detected other category: other_proposed count={len(other_proposed) if other_proposed else 0}, category_detail_keyword={category_detail_keyword}")
            
            # current_stageの判定（otherカテゴリの場合は"other"に設定）
            if is_other_category:
                current_stage = "other"
                self.logger.debug(f"🔍 [SELECTION] Set current_stage to 'other' based on category_detail_keyword or other_proposed")
            elif current_stage not in ["main", "sub", "soup"]:
                current_stage = "main"

            # 現在段階に応じた追加提案リクエスト文言を生成
            if current_stage == "main":
                # 主菜の追加提案（主要食材があれば付与）
                if not main_ingredient:
                    # 新しいセッションから取得を試みる
                    if session:
                        main_ingredient = session.get_context("main_ingredient")
                if main_ingredient:
                    additional_request = f"{main_ingredient}の主菜をもう5件提案して"
                else:
                    additional_request = "主菜をもう5件提案して"
            elif current_stage == "sub":
                # 副菜の追加提案（主菜で使っていない食材で副菜）
                # 使い回しのため在庫情報や使用済み食材はセッション側で利用される
                additional_request = "主菜で使っていない食材で副菜をもう5件提案して"
            elif current_stage == "soup":
                # 汁物の追加提案（和:味噌汁 / それ以外:スープ）
                menu_category = None
                if session:
                    try:
                        menu_category = session.get_menu_category()
                    except Exception:
                        menu_category = None
                soup_type = "味噌汁" if menu_category == "japanese" else "スープ"
                additional_request = f"{soup_type}をもう5件提案して"
            elif current_stage == "other":
                # otherカテゴリの追加提案
                if category_detail_keyword:
                    # category_detail_keywordに基づいて適切なリクエストを生成
                    if "麺もの" in category_detail_keyword or "麺" in category_detail_keyword:
                        additional_request = "麺もののレシピをもう5件提案して"
                    elif "パスタ" in category_detail_keyword:
                        additional_request = "パスタのレシピをもう5件提案して"
                    elif "丼" in category_detail_keyword or "ご飯もの" in category_detail_keyword:
                        additional_request = "ご飯もののレシピをもう5件提案して"
                    else:
                        additional_request = f"{category_detail_keyword}のレシピをもう5件提案して"
                else:
                    additional_request = "その他のレシピをもう5件提案して"
            else:
                # フォールバック
                additional_request = "主菜をもう5件提案して"
            
            self.logger.debug(f"📝 [SELECTION] Final additional request: {additional_request}")
            
            # プランニングループを実行
            # 重要: 追加提案の場合は、新しいSSEセッションID（additional-*で始まる）を使用
            # これにより、新しいSSE接続が確立され、通常のタスク進捗（進捗バー等）がフロントエンドに表示される
            self.logger.debug(f"🔄 [SELECTION] Processing additional proposal with SSE session: {sse_session_id}")
            
            if not self.process_request_callback:
                raise ValueError("process_request_callback not set")
            
            result = await self.process_request_callback(
                additional_request,
                user_id,
                token,
                sse_session_id,  # 新しいSSEセッションID（フロントエンドから渡される）
                is_confirmation_response=False
            )
            
            # Phase 1F: 追加提案の場合、SSE経由でメッセージが送信されるため、
            # ここで返す値はフロントエンドに表示されない（既にSSE経由で送信済み）
            # しかし、APIの返却値を調整
            if isinstance(result, dict):
                # SSE経由で送信済みのメッセージは不要なため空の辞書を返す
                result["success"] = True
                return result
            else:
                # 辞書以外の場合は辞書形式に変換
                return {
                    "success": True,
                    "response": str(result)
                }
            
        except Exception as e:
            self.logger.error(f"❌ [SELECTION] Failed to handle additional proposal request: {e}")
            return {
                "success": False,
                "error": str(e)
            }

