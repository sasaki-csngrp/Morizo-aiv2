#!/usr/bin/env python3
"""
CandidateComponent - 候補管理コンポーネント

候補情報の管理を担当
"""

from typing import Dict, List
from config.loggers import GenericLogger


class CandidateComponent:
    """候補管理コンポーネント"""
    
    def __init__(self, logger: GenericLogger):
        """初期化
        
        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.candidates: Dict[str, list] = {"main": [], "sub": [], "soup": [], "other": []}
    
    def set(self, category: str, candidates: list) -> None:
        """候補情報を保存（Phase 3C-3）
        
        Args:
            category: カテゴリ（"main", "sub", "soup", "other"）
            candidates: 候補情報のリスト
        """
        # カテゴリが存在しない場合は初期化
        if category not in self.candidates:
            self.candidates[category] = []
        self.candidates[category] = candidates
        self.logger.debug(f"💾 [SESSION] Set {len(candidates)} {category} candidates")
    
    def get(self, category: str) -> list:
        """候補情報を取得
        
        Args:
            category: カテゴリ（"main", "sub", "soup", "other"）
        
        Returns:
            list: 候補情報のリスト
        """
        return self.candidates.get(category, [])

