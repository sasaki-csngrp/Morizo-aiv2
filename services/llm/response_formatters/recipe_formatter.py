#!/usr/bin/env python3
"""
RecipeFormatter - レシピフォーマット処理

レシピ関連のレスポンスフォーマット処理を担当
"""

from typing import Dict, Any, List
from .base import BaseFormatter


class RecipeFormatter(BaseFormatter):
    """レシピフォーマット処理クラス"""
    
    def __init__(self):
        """初期化"""
        super().__init__("service", "llm.response.formatters.recipe")
    
    def format_web_recipes(self, web_data: Any) -> List[str]:
        """Web検索結果のフォーマット（簡素化版）"""
        response_parts = []
        
        try:
            # 修正: success判定を追加
            if isinstance(web_data, dict) and web_data.get("success"):
                # 成功時: dataからllm_menuとrag_menuを取得
                data = web_data.get("data", {})
                
                # 斬新な提案（LLM）
                if 'llm_menu' in data:
                    response_parts.extend(self.format_llm_menu(data['llm_menu']))
                
                # 伝統的な提案（RAG）
                if 'rag_menu' in data:
                    response_parts.extend(self.format_rag_menu(data['rag_menu']))
            else:
                # エラー時またはデータ形式エラー
                response_parts.append("レシピデータの形式が正しくありません。")
                
        except Exception as e:
            self.logger.error(f"❌ [RecipeFormatter] format_web_recipesでエラー: {e}")
            response_parts.append("レシピデータの処理中にエラーが発生しました。")
        
        return response_parts
    
    def format_llm_menu(self, llm_menu: Dict[str, Any]) -> List[str]:
        """LLMメニューのフォーマット"""
        response_parts = []
        response_parts.append("🍽️ 斬新な提案")
        response_parts.append("")
        
        # 主菜
        if 'main_dish' in llm_menu and llm_menu['main_dish']:
            dish_text = self.format_dish_item(llm_menu['main_dish'], "主菜")
            response_parts.append(dish_text)
        
        # 副菜
        if 'side_dish' in llm_menu and llm_menu['side_dish']:
            dish_text = self.format_dish_item(llm_menu['side_dish'], "副菜")
            response_parts.append(dish_text)
        
        # 汁物
        if 'soup' in llm_menu and llm_menu['soup']:
            dish_text = self.format_dish_item(llm_menu['soup'], "汁物")
            response_parts.append(dish_text)
        else:
            response_parts.append("汁物:")
        
        response_parts.append("")
        return response_parts
    
    def format_rag_menu(self, rag_menu: Dict[str, Any]) -> List[str]:
        """RAGメニューのフォーマット"""
        response_parts = []
        response_parts.append("🍽️ 伝統的な提案")
        response_parts.append("")
        
        # 主菜
        if 'main_dish' in rag_menu and rag_menu['main_dish']:
            dish_text = self.format_dish_item(rag_menu['main_dish'], "主菜")
            response_parts.append(dish_text)
        
        # 副菜
        if 'side_dish' in rag_menu and rag_menu['side_dish']:
            dish_text = self.format_dish_item(rag_menu['side_dish'], "副菜")
            response_parts.append(dish_text)
        
        # 汁物
        if 'soup' in rag_menu and rag_menu['soup']:
            dish_text = self.format_dish_item(rag_menu['soup'], "汁物")
            response_parts.append(dish_text)
        else:
            response_parts.append("汁物:")
        
        response_parts.append("")
        return response_parts
    
    def format_dish_item(self, dish_data: Any, dish_type: str) -> str:
        """料理項目のフォーマット（共通処理）"""
        if isinstance(dish_data, str):
            return f"{dish_type}: {dish_data}"
        elif isinstance(dish_data, dict) and 'title' in dish_data:
            return f"{dish_type}: {dish_data['title']}"
        else:
            return f"{dish_type}:"
    
    def format_main_dish_proposals(self, data: Dict[str, Any]) -> List[str]:
        """主菜5件提案のフォーマット（主要食材考慮）"""
        response_parts = []
        
        try:
            if data.get("success"):
                candidates = data.get("data", {}).get("candidates", [])
                main_ingredient = data.get("data", {}).get("main_ingredient")
                llm_count = data.get("data", {}).get("llm_count", 0)
                rag_count = data.get("data", {}).get("rag_count", 0)
                
                # 主要食材の表示
                if main_ingredient:
                    response_parts.append(f"🍽️ **主菜の提案（5件）- {main_ingredient}使用**")
                else:
                    response_parts.append("🍽️ **主菜の提案（5件）**")
                response_parts.append("")
                
                # LLM提案（最初の2件）
                if llm_count > 0:
                    response_parts.append("💡 **斬新な提案（LLM推論）**")
                    for i, candidate in enumerate(candidates[:llm_count], 1):
                        title = candidate.get("title", "")
                        ingredients = ", ".join(candidate.get("ingredients", []))
                        response_parts.append(f"{i}. {title}")
                        response_parts.append(f"   使用食材: {ingredients}")
                        response_parts.append("")
                
                # RAG提案（残りの3件）
                if rag_count > 0:
                    response_parts.append("📚 **伝統的な提案（RAG検索）**")
                    start_idx = llm_count
                    for i, candidate in enumerate(candidates[start_idx:], start_idx + 1):
                        title = candidate.get("title", "")
                        ingredients = ", ".join(candidate.get("ingredients", []))
                        response_parts.append(f"{i}. {title}")
                        response_parts.append(f"   使用食材: {ingredients}")
                        response_parts.append("")
            else:
                # エラー時の表示
                error_msg = data.get("error", "不明なエラー")
                response_parts.append("❌ **主菜提案の取得に失敗しました**")
                response_parts.append("")
                response_parts.append(f"エラー: {error_msg}")
                response_parts.append("")
                response_parts.append("もう一度お試しください。")
                
        except Exception as e:
            self.logger.error(f"❌ [RecipeFormatter] format_main_dish_proposalsでエラー: {e}")
        return response_parts

