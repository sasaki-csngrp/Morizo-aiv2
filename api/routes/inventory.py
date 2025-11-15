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

router = APIRouter()
logger = GenericLogger("api", "inventory")


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
        logger.info(f"🔍 [API] Inventory list request received: sort_by={sort_by}, sort_order={sort_order}")
        
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
        
        # 3. CRUDクラスを使用して在庫一覧を取得
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.get_all_items(client, user_id, sort_by=sort_by, sort_order=sort_order)
        
        if not result.get("success"):
            logger.error(f"❌ [API] Failed to get inventory list: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫取得処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] Retrieved {len(result.get('data', []))} inventory items")
        
        return {
            "success": True,
            "data": result.get("data", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in get_inventory_list: {e}")
        raise HTTPException(status_code=500, detail="在庫取得処理でエラーが発生しました")


@router.post("/inventory/add", response_model=InventoryItemResponse)
async def add_inventory_item(request: InventoryRequest, http_request: Request):
    """在庫アイテムを追加するエンドポイント"""
    try:
        logger.info("🔍 [API] Inventory add request received")
        logger.debug(f"🔍 [API] Item name: {request.item_name}")
        
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
        
        # 3. CRUDクラスを使用して在庫を追加
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
            logger.error(f"❌ [API] Failed to add inventory: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫追加処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] Inventory item added: {result.get('data', {}).get('id')}")
        
        return {
            "success": True,
            "data": result.get("data")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in add_inventory_item: {e}")
        raise HTTPException(status_code=500, detail="在庫追加処理でエラーが発生しました")


@router.put("/inventory/update/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: str,
    request: InventoryRequest,
    http_request: Request
):
    """在庫アイテムを更新するエンドポイント"""
    try:
        logger.info("🔍 [API] Inventory update request received")
        logger.debug(f"🔍 [API] Item ID: {item_id}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. CRUDクラスを使用して在庫を更新
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
            logger.error(f"❌ [API] Failed to update inventory: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫更新処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] Inventory item updated: {item_id}")
        
        return {
            "success": True,
            "data": result.get("data")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in update_inventory_item: {e}")
        raise HTTPException(status_code=500, detail="在庫更新処理でエラーが発生しました")


@router.delete("/inventory/delete/{item_id}")
async def delete_inventory_item(item_id: str, http_request: Request):
    """在庫アイテムを削除するエンドポイント"""
    try:
        logger.info("🔍 [API] Inventory delete request received")
        logger.debug(f"🔍 [API] Item ID: {item_id}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. CRUDクラスを使用して在庫を削除
        # 【特例】直接DB呼び出しは設計思想に反するが、在庫ビューアーは例外とする
        # CRUD操作のためにLLM→MCP経由は重いため、パフォーマンス重視で直接呼び出し
        crud = InventoryCRUD()
        result = await crud.delete_item_by_id(client, user_id, item_id)
        
        if not result.get("success"):
            logger.error(f"❌ [API] Failed to delete inventory: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "在庫削除処理でエラーが発生しました"))
        
        logger.info(f"✅ [API] Inventory item deleted: {item_id}")
        
        return {
            "success": True,
            "message": "在庫アイテムを削除しました"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Unexpected error in delete_inventory_item: {e}")
        raise HTTPException(status_code=500, detail="在庫削除処理でエラーが発生しました")

@router.post("/inventory/upload-csv", response_model=CSVUploadResponse)
async def upload_csv_inventory(
    file: UploadFile = File(...),
    http_request: Request = None
):
    """CSVファイルから在庫データを一括登録"""
    try:
        logger.info("🔍 [API] CSV upload request received")
        logger.debug(f"🔍 [API] Filename: {file.filename}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        
        # 2. ファイル検証
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="CSVファイルのみアップロード可能です")
        
        # ファイルサイズチェック（10MB制限）
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="ファイルサイズは10MB以下にしてください")
        
        # 3. CSV解析
        import csv
        import io
        from datetime import datetime
        
        # エンコーディング検出（UTF-8/BOM付き対応）
        try:
            text = file_content.decode('utf-8-sig')
        except:
            text = file_content.decode('utf-8')
        
        csv_reader = csv.DictReader(io.StringIO(text))
        
        # 4. データバリデーションと変換
        items = []
        validation_errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # ヘッダー行を除くため2から開始
            try:
                # 必須項目チェック
                if not row.get('item_name') or not row.get('item_name').strip():
                    validation_errors.append({
                        "row": row_num,
                        "item_name": row.get('item_name', ''),
                        "error": "アイテム名は必須です"
                    })
                    continue
                
                if not row.get('quantity'):
                    validation_errors.append({
                        "row": row_num,
                        "item_name": row.get('item_name', ''),
                        "error": "数量は必須です"
                    })
                    continue
                
                # 数量の型変換と検証
                try:
                    quantity = float(row['quantity'])
                    if quantity <= 0:
                        validation_errors.append({
                            "row": row_num,
                            "item_name": row.get('item_name', ''),
                            "error": "数量は0より大きい値が必要です"
                        })
                        continue
                except ValueError:
                    validation_errors.append({
                        "row": row_num,
                        "item_name": row.get('item_name', ''),
                        "error": "数量は数値である必要があります"
                    })
                    continue
                
                # アイテム名の長さチェック
                item_name = row['item_name'].strip()
                if len(item_name) > 100:
                    validation_errors.append({
                        "row": row_num,
                        "item_name": item_name,
                        "error": "アイテム名は100文字以下である必要があります"
                    })
                    continue
                
                # 単位の検証
                unit = row.get('unit', '個').strip()
                if len(unit) > 20:
                    validation_errors.append({
                        "row": row_num,
                        "item_name": item_name,
                        "error": "単位は20文字以下である必要があります"
                    })
                    continue
                
                # 保管場所の検証
                storage_location = row.get('storage_location', '冷蔵庫').strip()
                if storage_location and len(storage_location) > 50:
                    validation_errors.append({
                        "row": row_num,
                        "item_name": item_name,
                        "error": "保管場所は50文字以下である必要があります"
                    })
                    continue
                
                # 消費期限の検証
                expiry_date = row.get('expiry_date', '').strip()
                if expiry_date:
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        validation_errors.append({
                            "row": row_num,
                            "item_name": item_name,
                            "error": "消費期限はYYYY-MM-DD形式である必要があります"
                        })
                        continue
                
                # バリデーション通過
                items.append({
                    "item_name": item_name,
                    "quantity": quantity,
                    "unit": unit,
                    "storage_location": storage_location if storage_location else "冷蔵庫",
                    "expiry_date": expiry_date if expiry_date else None
                })
                
            except Exception as e:
                validation_errors.append({
                    "row": row_num,
                    "item_name": row.get('item_name', ''),
                    "error": f"データ処理エラー: {str(e)}"
                })
        
        # 5. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 6. 一括登録
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
        logger.error(f"❌ [API] Unexpected error in upload_csv_inventory: {e}")
        raise HTTPException(status_code=500, detail="CSVアップロード処理でエラーが発生しました")


def validate_image_file(image_bytes: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """画像ファイルの検証"""
    # ファイルサイズチェック（10MB制限）
    max_size = 10 * 1024 * 1024  # 10MB
    if len(image_bytes) > max_size:
        return False, "ファイルサイズは10MB以下にしてください"
    
    # ファイル形式チェック
    valid_extensions = ['.jpg', '.jpeg', '.png']
    file_ext = os.path.splitext(filename.lower())[1]
    
    if file_ext not in valid_extensions:
        return False, "JPEGまたはPNGファイルのみアップロード可能です"
    
    # 画像形式の検証（マジックナンバー）
    if image_bytes.startswith(b'\xff\xd8\xff'):
        # JPEG
        return True, None
    elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        # PNG
        return True, None
    else:
        return False, "画像ファイルの形式が正しくありません"


@router.post("/inventory/ocr-receipt", response_model=OCRReceiptResponse)
async def ocr_receipt(
    image: UploadFile = File(...),
    http_request: Request = None
):
    """レシート画像をOCR解析して在庫データを抽出・登録"""
    try:
        logger.info("🔍 [API] OCR receipt request received")
        logger.debug(f"🔍 [API] Filename: {image.filename}")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        
        # 2. 画像ファイルの検証
        image_bytes = await image.read()
        is_valid, error_message = validate_image_file(image_bytes, image.filename)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # 3. OCR解析
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
        
        # 4. 変換テーブル適用
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
            
            # 変換テーブルを適用
            items = await ocr_service.apply_item_mappings(items, client, user_id)
            logger.debug(f"✅ [API] Applied item mappings to {len(items)} items")
        except Exception as e:
            # 変換テーブル適用が失敗しても、既存の処理は継続
            logger.warning(f"⚠️ [API] Failed to apply item mappings: {e}")
        
        # 5. データバリデーション
        validated_items = []
        validation_errors = []
        
        for idx, item in enumerate(items, 1):
            try:
                # 必須項目チェック
                if not item.get("item_name") or not str(item.get("item_name")).strip():
                    validation_errors.append(f"行{idx}: アイテム名が空です")
                    continue
                
                if item.get("quantity") is None:
                    validation_errors.append(f"行{idx}: 数量が指定されていません")
                    continue
                
                # 数量の検証
                try:
                    quantity = float(item["quantity"])
                    if quantity <= 0:
                        validation_errors.append(f"行{idx}: 数量は0より大きい値が必要です")
                        continue
                except (ValueError, TypeError):
                    validation_errors.append(f"行{idx}: 数量が数値ではありません")
                    continue
                
                # 単位のデフォルト値
                unit = item.get("unit", "個")
                
                validated_items.append({
                    "item_name": str(item["item_name"]).strip(),
                    "quantity": quantity,
                    "unit": str(unit).strip(),
                    "storage_location": item.get("storage_location", "冷蔵庫"),
                    "expiry_date": item.get("expiry_date")
                })
                
            except Exception as e:
                validation_errors.append(f"行{idx}: データ処理エラー - {str(e)}")
        
        # 5. 在庫登録（バリデーション通過したアイテムのみ）
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
        logger.error(f"❌ [API] Unexpected error in ocr_receipt: {e}")
        raise HTTPException(status_code=500, detail="OCR処理でエラーが発生しました")


@router.post("/inventory/ocr-mapping", response_model=OCRMappingResponse)
async def add_ocr_mapping(
    request: OCRMappingRequest,
    http_request: Request = None
):
    """OCR変換テーブルに登録"""
    try:
        logger.info("🔍 [API] OCR mapping request received")
        logger.debug(f"🔍 [API] Mapping: '{request.original_name}' -> '{request.normalized_name}'")
        
        # 1. 認証処理
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        user_info = getattr(http_request.state, 'user_info', None)
        if not user_info:
            logger.error("❌ [API] User info not found in request state")
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        user_id = user_info['user_id']
        
        # 2. 認証済みSupabaseクライアントの作成
        try:
            client = get_authenticated_client(user_id, token)
            logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to create authenticated client: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")
        
        # 3. 変換テーブルに登録
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
            logger.error(f"❌ [API] Failed to add OCR mapping: {error_message}")
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
        logger.error(f"❌ [API] Unexpected error in add_ocr_mapping: {e}")
        raise HTTPException(status_code=500, detail="変換テーブル登録処理でエラーが発生しました")

