"""
Morizo AI v2 - OCR Mapping CRUD Operations

OCR商品名変換テーブルの基本CRUD操作
"""

from typing import Dict, Any, List, Optional
from supabase import Client

from config.loggers import GenericLogger


class OCRMappingCRUD:
    """OCR商品名変換テーブルの基本CRUD操作"""
    
    def __init__(self):
        self.logger = GenericLogger("mcp", "ocr_mapping_crud", initialize_logging=False)
    
    async def add_mapping(
        self,
        client: Client,
        user_id: str,
        original_name: str,
        normalized_name: str
    ) -> Dict[str, Any]:
        """変換テーブルに登録（UPSERT対応）
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            original_name: OCRで読み取られた元の名前
            normalized_name: 正規化後の名前
            
        Returns:
            {
                "success": bool,
                "data": Optional[Dict[str, Any]],
                "error": Optional[str]
            }
        """
        try:
            self.logger.info(f"📝 [CRUD] OCRマッピングを追加中")
            self.logger.debug(f"🔍 [CRUD] 元の名前: '{original_name}' -> 正規化名: '{normalized_name}'")
            
            # データ準備
            data = {
                "user_id": user_id,
                "original_name": original_name.strip(),
                "normalized_name": normalized_name.strip()
            }
            
            # UPSERT（既に存在する場合は更新、存在しない場合は挿入）
            # UNIQUE(user_id, original_name)制約があるため、upsertを使用
            result = client.table("ocr_item_mappings").upsert(
                data,
                on_conflict="user_id,original_name"
            ).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] OCRマッピングの追加/更新に成功しました")
                self.logger.debug(f"🔍 [CRUD] マッピングID: {result.data[0]['id']}")
                return {
                    "success": True,
                    "data": result.data[0]
                }
            else:
                raise Exception("No data returned from upsert")
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] OCRマッピングの追加に失敗: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
    
    async def get_mapping(
        self,
        client: Client,
        user_id: str,
        original_name: str
    ) -> Dict[str, Any]:
        """変換テーブルから取得
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            original_name: OCRで読み取られた元の名前
            
        Returns:
            {
                "success": bool,
                "data": Optional[Dict[str, Any]],
                "error": Optional[str]
            }
        """
        try:
            self.logger.debug(f"🔍 [CRUD] OCRマッピングを取得中: user_id={user_id}, 元の名前='{original_name}'")
            
            result = client.table("ocr_item_mappings").select("*").eq(
                "user_id", user_id
            ).eq(
                "original_name", original_name.strip()
            ).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.debug(f"✅ [CRUD] OCRマッピングが見つかりました: {result.data[0]['id']}")
                return {
                    "success": True,
                    "data": result.data[0]
                }
            else:
                self.logger.debug(f"ℹ️ [CRUD] '{original_name}'のOCRマッピングが見つかりませんでした")
                return {
                    "success": True,
                    "data": None
                }
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] OCRマッピングの取得に失敗: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
    
    async def get_all_mappings(
        self,
        client: Client,
        user_id: str
    ) -> Dict[str, Any]:
        """ユーザーの全変換テーブルを取得
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            
        Returns:
            {
                "success": bool,
                "data": List[Dict[str, Any]],
                "error": Optional[str]
            }
        """
        try:
            self.logger.info(f"🔍 [CRUD] 全OCRマッピングを取得中")
            self.logger.debug(f"🔍 [CRUD] ユーザーID: {user_id}")
            
            result = client.table("ocr_item_mappings").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] OCRマッピングの取得に成功しました")
                self.logger.debug(f"📊 [CRUD] {len(result.data)}件のOCRマッピングを取得しました")
                return {
                    "success": True,
                    "data": result.data
                }
            else:
                self.logger.info(f"ℹ️ [CRUD] ユーザー{user_id}のOCRマッピングが見つかりませんでした")
                return {
                    "success": True,
                    "data": []
                }
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] 全OCRマッピングの取得に失敗: {e}")
            return {
                "success": False,
                "data": [],
                "error": str(e)
            }
    
    async def update_mapping(
        self,
        client: Client,
        user_id: str,
        original_name: str,
        normalized_name: str
    ) -> Dict[str, Any]:
        """変換テーブルを更新
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            original_name: OCRで読み取られた元の名前
            normalized_name: 正規化後の名前（更新値）
            
        Returns:
            {
                "success": bool,
                "data": Optional[Dict[str, Any]],
                "error": Optional[str]
            }
        """
        try:
            self.logger.info(f"📝 [CRUD] OCRマッピングを更新中")
            self.logger.debug(f"🔍 [CRUD] 元の名前: '{original_name}' -> 正規化名: '{normalized_name}'")
            
            # 既存のマッピングを取得
            get_result = await self.get_mapping(client, user_id, original_name)
            
            if not get_result.get("success"):
                return {
                    "success": False,
                    "data": None,
                    "error": get_result.get("error", "Failed to get existing mapping")
                }
            
            if not get_result.get("data"):
                # 存在しない場合は新規作成
                return await self.add_mapping(client, user_id, original_name, normalized_name)
            
            # 更新
            mapping_id = get_result["data"]["id"]
            result = client.table("ocr_item_mappings").update({
                "normalized_name": normalized_name.strip()
            }).eq("id", mapping_id).execute()
            
            if result.data:
                self.logger.info(f"✅ [CRUD] OCRマッピングの更新に成功しました")
                self.logger.debug(f"🔍 [CRUD] マッピングID: {mapping_id}")
                return {
                    "success": True,
                    "data": result.data[0]
                }
            else:
                raise Exception("No data returned from update")
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] OCRマッピングの更新に失敗: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
    
    async def delete_mapping(
        self,
        client: Client,
        user_id: str,
        original_name: str
    ) -> Dict[str, Any]:
        """変換テーブルを削除
        
        Args:
            client: Supabaseクライアント
            user_id: ユーザーID
            original_name: OCRで読み取られた元の名前
            
        Returns:
            {
                "success": bool,
                "error": Optional[str]
            }
        """
        try:
            self.logger.info(f"🗑️ [CRUD] OCRマッピングを削除中")
            self.logger.debug(f"🔍 [CRUD] 元の名前: '{original_name}'")
            
            result = client.table("ocr_item_mappings").delete().eq(
                "user_id", user_id
            ).eq(
                "original_name", original_name.strip()
            ).execute()
            
            self.logger.info(f"✅ [CRUD] OCRマッピングの削除に成功しました")
            return {
                "success": True
            }
                
        except Exception as e:
            self.logger.error(f"❌ [CRUD] OCRマッピングの削除に失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

