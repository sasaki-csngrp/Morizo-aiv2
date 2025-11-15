#!/usr/bin/env python3
"""
ProposalComponent - 提案レシピ管理コンポーネント

提案レシピ履歴の管理を担当
"""

from typing import Dict, List
from config.loggers import GenericLogger


class ProposalComponent:
    """提案レシピ管理コンポーネント"""
    
    def __init__(self, logger: GenericLogger):
        """初期化
        
        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.proposed_recipes: Dict[str, list] = {"main": [], "sub": [], "soup": []}
    
    def add(self, category: str, titles: list) -> None:
        """提案済みレシピタイトルを追加
        
        Args:
            category: カテゴリ（"main", "sub", "soup"）
            titles: 提案済みタイトルのリスト
        """
        if category in self.proposed_recipes:
            self.proposed_recipes[category].extend(titles)
            self.logger.debug(f"📝 [SESSION] Added {len(titles)} proposed {category} recipes")
    
    def get(self, category: str) -> list:
        """提案済みレシピタイトルを取得
        
        Args:
            category: カテゴリ（"main", "sub", "soup"）
        
        Returns:
            list: 提案済みタイトルのリスト
        """
        return self.proposed_recipes.get(category, [])
    
    def clear(self, category: str) -> None:
        """提案済みレシピをクリア
        
        Args:
            category: カテゴリ（"main", "sub", "soup"）
        """
        if category in self.proposed_recipes:
            self.proposed_recipes[category] = []
            self.logger.info(f"🧹 [SESSION] Cleared proposed {category} recipes")

