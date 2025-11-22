#!/usr/bin/env python3
"""
API層 - レスポンスモデル

Pydanticによるレスポンスデータの型定義
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List


class ChatResponse(BaseModel):
    """チャットレスポンス"""
    model_config = ConfigDict(
        ser_json_exclude_defaults=False,
        ser_json_exclude_none=False
    )
    
    response: str = Field(..., description="AIからの応答")
    success: bool = Field(..., description="処理成功フラグ")
    model_used: str = Field(..., description="使用されたモデル")
    user_id: str = Field(..., description="ユーザーID")
    processing_time: Optional[float] = Field(default=None, description="処理時間（秒）")
    requires_confirmation: Optional[bool] = Field(default=False, description="曖昧性確認が必要かどうか")
    confirmation_session_id: Optional[str] = Field(default=None, description="確認セッションID")
    requires_selection: Optional[bool] = Field(default=False, description="ユーザー選択が必要かどうか")
    candidates: Optional[List[Dict[str, Any]]] = Field(default=None, description="選択候補リスト")
    task_id: Optional[str] = Field(default=None, description="タスクID")
    # Phase 3D: 段階情報
    current_stage: Optional[str] = Field(default=None, description="現在の段階（main/sub/soup）")
    used_ingredients: Optional[List[str]] = Field(default=None, description="使い残し食材リスト（在庫食材 - 使用済み食材）")
    menu_category: Optional[str] = Field(default=None, description="メニューカテゴリ（japanese/western/chinese）")
    # Phase 3C-3: 自動遷移フラグ
    requires_next_stage: Optional[bool] = Field(default=False, description="次の段階の提案が必要かどうか")


class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str = Field(..., description="サービス状態")
    service: str = Field(..., description="サービス名")
    version: str = Field(..., description="バージョン")
    timestamp: str = Field(..., description="チェック時刻")
    services: Optional[Dict[str, Any]] = Field(None, description="各サービスの状態")


class InventoryResponse(BaseModel):
    """在庫レスポンス"""
    id: str = Field(..., description="アイテムID")
    item_name: str = Field(..., description="アイテム名")
    quantity: float = Field(..., description="数量")
    unit: str = Field(..., description="単位")
    storage_location: Optional[str] = Field(None, description="保管場所")
    expiry_date: Optional[str] = Field(None, description="消費期限")
    created_at: str = Field(..., description="作成日時")
    updated_at: str = Field(..., description="更新日時")


class InventoryListResponse(BaseModel):
    """在庫一覧レスポンス"""
    success: bool = Field(..., description="成功フラグ")
    data: List[InventoryResponse] = Field(..., description="在庫アイテムリスト")


class InventoryItemResponse(BaseModel):
    """在庫アイテム単体レスポンス（追加・更新用）"""
    success: bool = Field(..., description="成功フラグ")
    data: InventoryResponse = Field(..., description="在庫アイテム")


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    detail: str = Field(..., description="エラー詳細")
    status_code: int = Field(..., description="HTTPステータスコード")
    timestamp: str = Field(..., description="エラー発生時刻")
    error_type: Optional[str] = Field(None, description="エラータイプ")


class SSEEvent(BaseModel):
    """SSEイベント"""
    type: str = Field(..., description="イベントタイプ")
    data: Dict[str, Any] = Field(..., description="イベントデータ")
    timestamp: str = Field(..., description="イベント時刻")


class SavedRecipe(BaseModel):
    """保存されたレシピ"""
    title: str = Field(..., description="レシピのタイトル")
    category: str = Field(..., description="レシピのカテゴリ")
    history_id: str = Field(..., description="保存されたレシピ履歴のID")


class RecipeAdoptionResponse(BaseModel):
    """レシピ採用通知レスポンス（複数対応）"""
    success: bool = Field(..., description="処理成功フラグ")
    message: str = Field(..., description="レスポンスメッセージ")
    saved_recipes: List[SavedRecipe] = Field(..., description="保存されたレシピのリスト")
    total_saved: int = Field(..., description="保存されたレシピ数")


class SavedMenuRecipe(BaseModel):
    """保存されたレシピ情報（献立保存用）"""
    category: str = Field(..., description="カテゴリ（main, sub, soup）")
    title: str = Field(..., description="プレフィックス付きタイトル")
    history_id: str = Field(..., description="保存されたレシピ履歴のID")


class MenuSaveResponse(BaseModel):
    """献立保存レスポンス"""
    success: bool = Field(..., description="処理成功フラグ")
    message: str = Field(..., description="レスポンスメッセージ")
    saved_recipes: List[SavedMenuRecipe] = Field(..., description="保存されたレシピのリスト")
    total_saved: int = Field(..., description="保存されたレシピ数")


class RecipeRatingUpdateRequest(BaseModel):
    """レシピ評価更新リクエスト"""
    rating: Optional[int] = Field(None, description="評価（5=好き、3=普通、1=好きじゃない）")
    notes: Optional[str] = Field(None, description="コメント")
    
    @field_validator('notes', mode='before')
    @classmethod
    def validate_notes(cls, v):
        """空文字列をNoneに変換"""
        if v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


class HistoryRecipe(BaseModel):
    """履歴レシピ情報"""
    category: Optional[str] = Field(None, description="カテゴリ（main, sub, soup, None）")
    title: str = Field(..., description="レシピのタイトル")
    source: str = Field(..., description="レシピの出典（web, rag等）")
    url: Optional[str] = Field(None, description="レシピのURL")
    history_id: str = Field(..., description="レシピ履歴のID")
    rating: Optional[int] = Field(None, description="評価（5=好き、3=普通、1=好きじゃない）")
    notes: Optional[str] = Field(None, description="コメント")
    image_url: Optional[str] = Field(None, description="レシピ画像URL")


class HistoryEntry(BaseModel):
    """履歴エントリ（日付単位）"""
    date: str = Field(..., description="日付（YYYY-MM-DD形式）")
    recipes: List[HistoryRecipe] = Field(..., description="その日のレシピリスト")
    ingredients_deleted: bool = Field(default=False, description="食材削除済みフラグ")


class MenuHistoryResponse(BaseModel):
    """献立履歴レスポンス"""
    success: bool = Field(..., description="処理成功フラグ")
    data: List[HistoryEntry] = Field(..., description="日付別の履歴エントリリスト")

class IngredientDeleteCandidate(BaseModel):
    """削除候補食材"""
    inventory_id: str = Field(..., description="在庫ID")
    item_name: str = Field(..., description="食材名")
    current_quantity: float = Field(..., description="現在の数量")
    unit: str = Field(..., description="単位")


class IngredientDeleteCandidatesResponse(BaseModel):
    """削除候補食材レスポンス"""
    success: bool = Field(..., description="処理成功フラグ")
    date: str = Field(..., description="日付（YYYY-MM-DD形式）")
    candidates: List[IngredientDeleteCandidate] = Field(..., description="削除候補食材リスト")


class IngredientDeleteResponse(BaseModel):
    """食材削除レスポンス"""
    success: bool = Field(..., description="処理成功フラグ")
    deleted_count: int = Field(..., description="削除件数（数量が0に設定された件数）")
    updated_count: int = Field(..., description="更新件数（数量が0以外に更新された件数）")
    failed_items: List[str] = Field(default_factory=list, description="失敗した食材リスト")
