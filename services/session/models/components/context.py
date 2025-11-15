#!/usr/bin/env python3
"""
ContextComponent - コンテキスト管理コンポーネント

セッションコンテキストの管理を担当
"""

from typing import Dict, Any
from config.loggers import GenericLogger


class ContextComponent:
    """コンテキスト管理コンポーネント"""
    
    def __init__(self, logger: GenericLogger):
        """初期化
        
        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.context: Dict[str, Any] = {
            "inventory_items": [],
            "main_ingredient": None,
            "menu_type": ""
        }
    
    def set(self, key: str, value: Any) -> None:
        """セッションコンテキストを設定
        
        Args:
            key: コンテキストキー（"inventory_items", "main_ingredient", "menu_type"等）
            value: 値
        """
        self.context[key] = value
        self.logger.debug(f"💾 [SESSION] Context set: {key}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """セッションコンテキストを取得
        
        Args:
            key: コンテキストキー
            default: デフォルト値
        
        Returns:
            Any: コンテキスト値
        """
        return self.context.get(key, default)

