#!/usr/bin/env python3
"""
API層 - 献立ルート

献立保存のエンドポイント
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from config.loggers import GenericLogger
from ..models import MenuSaveRequest, MenuSaveResponse, SavedMenuRecipe, MenuHistoryResponse, HistoryRecipe, HistoryEntry, RecipeRatingUpdateRequest
from mcp_servers.recipe_history_crud import RecipeHistoryCRUD
from mcp_servers.utils import get_authenticated_client
from services.session.service import session_service

router = APIRouter()
logger = GenericLogger("api", "menu")


@router.post("/menu/save", response_model=MenuSaveResponse)
async def save_menu(request: MenuSaveRequest, http_request: Request):
    """献立をDBに保存するエンドポイント"""
    try:
        logger.debug(f"🔍 [API] Menu save request received: sse_session_id={request.sse_session_id}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] リクエストステートにユーザー情報が見つかりません")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 選択済みレシピを取得（フロントエンドから直接送信された場合は優先）
        if request.recipes:
            # フロントエンドから直接送信されたレシピ情報を使用
            selected_recipes = request.recipes
            logger.debug(f"🔍 [API] Using recipes from request: main={selected_recipes.get('main') is not None}, sub={selected_recipes.get('sub') is not None}, soup={selected_recipes.get('soup') is not None}, other={selected_recipes.get('other') is not None}")
            # デバッグログ: フロントエンドから送信されたレシピデータの内容を確認
            for category in ["main", "sub", "soup", "other"]:
                recipe = selected_recipes.get(category)
                if recipe:
                    ingredients = recipe.get("ingredients", [])
                    has_ingredients = "ingredients" in recipe and ingredients
                    logger.debug(f"🔍 [API] Recipe data from frontend ({category}): title='{recipe.get('title', 'N/A')}', source='{recipe.get('source', 'N/A')}', has_ingredients={has_ingredients}, ingredients={ingredients}")
                else:
                    logger.debug(f"🔍 [API] Recipe data from frontend ({category}): None")
        elif request.sse_session_id:
            # セッションIDから選択済みレシピを取得（後方互換性）
            selected_recipes = await session_service.get_selected_recipes(request.sse_session_id)
            logger.debug(f"🔍 [API] Using recipes from session: main={selected_recipes.get('main') is not None}, sub={selected_recipes.get('sub') is not None}, soup={selected_recipes.get('soup') is not None}, other={selected_recipes.get('other') is not None}")
        else:
            # どちらも指定されていない場合はエラー
            logger.warning(f"⚠️ [API] Neither recipes nor sse_session_id provided")
            return MenuSaveResponse(
                success=False,
                message="レシピ情報またはセッションIDが必要です",
                saved_recipes=[],
                total_saved=0
            )
        
        # 選択済みレシピがない、またはすべてNoneの場合
        if not selected_recipes or all(recipe is None for recipe in selected_recipes.values()):
            logger.warning(f"⚠️ [API] No selected recipes found")
            return MenuSaveResponse(
                success=False,
                message="保存するレシピがありません",
                saved_recipes=[],
                total_saved=0
            )
        
        # 選択済みレシピのログ出力
        logger.debug(f"🔍 [API] Selected recipes to save:")
        for category in ["main", "sub", "soup", "other"]:
            recipe = selected_recipes.get(category)
            if recipe:
                logger.debug(f"  {category}: {recipe.get('title', 'N/A')} (source: {recipe.get('source', 'N/A')})")
            else:
                logger.debug(f"  {category}: None")
        
        # 3. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] ユーザー {user_id} の認証済みクライアントを作成しました")
        except Exception as e:
            logger.error(f"❌ [API] 認証済みクライアントの作成に失敗しました: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 4. 各レシピをDBに保存
        crud = RecipeHistoryCRUD()
        saved_recipes = []
        failed_count = 0
        
        category_prefix_map = {
            "main": "主菜: ",
            "sub": "副菜: ",
            "soup": "汁物: ",
            "other": "その他: "
        }
        
        source_mapping = {
            "llm": "web",
            "rag": "rag",
            "web": "web"
        }
        
        for category in ["main", "sub", "soup", "other"]:
            recipe = selected_recipes.get(category)
            if not recipe:
                continue  # 未選択のレシピはスキップ
            
            try:
                # タイトルにプレフィックスを追加
                original_title = recipe.get("title", "")
                prefixed_title = f"{category_prefix_map[category]}{original_title}"
                
                # source のマッピング
                recipe_source = recipe.get("source", "web")
                db_source = source_mapping.get(recipe_source, "web")
                
                # URLの取得
                url = recipe.get("url")
                
                # ingredientsを取得
                ingredients = recipe.get("ingredients", [])
                has_ingredients = "ingredients" in recipe and ingredients
                if not ingredients:
                    ingredients = None  # 空リストの場合はNoneに
                
                if has_ingredients:
                    logger.debug(f"✅ [API] Saving {category}: title='{prefixed_title}', source={recipe_source}→{db_source}, ingredients={recipe.get('ingredients', [])} ({len(recipe.get('ingredients', []))} items)")
                else:
                    logger.warning(f"⚠️ [API] Saving {category}: title='{prefixed_title}', source={recipe_source}→{db_source}, ingredients missing or empty (ingredients={ingredients})")
                
                # DBに保存
                result = await crud.add_history(
                    client=client,
                    user_id=user_id,
                    title=prefixed_title,
                    source=db_source,
                    url=url,
                    ingredients=ingredients
                )
                
                if result.get("success"):
                    history_id = result.get("data", {}).get("id")
                    logger.info(f"✅ [API] {category} saved successfully: history_id={history_id}")
                    saved_recipes.append(SavedMenuRecipe(
                        category=category,
                        title=prefixed_title,
                        history_id=history_id
                    ))
                else:
                    failed_count += 1
                    error_msg = result.get("error", "不明なエラー")
                    logger.error(f"❌ [API] {category} の保存に失敗しました: {error_msg}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ [API] Error saving {category}: {e}")
        
        # 5. レスポンスの生成
        total_saved = len(saved_recipes)
        if total_saved == 0:
            message = "レシピの保存に失敗しました"
            success = False
        elif failed_count > 0:
            message = f"{total_saved}つのレシピが保存されました（{failed_count}つ失敗）"
            success = True
        else:
            message = f"{total_saved}つのレシピが履歴に保存されました"
            success = True
        
        logger.info(f"🔍 [API] Final result: {total_saved} recipes saved, {failed_count} failed")
        
        return MenuSaveResponse(
            success=success,
            message=message,
            saved_recipes=saved_recipes,
            total_saved=total_saved
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 献立保存処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="献立保存処理でエラーが発生しました")


@router.get("/menu/history", response_model=MenuHistoryResponse)
async def get_menu_history(
    days: Optional[int] = 14,
    category: Optional[str] = None,
    http_request: Request = None
):
    """献立履歴を取得するエンドポイント"""
    try:
        logger.debug(f"🔍 [API] Menu history request received: days={days}, category={category}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] リクエストステートにユーザー情報が見つかりません")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] ユーザー {user_id} の認証済みクライアントを作成しました")
        except Exception as e:
            logger.error(f"❌ [API] 認証済みクライアントの作成に失敗しました: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. 履歴を取得
        # days=0の場合は30日以前のレシピのみを取得
        query = client.table("recipe_historys")\
            .select("*")\
            .eq("user_id", user_id)
        
        if days is not None and days > 0:
            # 指定日数以降のレシピを取得
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.gte("cooked_at", cutoff_date.isoformat())
        elif days == 0:
            # それ以前: 30日以前のレシピのみを取得（30日未満は除外）
            cutoff_date = datetime.now() - timedelta(days=30)
            query = query.lt("cooked_at", cutoff_date.isoformat())
        
        result = query.order("cooked_at", desc=True).execute()
        
        logger.debug(f"🔍 [API] データベースから {len(result.data)} 件のレシピ履歴を取得しました")
        
        # 4. 日付ごとにグループ化
        history_by_date = {}
        ingredients_deleted_by_date = {}  # 日付ごとのingredients_deletedフラグ
        category_prefix_map = {
            "main": "主菜: ",
            "sub": "副菜: ",
            "soup": "汁物: "
        }
        
        for item in result.data:
            # cooked_atから日付を取得
            cooked_at_str = item.get("cooked_at")
            if not cooked_at_str:
                logger.warning(f"⚠️ [API] Missing cooked_at for history_id={item.get('id')}")
                continue
            
            try:
                # ISO形式の日時文字列をパース
                if "Z" in cooked_at_str:
                    cooked_at = datetime.fromisoformat(cooked_at_str.replace("Z", "+00:00"))
                else:
                    cooked_at = datetime.fromisoformat(cooked_at_str)
                
                # タイムゾーン情報を削除して日付のみ取得
                if cooked_at.tzinfo:
                    cooked_at = cooked_at.replace(tzinfo=None)
                
                date_key = cooked_at.date().isoformat()
            except Exception as e:
                logger.error(f"❌ [API] cooked_at の解析に失敗しました: {cooked_at_str}, エラー: {e}")
                continue
            
            if date_key not in history_by_date:
                history_by_date[date_key] = []
                ingredients_deleted_by_date[date_key] = []
            
            # ingredients_deletedフラグを収集
            ingredients_deleted = item.get("ingredients_deleted", False)
            ingredients_deleted_by_date[date_key].append(ingredients_deleted)
            
            # カテゴリを判定（タイトルのプレフィックスから）
            title = item.get("title", "")
            recipe_category = None
            for cat, prefix in category_prefix_map.items():
                if title.startswith(prefix):
                    recipe_category = cat
                    break
            
            # カテゴリフィルター適用
            if category and recipe_category != category:
                continue
            
            # 画像URLを生成
            from mcp_servers.recipe_web_utils import build_recipe_image_url
            image_url = build_recipe_image_url(item.get("url"))
            
            history_by_date[date_key].append(HistoryRecipe(
                category=recipe_category,
                title=title,
                source=item.get("source", "web"),
                url=item.get("url"),
                history_id=item.get("id"),
                rating=item.get("rating"),
                notes=item.get("notes"),
                image_url=image_url
            ))
        
        # 5. 日付ごとのingredients_deletedフラグを判定（その日のすべてのレシピがTrueの場合のみTrue）
        ingredients_deleted_flags = {}
        for date_key, flags in ingredients_deleted_by_date.items():
            # その日のすべてのレシピがingredients_deleted=Trueの場合のみTrue
            ingredients_deleted_flags[date_key] = all(flags) if flags else False
        
        # 6. 日付順にソート（最新順）
        sorted_history = sorted(
            [
                HistoryEntry(
                    date=date,
                    recipes=recipes,
                    ingredients_deleted=ingredients_deleted_flags.get(date, False)
                )
                for date, recipes in history_by_date.items()
            ],
            key=lambda x: x.date,
            reverse=True
        )
        
        logger.debug(f"✅ [API] Returning {len(sorted_history)} date entries with total {sum(len(entry.recipes) for entry in sorted_history)} recipes")
        
        # 7. レスポンスを生成
        return MenuHistoryResponse(
            success=True,
            data=sorted_history
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 履歴取得処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="履歴取得処理でエラーが発生しました")


@router.put("/menu/history/{history_id}/rating")
async def update_recipe_rating(
    history_id: str,
    request: RecipeRatingUpdateRequest,
    http_request: Request = None
):
    """レシピ履歴の評価・コメントを更新するエンドポイント"""
    try:
        logger.debug(f"🔍 [API] Recipe rating update request received: history_id={history_id}")
        logger.debug(f"🔍 [API] Request body - rating: {request.rating}, notes: {repr(request.notes)}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] リクエストステートにユーザー情報が見つかりません")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] ユーザー {user_id} の認証済みクライアントを作成しました")
        except Exception as e:
            logger.error(f"❌ [API] 認証済みクライアントの作成に失敗しました: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. 空文字列をNoneに変換
        notes_value = request.notes
        logger.debug(f"🔍 [API] Original notes value: {repr(notes_value)}")
        if notes_value is not None and notes_value.strip() == "":
            notes_value = None
            logger.debug(f"🔍 [API] Converted empty string to None")
        logger.debug(f"🔍 [API] Final notes value to send to CRUD: {repr(notes_value)}")
        
        # 4. CRUD層で評価・コメントを更新
        crud = RecipeHistoryCRUD()
        result = await crud.update_history_by_id(
            client=client,
            user_id=user_id,
            history_id=history_id,
            rating=request.rating,
            notes=notes_value
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ [API] レシピ評価の更新に失敗しました: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        # 4. 更新後のデータを取得
        updated_data = result.get("data", {})
        
        # 5. 画像URLを生成
        from mcp_servers.recipe_web_utils import build_recipe_image_url
        image_url = build_recipe_image_url(updated_data.get("url"))
        
        # 6. レスポンスを生成
        response_data = HistoryRecipe(
            category=None,  # カテゴリは履歴取得時のみ設定
            title=updated_data.get("title", ""),
            source=updated_data.get("source", "web"),
            url=updated_data.get("url"),
            history_id=updated_data.get("id"),
            rating=updated_data.get("rating"),
            notes=updated_data.get("notes"),
            image_url=image_url
        )
        
        logger.info(f"✅ [API] Recipe rating updated successfully: history_id={history_id}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 評価更新処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="評価更新処理でエラーが発生しました")


@router.delete("/menu/history/{history_id}")
async def delete_recipe_history(
    history_id: str,
    http_request: Request = None
):
    """レシピ履歴を削除するエンドポイント"""
    try:
        logger.debug(f"🔍 [API] Recipe history delete request received: history_id={history_id}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] リクエストステートにユーザー情報が見つかりません")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] ユーザー {user_id} の認証済みクライアントを作成しました")
        except Exception as e:
            logger.error(f"❌ [API] 認証済みクライアントの作成に失敗しました: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. CRUD層で削除
        crud = RecipeHistoryCRUD()
        result = await crud.delete_history_by_id(
            client=client,
            user_id=user_id,
            history_id=history_id
        )
        
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ [API] レシピ履歴の削除に失敗しました: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        logger.info(f"✅ [API] Recipe history deleted successfully: history_id={history_id}")
        return {"success": True, "message": "レシピ履歴を削除しました"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 履歴削除処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="履歴削除処理でエラーが発生しました")

