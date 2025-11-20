#!/usr/bin/env python3
"""
Recipe data models - レシピ関連のデータモデル定義

データ構造を明確化し、型安全性を向上させるためのデータクラス
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class RecipeProposal:
    """レシピ提案のデータモデル"""
    title: str
    ingredients: List[str]
    source: str  # "llm" or "rag"
    url: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            "title": self.title,
            "ingredients": self.ingredients,
            "source": self.source
        }
        if self.url:
            result["url"] = self.url
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class MenuResult:
    """献立結果のデータモデル"""
    main_dish: str
    side_dish: str
    soup: str
    main_dish_ingredients: List[str]
    side_dish_ingredients: List[str]
    soup_ingredients: List[str]
    ingredients_used: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "main_dish": self.main_dish,
            "side_dish": self.side_dish,
            "soup": self.soup,
            "main_dish_ingredients": self.main_dish_ingredients,
            "side_dish_ingredients": self.side_dish_ingredients,
            "soup_ingredients": self.soup_ingredients,
            "ingredients_used": self.ingredients_used
        }


@dataclass
class WebSearchResult:
    """Web検索結果のデータモデル"""
    title: str
    url: str
    source: str  # "vector_db" or "web"
    description: Optional[str] = None
    site: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            "title": self.title,
            "url": self.url,
            "source": self.source
        }
        if self.description:
            result["description"] = self.description
        if self.site:
            result["site"] = self.site
        return result

