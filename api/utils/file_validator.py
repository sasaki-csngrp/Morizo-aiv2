#!/usr/bin/env python3
"""
API層 - ファイル検証ユーティリティ

ファイルアップロード時の検証処理
"""

import os
from typing import Tuple, Optional


def validate_image_file(image_bytes: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """画像ファイルの検証
    
    Args:
        image_bytes: 画像ファイルのバイトデータ
        filename: ファイル名
    
    Returns:
        Tuple[bool, Optional[str]]: (検証結果, エラーメッセージ)
    """
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

