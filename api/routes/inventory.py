#!/usr/bin/env python3
"""
API層 - 在庫ルート

在庫管理のエンドポイント（一覧取得、CRUD操作）
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from typing import Dict, Any, Optional, Tuple
import os
from config.loggers import GenericLogger
from ..models import InventoryResponse, InventoryListResponse, InventoryItemResponse, InventoryRequest, CSVUploadResponse, OCRReceiptResponse, OCRMappingRequest, OCRMappingResponse
from mcp_servers.inventory_crud import InventoryCRUD
from mcp_servers.utils import get_authenticated_client
from ..utils.inventory_auth import get_authenticated_user_and_client
from ..utils.file_validator import validate_image_file
from ..utils.csv_validator import parse_and_validate_csv
from ..utils.ocr_validator import validate_ocr_items
from ..utils.subscription_service import SubscriptionService
from ..models.responses import UsageLimitExceededResponse

router = APIRouter()
logger = GenericLogger("api", "inventory")
subscription_service = SubscriptionService()


@router.get("/inventory/list", response_model=InventoryListResponse)
async def get_inventory_list(
    http_request: Request,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc"
):
    """在庫一覧を取得するエンドポイント
    
    Args:
        sort_by: ソート対象カラム (item_name, quantity, created_at, storage_location, expiry_date)
        sort_order: ソート順序 (asc, desc)
    """
    try:
        logger.info(f"🔍 [API] 在庫一覧リクエストを受信しました: sort_by={sort_by}, sort_order={sort_order}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. CRUDクラスを使用して在庫一覧を取得
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.get_all_items(client, user_id, sort_by=sort_by, sort_order=sort_order)
        
        if not result.get("success"):
            logger.error(f"❌ [API] 在庫一覧の取得に失敗しました: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫取得処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] 在庫アイテム {len(result.get('data', []))} 件を取得しました")
        
        return {
            "success": True,
            "data": result.get("data", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 在庫一覧取得処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="在庫取得処理でエラーが発生しました")


@router.post("/inventory/add", response_model=InventoryItemResponse)
async def add_inventory_item(request: InventoryRequest, http_request: Request):
    """在庫アイテムを追加するエンドポイント"""
    try:
        logger.info("🔍 [API] 在庫追加リクエストを受信しました")
        logger.debug(f"🔍 [API] Item name: {request.item_name}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. CRUDクラスを使用して在庫を追加
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.add_item(
            client=client,
            user_id=user_id,
            item_name=request.item_name,
            quantity=request.quantity,
            unit=request.unit,
            storage_location=request.storage_location,
            expiry_date=request.expiry_date
        )
        
        if not result.get("success"):
            logger.error(f"❌ [API] 在庫追加に失敗しました: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫追加処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] 在庫アイテムを追加しました: {result.get('data', {}).get('id')}")
        
        return {
            "success": True,
            "data": result.get("data")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 在庫追加処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="在庫追加処理でエラーが発生しました")


@router.put("/inventory/update/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: str,
    request: InventoryRequest,
    http_request: Request
):
    """在庫アイテムを更新するエンドポイント"""
    try:
        logger.info("🔍 [API] 在庫更新リクエストを受信しました")
        logger.debug(f"🔍 [API] Item ID: {item_id}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. CRUDクラスを使用して在庫を更新
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.update_item_by_id(
            client=client,
            user_id=user_id,
            item_id=item_id,
            item_name=request.item_name,
            quantity=request.quantity,
            unit=request.unit,
            storage_location=request.storage_location,
            expiry_date=request.expiry_date
        )
        
        if not result.get("success"):
            logger.error(f"❌ [API] 在庫更新に失敗しました: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫更新処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] 在庫アイテムを更新しました: {item_id}")
        
        return {
            "success": True,
            "data": result.get("data")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 在庫更新処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="在庫更新処理でエラーが発生しました")


@router.delete("/inventory/delete/{item_id}")
async def delete_inventory_item(item_id: str, http_request: Request):
    """在庫アイテムを削除するエンドポイント"""
    try:
        logger.info("🔍 [API] 在庫削除リクエストを受信しました")
        logger.debug(f"🔍 [API] Item ID: {item_id}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. CRUDクラスを使用して在庫を削除
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.delete_item_by_id(client, user_id, item_id)
        
        if not result.get("success"):
            logger.error(f"❌ [API] 在庫削除に失敗しました: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫削除処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] 在庫アイテムを削除しました: {item_id}")
        
        return {
            "success": True,
            "message": "在庫アイテムを削除しました"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] 在庫削除処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="在庫削除処理でエラーが発生しました")

@router.post("/inventory/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_inventory(
    file: UploadFile = File(...),
    http_request: Request = None
):
    """CSVファイルから在庫データを一括登録"""
    try:
        logger.info("🔍 [API] CSVアップロードリクエストを受信しました")
        logger.debug(f"🔍 [API] Filename: {file.filename}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. ファイル検証
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="CSVファイルのみアップロード可能です")
        
        # ファイルサイズチェック（10MB制限）
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="ファイルサイズは10MB以下にしてください")
        
        # 3. CSV解析とバリデーション
        items, validation_errors = parse_and_validate_csv(file_content, file.filename)
        
        # 4. 一括登録
        crud = InventoryCRUD()
        result = await crud.add_items_bulk(client, user_id, items)
        
        # バリデーションエラーとDBエラーを統合
        total_errors = validation_errors + result.get("errors", [])
        
        return {
            "success": result.get("success", False) and len(validation_errors) == 0,
            "total": len(items) + len(validation_errors),
            "success_count": result.get("success_count", 0),
            "error_count": len(total_errors),
            "errors": total_errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] CSVアップロード処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="CSVアップロード処理でエラーが発生しました")


@router.post("/inventory/ocr-receipt", response_model=OCRReceiptResponse)
async def ocr_receipt(
    image: UploadFile = File(...),
    http_request: Request = None
):
    """レシート画像をOCR解析して在庫データを抽出・登録"""
    try:
        logger.info("🔍 [API] OCRレシートリクエストを受信しました")
        logger.debug(f"🔍 [API] Filename: {image.filename}")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. 利用回数制限チェック（OCR機能）
        is_allowed, limit_info = await subscription_service.check_usage_limit(user_id, "ocr", client)
        if not is_allowed:
            logger.warning(f"⚠️ [API] OCR usage limit exceeded for user: {user_id}")
            raise HTTPException(
                status_code=403,
                detail=limit_info.get("error", "利用回数制限に達しました"),
                headers={
                    "X-Error-Code": limit_info.get("error_code", "USAGE_LIMIT_EXCEEDED"),
                    "X-Feature": limit_info.get("feature", "ocr"),
                    "X-Current-Count": str(limit_info.get("current_count", 0)),
                    "X-Limit": str(limit_info.get("limit", 0)),
                    "X-Plan": limit_info.get("plan", "free"),
                    "X-Reset-At": limit_info.get("reset_at", "")
                }
            )
        
        # 3. 画像ファイルの検証
        image_bytes = await image.read()
        is_valid, error_message = validate_image_file(image_bytes, image.filename)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # 4. OCR解析
        from services.ocr_service import OCRService
        
        ocr_service = OCRService()
        ocr_result = await ocr_service.analyze_receipt_image(image_bytes)
        
        if not ocr_result.get("success"):
            # OCR解析失敗の場合は400エラーとして返す（クライアント側の問題）
            error_message = ocr_result.get("error", "OCR解析に失敗しました")
            logger.error(f"❌ [API] OCR解析失敗: {error_message}")
            raise HTTPException(
                status_code=400,
                detail=error_message
            )
        
        items = ocr_result.get("items", [])
        
        if not items:
            return {
                "success": True,
                "items": [],
                "registered_count": 0,
                "errors": ["レシートから在庫情報を抽出できませんでした"]
            }
        
        # 5. 利用回数をインクリメント（OCR解析成功時）
        increment_result = await subscription_service.increment_usage(user_id, "ocr", client)
        if not increment_result.get("success"):
            logger.warning(f"⚠️ [API] OCR利用回数のインクリメントに失敗しました: {increment_result.get('error')}")
            # インクリメント失敗は警告のみ（処理は継続）
        
        # 6. 変換テーブル適用
        try:
            # 変換テーブルを適用
            items = await ocr_service.apply_item_mappings(items, client, user_id)
            logger.debug(f"✅ [API] {len(items)} 件のアイテムにマッピングを適用しました")
        except Exception as e:
            # 変換テーブル適用が失敗しても、既存の処理は継続
            logger.warning(f"⚠️ [API] アイテムマッピングの適用に失敗しました: {e}")
        
        # 7. データバリデーション
        validated_items, validation_errors = validate_ocr_items(items)
        
        # 8. 在庫登録（バリデーション通過したアイテムのみ）
        # 【コメントアウト】フロントエンドで選択したアイテムのみを登録するため、自動登録は無効化
        # registered_count = 0
        # if validated_items:
        #     try:
        #         client = get_authenticated_client(user_id, token)
        #         crud = InventoryCRUD()
        #         result = await crud.add_items_bulk(client, user_id, validated_items)
        #         
        #         if result.get("success"):
        #             registered_count = result.get("success_count", 0)
        #             # DBエラーもvalidation_errorsに追加
        #             if result.get("errors"):
        #                 validation_errors.extend([
        #                     f"DBエラー: {err.get('error', 'Unknown error')}"
        #                     for err in result.get("errors", [])
        #                 ])
        #         else:
        #             validation_errors.append("在庫登録に失敗しました")
        #             
        #     except Exception as e:
        #         logger.error(f"❌ [API] Failed to register inventory: {e}")
        #         validation_errors.append(f"在庫登録エラー: {str(e)}")
        
        # フロントエンドで登録するため、registered_countは常に0
        registered_count = 0
        
        return {
            "success": True,
            "items": validated_items,
            "registered_count": registered_count,
            "errors": validation_errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] OCR処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="OCR処理でエラーが発生しました")


@router.post("/inventory/ocr-mapping", response_model=OCRMappingResponse)
async def add_ocr_mapping(
    request: OCRMappingRequest,
    http_request: Request = None
):
    """OCR変換テーブルに登録"""
    try:
        logger.info("🔍 [API] OCRマッピングリクエストを受信しました")
        logger.debug(f"🔍 [API] Mapping: '{request.original_name}' -> '{request.normalized_name}'")
        
        # 1. 認証処理とクライアント作成
        user_id, client = await get_authenticated_user_and_client(http_request)
        
        # 2. 変換テーブルに登録
        from mcp_servers.ocr_mapping_crud import OCRMappingCRUD
        
        mapping_crud = OCRMappingCRUD()
        result = await mapping_crud.add_mapping(
            client=client,
            user_id=user_id,
            original_name=request.original_name,
            normalized_name=request.normalized_name
        )
        
        if not result.get("success"):
            error_message = result.get("error", "変換テーブルへの登録に失敗しました")
            logger.error(f"❌ [API] OCRマッピングの追加に失敗しました: {error_message}")
            raise HTTPException(status_code=500, detail=error_message)
        
        mapping_id = result.get("data", {}).get("id") if result.get("data") else None
        
        logger.info(f"✅ [API] OCR mapping added successfully: {mapping_id}")
        
        return {
            "success": True,
            "message": "変換テーブルに登録しました",
            "mapping_id": mapping_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] OCRマッピング追加処理で予期しないエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="変換テーブル登録処理でエラーが発生しました")

