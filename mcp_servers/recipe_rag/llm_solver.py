#!/usr/bin/env python3
"""
LLM制約解決機能

LLMを使用した食材重複抑止の制約解決機能を提供
"""

from typing import List, Dict, Any
from openai import AsyncOpenAI
from config.loggers import GenericLogger

logger = GenericLogger("mcp", "recipe_rag", initialize_logging=False)


class LLMConstraintSolver:
    """LLM制約解決エンジン"""
    
    def __init__(self, llm_client: AsyncOpenAI, llm_model: str):
        """初期化"""
        self.llm_client = llm_client
        self.llm_model = llm_model
    
    async def solve_menu_constraints_with_llm(
        self,
        menu_candidates: List[Dict[str, Any]],
        inventory_items: List[str],
        menu_type: str
    ) -> Dict[str, Any]:
        """
        LLMによる食材重複抑止の制約解決
        
        Args:
            menu_candidates: 複数の献立候補
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
        
        Returns:
            最適な献立選択結果
        """
        try:
            logger.info(f"🤖 [RAG] LLMで献立制約を解決中")
            logger.debug(f"🔍 [RAG] 候補数: {len(menu_candidates)}")
            
            # LLMプロンプトを生成
            prompt = self._create_constraint_solving_prompt(menu_candidates, inventory_items, menu_type)
            
            # LLMに問い合わせ
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  # 一貫性を重視
            )
            
            # レスポンスを解析
            selected_menu = self._parse_llm_menu_selection(response.choices[0].message.content)
            
            return selected_menu
            
        except Exception as e:
            logger.error(f"❌ [RAG] LLM制約解決エラー: {e}")
            logger.error(f"❌ [RAG] エラー詳細: {str(e)}")
            # エラー時は最初の候補を返す
            fallback = menu_candidates[0] if menu_candidates else {}
            logger.debug(f"🔄 [RAG] フォールバック献立を使用: {fallback}")
            return fallback
    
    def _create_constraint_solving_prompt(
        self,
        candidates: List[Dict[str, Any]],
        inventory_items: List[str],
        menu_type: str
    ) -> str:
        """
        制約解決用のLLMプロンプトを生成
        """
        candidates_text = ""
        for i, candidate in enumerate(candidates, 1):
            candidates_text += f"\n候補{i}:\n"
            candidates_text += f"  主菜: {candidate.get('main_dish', {}).get('title', '')} (食材: {candidate.get('main_dish', {}).get('ingredients', [])})\n"
            candidates_text += f"  副菜: {candidate.get('side_dish', {}).get('title', '')} (食材: {candidate.get('side_dish', {}).get('ingredients', [])})\n"
            candidates_text += f"  汁物: {candidate.get('soup', {}).get('title', '')} (食材: {candidate.get('soup', {}).get('ingredients', [])})\n"
        
        prompt = f"""
在庫食材: {inventory_items}
献立タイプ: {menu_type}

以下の複数の献立候補から、以下の条件で最適な組み合わせを選択してください:

1. 食材の重複を最小限に抑える
2. 在庫食材を最大限活用する
3. 栄養バランスが良い
4. {menu_type}らしい献立構成

候補献立:
{candidates_text}

以下のJSON形式で最適な献立を返してください（タイトルは元のレシピタイトルをそのまま使用してください）:
{{
    "main_dish": {{"title": "元のレシピタイトルそのまま", "ingredients": ["食材1", "食材2"]}},
    "side_dish": {{"title": "元のレシピタイトルそのまま", "ingredients": ["食材1", "食材2"]}},
    "soup": {{"title": "元のレシピタイトルそのまま", "ingredients": ["食材1", "食材2"]}},
    "selection_reason": "選択理由"
}}
"""
        return prompt
    
    def _parse_llm_menu_selection(self, llm_response: str) -> Dict[str, Any]:
        """
        LLMレスポンスから献立選択結果を解析
        """
        try:
            import json
            import re
            
            # JSON部分を抽出
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                
                result = json.loads(json_str)
                
                # 必要なフィールドが存在するかチェック
                required_fields = ["main_dish", "side_dish", "soup"]
                for field in required_fields:
                    if field not in result:
                        result[field] = {"title": "", "ingredients": []}
                
                return result
            else:
                return {}
                
        except Exception as e:
            logger.error(f"❌ [RAG] LLMレスポンスの解析に失敗: {e}")
            logger.error(f"❌ [RAG] レスポンス内容: {llm_response}")
            return {}
