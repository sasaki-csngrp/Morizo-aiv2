"""
Morizo AI v2 - Recipe History CRUD Operations

This module provides basic CRUD operations for recipe history management.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from supabase import Client

from config.loggers import GenericLogger


class RecipeHistoryCRUD:
    """レシピ履歴管理の基本CRUD操作"""
    
    def __init__(self):
        self.logger = GenericLogger("mcp", "recipe_history_crud", initialize_logging=False)
    
    async def add_history(
        self, 
        client: Client, 
        user_id: str, 
        title: str, 
        source: str,
        url: Optional[str] = None,
        ingredients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """レシピ履歴を1件追加"""
        try:
            self.logger.info(f"📝 [CRUD] Adding recipe history")
            self.logger.debug(f"🔍 [CRUD] Title: {title}")
            
            # データ準備
            data = {
                "user_id": user_id,
                "title": title,
                "source": source
            }
            
            if url:
                data["url"] = url
            
            # ingredientsをJSONB形式で保存
            if ingredients:
                data["ingredients"] = ingredients
            
            # データベースに挿入
            result = client.table("recipe_historys").insert(data).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] Recipe history added successfully")
                self.logger.debug(f"🔍 [CRUD] History ID: {result.data[0]['id']}")
                return {"success": True, "data": result.data[0]}
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to add recipe history: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_histories(self, client: Client, user_id: str) -> Dict[str, Any]:
        """ユーザーの全レシピ履歴を取得"""
        try:
            self.logger.info(f"📋 [CRUD] Getting all recipe histories")
            self.logger.debug(f"🔍 [CRUD] User ID: {user_id}")
            
            result = client.table("recipe_historys").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            self.logger.info(f"✅ [CRUD] Retrieved recipe histories successfully")
            self.logger.debug(f"📊 [CRUD] Retrieved {len(result.data)} recipe histories")
            return {"success": True, "data": result.data}
            
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to get recipe histories: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_history_by_id(self, client: Client, user_id: str, history_id: str) -> Dict[str, Any]:
        """特定のレシピ履歴を1件取得"""
        try:
            self.logger.info(f"🔍 [CRUD] Getting recipe history by ID")
            self.logger.debug(f"🔍 [CRUD] History ID: {history_id}")
            
            result = client.table("recipe_historys").select("*").eq("user_id", user_id).eq("id", history_id).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] Recipe history retrieved successfully")
                return {"success": True, "data": result.data[0]}
            else:
                return {"success": False, "error": "Recipe history not found"}
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to get recipe history by ID: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_history_by_id(
        self, 
        client: Client, 
        user_id: str, 
        history_id: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        url: Optional[str] = None,
        rating: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """ID指定でのレシピ履歴1件更新"""
        try:
            self.logger.info(f"✏️ [CRUD] Updating recipe history by ID")
            self.logger.debug(f"🔍 [CRUD] History ID: {history_id}")
            self.logger.debug(f"🔍 [CRUD] Received notes value: {repr(notes)} (type: {type(notes)})")
            
            # 更新データの準備
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if source is not None:
                update_data["source"] = source
            if url is not None:
                update_data["url"] = url
            if rating is not None:
                update_data["rating"] = rating
            if notes is not None:
                # 空文字列の場合はNULLに更新
                if isinstance(notes, str) and notes.strip() == "":
                    update_data["notes"] = None
                    self.logger.debug(f"🔍 [CRUD] Converted empty string to None for notes")
                else:
                    update_data["notes"] = notes
            elif notes is None:
                # notesが明示的にNoneの場合は、NULLに更新するために含める
                update_data["notes"] = None
                self.logger.debug(f"🔍 [CRUD] Setting notes to None explicitly")
            
            self.logger.debug(f"🔍 [CRUD] Update data: {update_data}")
            
            if not update_data:
                return {"success": False, "error": "No update data provided"}
            
            # データベース更新
            result = client.table("recipe_historys").update(update_data).eq("user_id", user_id).eq("id", history_id).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] Recipe history updated successfully")
                return {"success": True, "data": result.data[0]}
            else:
                return {"success": False, "error": "Recipe history not found"}
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to update recipe history by ID: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_history_by_id(self, client: Client, user_id: str, history_id: str) -> Dict[str, Any]:
        """ID指定でのレシピ履歴1件削除"""
        try:
            self.logger.info(f"🗑️ [CRUD] Deleting recipe history by ID")
            self.logger.debug(f"🔍 [CRUD] History ID: {history_id}")
            
            result = client.table("recipe_historys").delete().eq("user_id", user_id).eq("id", history_id).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] Recipe history deleted successfully")
                return {"success": True, "data": result.data[0]}
            else:
                return {"success": False, "error": "Recipe history not found"}
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to delete recipe history by ID: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_recent_recipe_titles(
        self,
        client: Client,
        user_id: str,
        category: str,  # "main", "sub", "soup"
        days: int = 14  # デフォルト14日間
    ) -> Dict[str, Any]:
        """指定期間内のレシピタイトルを取得（重複回避用）
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            category: カテゴリ（"main", "sub", "soup"）
            days: 重複回避期間（日数）
        
        Returns:
            Dict[str, Any]: {"success": bool, "data": List[str]} レシピタイトルのリスト
        """
        try:
            self.logger.debug(f"📋 [CRUD] Getting recent recipes")
            self.logger.debug(f"🔍 [CRUD] Category: {category}, User ID: {user_id}, Days: {days}")
            
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # カテゴリマッピング
            category_prefix_map = {
                "main": "主菜: ",
                "sub": "副菜: ",
                "soup": "汁物: "
            }
            
            # 指定期間内のレシピを取得
            result = client.table("recipe_historys")\
                .select("title")\
                .eq("user_id", user_id)\
                .gte("cooked_at", cutoff_date.isoformat())\
                .execute()
            
            # カテゴリでフィルタリング
            category_prefix = category_prefix_map.get(category)
            if category_prefix:
                titles = [item["title"] for item in result.data 
                          if item["title"].startswith(category_prefix)]
            else:
                # カテゴリ指定がない場合は全件
                titles = [item["title"] for item in result.data]
            
            self.logger.debug(f"✅ [CRUD] Retrieved recent recipe titles successfully")
            self.logger.debug(f"📊 [CRUD] Retrieved {len(titles)} recent {category} recipe titles")
            return {"success": True, "data": titles}
            
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to get recent recipe titles: {e}")
            return {"success": False, "error": str(e), "data": []}
    
    async def update_ingredients_deleted(
        self,
        client: Client,
        user_id: str,
        date: str,  # YYYY-MM-DD形式
        deleted: bool = True
    ) -> Dict[str, Any]:
        """指定日付のレシピ履歴のingredients_deletedフラグを更新"""
        try:
            self.logger.debug(f"✏️ [CRUD] Updating ingredients_deleted flag")
            self.logger.debug(f"🔍 [CRUD] Date: {date}")
            
            # 日付の検証と変換
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                start_datetime = datetime.combine(date_obj, datetime.min.time())
                end_datetime = datetime.combine(date_obj, datetime.max.time())
            except ValueError:
                return {"success": False, "error": "Invalid date format (YYYY-MM-DD required)"}
            
            # 指定日付のレシピ履歴を取得
            result = client.table("recipe_historys")\
                .select("id")\
                .eq("user_id", user_id)\
                .gte("cooked_at", start_datetime.isoformat())\
                .lte("cooked_at", end_datetime.isoformat())\
                .execute()
            
            if not result.data:
                self.logger.warning(f"⚠️ [CRUD] No recipe histories found for date: {date}")
                return {"success": True, "data": [], "updated_count": 0}
            
            # ingredients_deletedフラグを更新
            update_result = client.table("recipe_historys")\
                .update({"ingredients_deleted": deleted})\
                .eq("user_id", user_id)\
                .gte("cooked_at", start_datetime.isoformat())\
                .lte("cooked_at", end_datetime.isoformat())\
                .execute()
            
            updated_count = len(update_result.data) if update_result.data else 0
            self.logger.debug(f"✅ [CRUD] Updated recipe histories successfully")
            self.logger.debug(f"📊 [CRUD] Updated {updated_count} recipe histories")
            
            return {"success": True, "data": update_result.data, "updated_count": updated_count}
            
        except Exception as e:
            self.logger.error(f"❌ [CRUD] Failed to update ingredients_deleted flag: {e}")
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("✅ Recipe History CRUD module loaded successfully")
