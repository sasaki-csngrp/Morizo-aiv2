#!/usr/bin/env python3
"""
API層 - CSVバリデーションユーティリティ

CSVファイルの解析とバリデーション処理
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Tuple, Any


def parse_and_validate_csv(file_content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    CSVファイルを解析し、バリデーションを実行
    
    Args:
        file_content: CSVファイルのバイトデータ
        filename: ファイル名（検証用）
    
    Returns:
        Tuple[List[Dict], List[Dict]]: (validated_items, validation_errors)
        - validated_items: バリデーション通過したアイテムのリスト
        - validation_errors: バリデーションエラーのリスト
    """
    # エンコーディング検出（UTF-8/BOM付き対応）
    try:
        text = file_content.decode('utf-8-sig')
    except:
        text = file_content.decode('utf-8')
    
    csv_reader = csv.DictReader(io.StringIO(text))
    
    # データバリデーションと変換
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
    
    return items, validation_errors

