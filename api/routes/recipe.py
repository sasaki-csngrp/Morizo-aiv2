#!/usr/bin/env python3
"""
API層 - レシピルート

レシピ採用通知と履歴管理のエンドポイント
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List
from datetime import datetime
import json
from config.loggers import GenericLogger
from ..models import RecipeAdoptionRequest, RecipeAdoptionResponse, SavedRecipe, IngredientDeleteCandidatesResponse, IngredientDeleteCandidate, IngredientDeleteRequest, IngredientDeleteResponse
from mcp_servers.recipe_history_crud import RecipeHistoryCRUD
from mcp_servers.utils import get_authenticated_client
from mcp_servers.inventory_crud import InventoryCRUD
from services.session.models.components.ingredient_mapper import IngredientMapperComponent

router = APIRouter()
logger = GenericLogger("api", "recipe")


@router.post("/recipe/adopt", response_model=RecipeAdoptionResponse)
async def adopt_recipe(request: RecipeAdoptionRequest, http_request: Request):
    """レシピ採用通知エンドポイント（複数対応）"""
    try:
        logger.info(f"🔍 [API] Recipe adoption request received:")
        logger.info(f"  Number of recipes: {len(request.recipes)}")
        
        for i, recipe in enumerate(request.recipes):
            logger.info(f"  Recipe {i+1}: {recipe.title} ({recipe.category}, {recipe.menu_source})")
        
        # 1. 認証トークンの取得（ヘッダーまたはリクエストボディ）
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        # リクエストボディのトークンを優先
        if request.token:
            token = request.token
            
        logger.debug(f"🔍 [API] Token: {'SET' if token else 'NOT SET'}")
        
        # 2. ユーザー情報の取得（ミドルウェアから）
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
            
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 3. menu_source → source のマッピング変換
        db_source_mapping = {
            "llm_menu": "web",   # LLM推論で生成したメニューはWeb検索でレシピ取得
            "rag_menu": "rag",   # RAG検索で生成したメニュー
            "manual": "manual"   # 将来の手動検索用
        }
        
        # 4. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 5. 各レシピを順次保存
        crud = RecipeHistoryCRUD()
        saved_recipes = []
        failed_recipes = []
        
        for i, recipe in enumerate(request.recipes):
            try:
                logger.debug(f"🔍 [API] Processing recipe {i+1}/{len(request.recipes)}: {recipe.title}")
                
                # デバッグログ: フロントエンドから送信されたレシピデータの内容を確認
                ingredients = recipe.ingredients if recipe.ingredients else None
                has_ingredients = recipe.ingredients is not None and len(recipe.ingredients) > 0 if recipe.ingredients else False
                logger.debug(f"🔍 [API] Recipe data from frontend ({i+1}): title='{recipe.title}', category='{recipe.category}', menu_source='{recipe.menu_source}', has_ingredients={has_ingredients}, ingredients={ingredients}")
                
                # menu_source → source のマッピング
                db_source = db_source_mapping.get(recipe.menu_source)
                if not db_source:
                    logger.error(f"❌ [API] Invalid menu_source for recipe {i+1}: {recipe.menu_source}")
                    failed_recipes.append(f"Recipe {i+1}: Invalid menu_source '{recipe.menu_source}'")
                    continue
                
                logger.debug(f"🔍 [API] Mapped source for recipe {i+1}: {recipe.menu_source} → {db_source}")
                
                # RecipeHistoryCRUD.add_history()を呼び出し
                if has_ingredients:
                    logger.debug(f"✅ [API] Saving recipe {i+1} with {len(recipe.ingredients)} ingredients: {recipe.ingredients}")
                else:
                    logger.warning(f"⚠️ [API] Saving recipe {i+1} without ingredients (ingredients={ingredients})")
                
                result = await crud.add_history(
                    client=client,
                    user_id=user_id,
                    title=recipe.title,
                    source=db_source,
                    url=recipe.url,
                    ingredients=ingredients  # 新規追加
                )
                
                if result.get("success"):
                    history_id = result.get("data", {}).get("id")
                    logger.info(f"✅ [API] Recipe {i+1} saved successfully: {history_id}")
                    
                    saved_recipes.append(SavedRecipe(
                        title=recipe.title,
                        category=recipe.category,
                        history_id=history_id
                    ))
                else:
                    error_msg = result.get("error", "不明なエラー")
                    logger.error(f"❌ [API] Failed to save recipe {i+1}: {error_msg}")
                    failed_recipes.append(f"Recipe {i+1}: {error_msg}")
                    
            except Exception as e:
                logger.error(f"❌ [API] Error processing recipe {i+1}: {e}")
                failed_recipes.append(f"Recipe {i+1}: {str(e)}")
        
        # 6. レスポンスの生成
        total_recipes = len(request.recipes)
        saved_count = len(saved_recipes)
        failed_count = len(failed_recipes)
        
        if saved_count == total_recipes:
            # すべて成功
            message = f"{saved_count}つのレシピが履歴に保存されました"
            success = True
        elif saved_count > 0:
            # 一部成功
            message = f"{saved_count}つのレシピが保存されました（{failed_count}つ失敗）"
            success = True
        else:
            # すべて失敗
            message = f"すべてのレシピの保存に失敗しました"
            success = False
        
        logger.info(f"🔍 [API] Final result: {saved_count}/{total_recipes} recipes saved")
        
        return RecipeAdoptionResponse(
            success=success,
            message=message,
            saved_recipes=saved_recipes,
            total_saved=saved_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in adopt_recipe: {e}")
        raise HTTPException(status_code=500, detail="レシピ採用処理でエラーが発生しました")

@router.get("/recipe/ingredients/delete-candidates/{date}", response_model=IngredientDeleteCandidatesResponse)
async def get_ingredient_delete_candidates(
    date: str,  # YYYY-MM-DD形式
    http_request: Request
):
    """指定日付のレシピから利用食材の削除候補を取得"""
    try:
        logger.info(f"🔍 [API] Ingredient delete candidates request received: date={date}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. 日付の検証と変換
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            start_datetime = datetime.combine(date_obj, datetime.min.time())
            end_datetime = datetime.combine(date_obj, datetime.max.time())
        except ValueError:
            logger.error(f"❌ [API] Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="日付の形式が不正です（YYYY-MM-DD形式で指定してください）")
        
        # 4. 指定日付のレシピ履歴を取得（削除未済みのみ）
        crud = RecipeHistoryCRUD()
        result = client.table("recipe_historys")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("cooked_at", start_datetime.isoformat())\
            .lte("cooked_at", end_datetime.isoformat())\
            .or_("ingredients_deleted.is.null,ingredients_deleted.eq.false")\
            .execute()
        
        logger.debug(f"🔍 [API] Retrieved {len(result.data)} recipe histories for date: {date}")
        
        # 5. 各レシピのingredientsを集約（重複除去）
        all_ingredients = []
        for recipe in result.data:
            ingredients = recipe.get("ingredients")
            if ingredients:
                if isinstance(ingredients, list):
                    all_ingredients.extend(ingredients)
                elif isinstance(ingredients, str):
                    # JSON文字列の場合
                    try:
                        ingredients_list = json.loads(ingredients)
                        if isinstance(ingredients_list, list):
                            all_ingredients.extend(ingredients_list)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ [API] Failed to parse ingredients JSON: {ingredients}")
        
        # 重複除去（順序を保持）
        unique_ingredients = list(dict.fromkeys(all_ingredients))
        logger.debug(f"🔍 [API] Aggregated {len(unique_ingredients)} unique ingredients")
        logger.debug(f"🔍 [API] Unique ingredients list: {unique_ingredients}")
        
        # 6. 在庫一覧を取得
        inventory_crud = InventoryCRUD()
        inventory_result = await inventory_crud.get_all_items(client, user_id)
        
        if not inventory_result.get("success"):
            logger.error(f"❌ [API] Failed to get inventory list: {inventory_result.get('error')}")
            raise HTTPException(status_code=500, detail="在庫情報の取得に失敗しました")
        
        inventory_items = inventory_result.get("data", [])
        logger.debug(f"🔍 [API] Retrieved {len(inventory_items)} inventory items")
        
        # 7. 食材名でマッチングして削除候補リストを作成
        # 食材名の正規化用（既存のIngredientMapperComponentを活用）
        ingredient_mapper = IngredientMapperComponent(GenericLogger("api", "ingredient_mapper"))
        
        candidates = []
        matched_inventory_ids = set()  # 重複防止用
        
        # 在庫名を正規化してインデックスを作成（ループ外で一度だけ作成）
        inventory_normalized = {}
        for inv_item in inventory_items:
            normalized = ingredient_mapper.normalize_ingredient_name(inv_item.get("item_name", ""))
            if normalized not in inventory_normalized:
                inventory_normalized[normalized] = []
            inventory_normalized[normalized].append(inv_item)
        
        # デバッグログ: 在庫名の正規化結果を確認
        for normalized_name, items in inventory_normalized.items():
            if len(items) > 1:
                logger.debug(f"🔍 [API] Multiple inventory items for normalized name '{normalized_name}': {len(items)} items")
                for item in items:
                    logger.debug(f"  - ID: {item.get('id')}, Name: {item.get('item_name')}, Quantity: {item.get('quantity')}")
        
        # レシピ食材を在庫名にマッピング
        for ingredient_name in unique_ingredients:
            normalized_ingredient = ingredient_mapper.normalize_ingredient_name(ingredient_name)
            logger.debug(f"🔍 [API] Processing ingredient '{ingredient_name}' (normalized: '{normalized_ingredient}')")
            
            matched = False
            # 正規化された在庫名インデックスから検索
            if normalized_ingredient in inventory_normalized:
                # 完全一致の場合：同じ食材名のすべての在庫レコードを候補に追加
                matched_items = inventory_normalized[normalized_ingredient]
                logger.debug(f"🔍 [API] Found {len(matched_items)} inventory items for ingredient '{ingredient_name}' (normalized: '{normalized_ingredient}')")
                for inv_item in matched_items:
                    inv_id = inv_item.get("id")
                    if inv_id not in matched_inventory_ids:
                        candidates.append(IngredientDeleteCandidate(
                            inventory_id=inv_id,
                            item_name=inv_item.get("item_name", ""),
                            current_quantity=float(inv_item.get("quantity", 0)),
                            unit=inv_item.get("unit", "個")
                        ))
                        matched_inventory_ids.add(inv_id)
                        matched = True
                        logger.debug(f"✅ [API] Added candidate: {inv_item.get('item_name')} (ID: {inv_id}, Quantity: {inv_item.get('quantity')})")
                    else:
                        logger.debug(f"⚠️ [API] Skipped duplicate inventory ID: {inv_id} for ingredient '{ingredient_name}'")
            else:
                # 部分一致をチェック（正規化された在庫名とレシピ食材名の部分一致）
                # まず、末尾の英数字を除去した正規化名でマッチングを試みる
                import re
                # 末尾の英数字を除去（例：「卵l」→「卵」）
                ingredient_base = re.sub(r'[a-z0-9]+$', '', normalized_ingredient)
                if ingredient_base and ingredient_base != normalized_ingredient:
                    logger.debug(f"🔍 [API] Trying base match for '{ingredient_name}': base='{ingredient_base}' (original normalized='{normalized_ingredient}')")
                    if ingredient_base in inventory_normalized:
                        # ベース名で完全一致した場合：すべての在庫レコードを候補に追加
                        matched_items = inventory_normalized[ingredient_base]
                        logger.debug(f"🔍 [API] Found {len(matched_items)} inventory items for ingredient base '{ingredient_base}'")
                        for inv_item in matched_items:
                            inv_id = inv_item.get("id")
                            if inv_id not in matched_inventory_ids:
                                candidates.append(IngredientDeleteCandidate(
                                    inventory_id=inv_id,
                                    item_name=inv_item.get("item_name", ""),
                                    current_quantity=float(inv_item.get("quantity", 0)),
                                    unit=inv_item.get("unit", "個")
                                ))
                                matched_inventory_ids.add(inv_id)
                                matched = True
                                logger.debug(f"✅ [API] Added candidate (base match): {inv_item.get('item_name')} (ID: {inv_id}, Quantity: {inv_item.get('quantity')})")
                
                # ベース名でマッチしなかった場合、通常の部分一致をチェック
                if not matched:
                    for normalized_inv, inv_items in inventory_normalized.items():
                        if normalized_ingredient in normalized_inv or normalized_inv in normalized_ingredient:
                            # 部分一致の場合：最初にマッチした在庫レコードのみ候補に追加
                            for inv_item in inv_items:
                                inv_id = inv_item.get("id")
                                if inv_id not in matched_inventory_ids:
                                    candidates.append(IngredientDeleteCandidate(
                                        inventory_id=inv_id,
                                        item_name=inv_item.get("item_name", ""),
                                        current_quantity=float(inv_item.get("quantity", 0)),
                                        unit=inv_item.get("unit", "個")
                                    ))
                                    matched_inventory_ids.add(inv_id)
                                    matched = True
                                    logger.debug(f"✅ [API] Added candidate (partial match): {inv_item.get('item_name')} (ID: {inv_id}, Quantity: {inv_item.get('quantity')})")
                                    break  # 部分一致が見つかったら次の食材へ
                            break  # 部分一致が見つかったら次の食材へ
            
            if not matched:
                logger.debug(f"⚠️ [API] Ingredient '{ingredient_name}' not found in inventory")
        
        logger.debug(f"✅ [API] Created {len(candidates)} delete candidates")
        
        return IngredientDeleteCandidatesResponse(
            success=True,
            date=date,
            candidates=candidates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in get_ingredient_delete_candidates: {e}")
        raise HTTPException(status_code=500, detail="削除候補の取得処理でエラーが発生しました")


@router.post("/recipe/ingredients/delete", response_model=IngredientDeleteResponse)
async def delete_ingredients(
    request: IngredientDeleteRequest,
    http_request: Request
):
    """指定された食材を在庫から削除（数量を0に設定）"""
    try:
        logger.debug(f"🔍 [API] Ingredient delete request received: date={request.date}, ingredients={len(request.ingredients)}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        logger.debug(f"🔍 [API] User ID: {user_id}")
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. 在庫一覧を取得
        inventory_crud = InventoryCRUD()
        inventory_result = await inventory_crud.get_all_items(client, user_id)
        
        if not inventory_result.get("success"):
            logger.error(f"❌ [API] Failed to get inventory list: {inventory_result.get('error')}")
            raise HTTPException(status_code=500, detail="在庫情報の取得に失敗しました")
        
        inventory_items = inventory_result.get("data", [])
        logger.debug(f"🔍 [API] Retrieved {len(inventory_items)} inventory items")
        
        # 4. 食材名の正規化用
        ingredient_mapper = IngredientMapperComponent(GenericLogger("api", "ingredient_mapper"))
        
        # 5. リクエストの食材名で在庫を検索して更新
        deleted_count = 0
        updated_count = 0
        failed_items = []
        
        for ingredient_item in request.ingredients:
            try:
                item_name = ingredient_item.item_name
                target_quantity = ingredient_item.quantity
                inventory_id = ingredient_item.inventory_id
                
                # 在庫IDが指定されている場合は直接更新または削除
                if inventory_id:
                    if target_quantity == 0:
                        # 削除の場合
                        result = await inventory_crud.delete_item_by_id(
                            client=client,
                            user_id=user_id,
                            item_id=inventory_id
                        )
                        
                        if result.get("success"):
                            deleted_count += 1
                            logger.debug(f"✅ [API] Deleted inventory item: {inventory_id}")
                        else:
                            failed_items.append(f"{item_name} (ID: {inventory_id})")
                            logger.error(f"❌ [API] Failed to delete inventory item: {inventory_id}")
                    else:
                        # 数量更新の場合
                        result = await inventory_crud.update_item_by_id(
                            client=client,
                            user_id=user_id,
                            item_id=inventory_id,
                            quantity=target_quantity
                        )
                        
                        if result.get("success"):
                            updated_count += 1
                            logger.debug(f"✅ [API] Updated inventory item: {inventory_id}, quantity={target_quantity}")
                        else:
                            failed_items.append(f"{item_name} (ID: {inventory_id})")
                            logger.error(f"❌ [API] Failed to update inventory item: {inventory_id}")
                else:
                    # 食材名で検索（複数在庫がある場合はすべて更新）
                    matched_items = []
                    normalized_item_name = ingredient_mapper.normalize_ingredient_name(item_name)
                    
                    for inv_item in inventory_items:
                        normalized_inv = ingredient_mapper.normalize_ingredient_name(inv_item.get("item_name", ""))
                        if normalized_item_name == normalized_inv or \
                           normalized_item_name in normalized_inv or \
                           normalized_inv in normalized_item_name:
                            matched_items.append(inv_item)
                    
                    if not matched_items:
                        failed_items.append(f"{item_name} (在庫に存在しません)")
                        logger.warning(f"⚠️ [API] Inventory item not found: {item_name}")
                        continue
                    
                    # すべてのマッチした在庫を更新または削除
                    for inv_item in matched_items:
                        inv_id = inv_item.get("id")
                        if target_quantity == 0:
                            # 削除の場合
                            result = await inventory_crud.delete_item_by_id(
                                client=client,
                                user_id=user_id,
                                item_id=inv_id
                            )
                            
                            if result.get("success"):
                                deleted_count += 1
                                logger.info(f"✅ [API] Deleted inventory item: {inv_id}")
                            else:
                                failed_items.append(f"{item_name} (ID: {inv_id})")
                                logger.error(f"❌ [API] Failed to delete inventory item: {inv_id}")
                        else:
                            # 数量更新の場合
                            result = await inventory_crud.update_item_by_id(
                                client=client,
                                user_id=user_id,
                                item_id=inv_id,
                                quantity=target_quantity
                            )
                            
                            if result.get("success"):
                                updated_count += 1
                                logger.info(f"✅ [API] Updated inventory item: {inv_id}, quantity={target_quantity}")
                            else:
                                failed_items.append(f"{item_name} (ID: {inv_id})")
                                logger.error(f"❌ [API] Failed to update inventory item: {inv_id}")
                            
            except Exception as e:
                failed_items.append(f"{ingredient_item.item_name} (エラー: {str(e)})")
                logger.error(f"❌ [API] Error processing ingredient: {ingredient_item.item_name}, error: {e}")
        
        # 6. レシピ履歴のingredients_deletedフラグを更新
        crud = RecipeHistoryCRUD()
        update_result = await crud.update_ingredients_deleted(
            client=client,
            user_id=user_id,
            date=request.date,
            deleted=True
        )
        
        if not update_result.get("success"):
            logger.warning(f"⚠️ [API] Failed to update ingredients_deleted flag: {update_result.get('error')}")
        
        logger.debug(f"✅ [API] Ingredient delete completed: deleted={deleted_count}, updated={updated_count}, failed={len(failed_items)}")
        
        return IngredientDeleteResponse(
            success=True,
            deleted_count=deleted_count,
            updated_count=updated_count,
            failed_items=failed_items
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in delete_ingredients: {e}")
        raise HTTPException(status_code=500, detail="食材削除処理でエラーが発生しました")
