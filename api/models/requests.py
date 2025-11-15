#!/usr/bin/env python3
"""
API層 - リクエストモデル

Pydanticによるリクエストデータの型定義とバリデーション
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """チャットリクエスト"""
    model_config = {"populate_by_name": True}  # Pydantic v2
    
    message: str = Field(..., description="ユーザーメッセージ", min_length=1, max_length=1000)
    token: Optional[str] = Field(None, description="認証トークン")
    sse_session_id: Optional[str] = Field(None, description="SSEセッションID", alias="sseSessionId")
    confirm: bool = Field(
        default=False, 
        description="曖昧性解決の回答かどうか"
    )
    
    @field_validator('confirm', mode='before')
    @classmethod
    def validate_confirm(cls, v):
        """confirmのバリデーション（デバッグ用）"""
        from config.loggers import GenericLogger
        logger = GenericLogger("api", "pydantic")
        logger.debug(f"🔍 [Pydantic] confirm validator called with value: {v} (type: {type(v)})")
        return v


class ProgressUpdate(BaseModel):
    """進捗更新"""
    type: str = Field(..., description="更新タイプ: progress, complete, error")
    progress: int = Field(..., description="進捗率（0-100）", ge=0, le=100)
    message: str = Field(..., description="進捗メッセージ")
    timestamp: str = Field(..., description="タイムスタンプ")


class InventoryRequest(BaseModel):
    """在庫リクエスト"""
    item_name: str = Field(..., description="アイテム名", min_length=1, max_length=100)
    quantity: float = Field(..., description="数量", gt=0)
    unit: str = Field(..., description="単位", min_length=1, max_length=20)
    storage_location: Optional[str] = Field(None, description="保管場所", max_length=50)
    expiry_date: Optional[str] = Field(None, description="消費期限")


class HealthRequest(BaseModel):
    """ヘルスチェックリクエスト"""
    check_services: Optional[bool] = Field(False, description="サービス状態の確認")


class RecipeItem(BaseModel):
    """個別レシピアイテム"""
    title: str = Field(
        ..., 
        description="レシピのタイトル", 
        min_length=1, 
        max_length=255
    )
    category: str = Field(
        ..., 
        description="レシピのカテゴリ",
        pattern="^(main_dish|side_dish|soup)$"
    )
    menu_source: str = Field(
        ..., 
        description="メニューの出典",
        pattern="^(llm_menu|rag_menu|manual)$"
    )
    url: Optional[str] = Field(
        None, 
        description="レシピのURL（Web検索から採用した場合）"
    )
    ingredients: Optional[List[str]] = Field(None, description="利用食材リスト")


class RecipeAdoptionRequest(BaseModel):
    """レシピ採用通知リクエスト（複数対応）"""
    recipes: List[RecipeItem] = Field(
        ..., 
        description="採用されたレシピのリスト",
        min_length=1,
        max_length=3  # 主菜・副菜・汁物の最大3つ
    )
    token: Optional[str] = Field(
        None, 
        description="認証トークン（ヘッダーからも取得可能）"
    )


class MenuSaveRequest(BaseModel):
    """献立保存リクエスト"""
    sse_session_id: Optional[str] = Field(None, description="SSEセッションID（後方互換性のためオプショナル）")
    recipes: Optional[Dict[str, Any]] = Field(None, description="選択済みレシピ（main, sub, soup）。指定された場合はセッションIDよりも優先される")

class CSVUploadError(BaseModel):
    """CSVアップロードエラー情報"""
    row: Optional[int] = Field(None, description="行番号（CSV行番号、空の場合はNone）")
    item_name: Optional[str] = Field(None, description="アイテム名")
    error: str = Field(..., description="エラーメッセージ")


class CSVUploadResponse(BaseModel):
    """CSVアップロードレスポンス"""
    success: bool = Field(..., description="成功したかどうか")
    total: int = Field(..., description="総件数")
    success_count: int = Field(..., description="成功件数")
    error_count: int = Field(..., description="エラー件数")
    errors: List[CSVUploadError] = Field(default_factory=list, description="エラー詳細")


class OCRReceiptItem(BaseModel):
    """OCR抽出アイテム"""
    item_name: str = Field(..., description="アイテム名")
    quantity: float = Field(..., description="数量")
    unit: str = Field(..., description="単位")
    storage_location: Optional[str] = Field(None, description="保管場所")
    expiry_date: Optional[str] = Field(None, description="消費期限")


class OCRReceiptResponse(BaseModel):
    """OCRレシート解析レスポンス"""
    success: bool = Field(..., description="成功したかどうか")
    items: List[OCRReceiptItem] = Field(default_factory=list, description="抽出されたアイテムリスト")
    registered_count: int = Field(..., description="登録された件数")
    errors: List[str] = Field(default_factory=list, description="エラーメッセージ")


class IngredientDeleteItem(BaseModel):
    """削除対象食材アイテム"""
    item_name: str = Field(..., description="食材名")
    quantity: float = Field(0, description="更新後の数量（0で削除）")
    inventory_id: Optional[str] = Field(None, description="在庫ID（指定がある場合）")


class IngredientDeleteRequest(BaseModel):
    """食材削除リクエスト"""
    date: str = Field(..., description="日付（YYYY-MM-DD形式）")
    ingredients: List[IngredientDeleteItem] = Field(..., description="削除対象食材リスト")


class OCRMappingRequest(BaseModel):
    """OCR変換テーブル登録リクエスト"""
    original_name: str = Field(..., description="OCRで読み取られた元の名前", min_length=1, max_length=255)
    normalized_name: str = Field(..., description="正規化後の名前", min_length=1, max_length=255)


class OCRMappingResponse(BaseModel):
    """OCR変換テーブル登録レスポンス"""
    success: bool = Field(..., description="成功したかどうか")
    message: str = Field(..., description="メッセージ")
    mapping_id: Optional[str] = Field(None, description="登録されたマッピングID")
