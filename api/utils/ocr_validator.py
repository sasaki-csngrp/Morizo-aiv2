#!/usr/bin/env python3
"""
API層 - OCRバリデーションユーティリティ

OCR結果のバリデーション処理
"""

from typing import List, Dict, Tuple, Any


def validate_ocr_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    OCR結果のアイテムをバリデーション
    
    Args:
        items: OCRで抽出されたアイテムのリスト
    
    Returns:
        Tuple[List[Dict], List[str]]: (validated_items, validation_errors)
        - validated_items: バリデーション通過したアイテムのリスト
        - validation_errors: バリデーションエラーのリスト（文字列形式）
    """
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
    
    return validated_items, validation_errors

