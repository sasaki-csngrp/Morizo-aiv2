"""
Morizo AI v2 - Recipe LLM Client

This module provides LLM-based recipe title generation functionality.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

from config.loggers import GenericLogger, log_prompt_with_tokens

# .envファイルを読み込み
load_dotenv()


class RecipeLLM:
    """LLM推論クライアント"""
    
    def __init__(self):
        self.logger = GenericLogger("mcp", "recipe_llm", initialize_logging=False)
        
        # 環境変数から設定を取得
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.temperature = float(os.getenv('OPENAI_TEMPERATURE', '0.8'))
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        
        # OpenAIクライアントを初期化
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        self.logger.debug(f"🤖 [LLM] Initialized")
        self.logger.debug(f"🔍 [LLM] Model: {self.model}, temperature: {self.temperature}")
    
    # 食材重複抑止機能
    # - プロンプト内で「食材の重複を避ける」と明示的に指示
    # - LLMが1回の推論で主菜・副菜・汁物の3品構成を生成
    # - 各料理間で食材の重複を避けるように設計
    # - 在庫食材を最大限活用し、バランスの良い献立構成を実現
    
    async def generate_menu_titles(
        self, 
        inventory_items: List[str], 
        menu_type: str,
        excluded_recipes: List[str] = None
    ) -> Dict[str, Any]:
        """
        LLM推論による独創的な献立タイトル生成
        
        Args:
            inventory_items: 在庫食材リスト
            menu_type: 献立のタイプ
            excluded_recipes: 除外するレシピタイトル
        
        Returns:
            生成された献立タイトルの候補リスト
        
        実装済み: 食材重複抑止機能
        - プロンプト内で「食材の重複を避ける」と明示的に指示（_build_menu_prompt参照）
        - 1回のLLM推論で主菜・副菜・汁物の3品構成を生成
        - 各料理間で食材が重複しないように設計されたプロンプトを使用
        - LLMの推論能力により、献立内の食材バランスを自動調整
        """
        try:
            self.logger.debug(f"🧠 [LLM] Generating menu titles")
            self.logger.debug(f"🔍 [LLM] Menu type: {menu_type}, ingredients count: {len(inventory_items)}")
            
            # プロンプトを構築
            prompt = self._build_menu_prompt(inventory_items, menu_type, excluded_recipes)
            
            # プロンプトロギング
            log_prompt_with_tokens(prompt, max_tokens=1000, logger_name="mcp.recipe_llm")
            
            # LLM呼び出し
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=1000
            )
            
            # レスポンスを解析
            menu_titles = self._parse_menu_response(response.choices[0].message.content)
            
            self.logger.debug(f"✅ [LLM] Generated menu titles")
            self.logger.debug(f"📊 [LLM] Generated {len(menu_titles)} menu titles")
            return {"success": True, "data": menu_titles}
            
        except Exception as e:
            self.logger.error(f"❌ [LLM] 献立タイトルの生成に失敗しました: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_menu_prompt(
        self, 
        inventory_items: List[str], 
        menu_type: str,
        excluded_recipes: List[str] = None
    ) -> str:
        """献立生成用のプロンプトを構築"""
        
        excluded_text = ""
        if excluded_recipes:
            excluded_text = f"\n除外するレシピ: {', '.join(excluded_recipes)}"
        
        prompt = f"""
在庫食材: {', '.join(inventory_items)}
献立タイプ: {menu_type}{excluded_text}

以下の条件で独創的な献立タイトルを生成してください:
1. 主菜・副菜・汁物の3品構成
2. 在庫食材のみを使用
3. 食材の重複を避ける
4. 独創的で新しいレシピタイトル
5. 除外レシピは使用しない

重要: 具体的な調理手順は生成せず、レシピタイトルのみを生成してください。
例: "牛乳と卵のフレンチトースト"、"ほうれん草の胡麻和え"

以下のJSON形式で回答してください:
{{
    "main_dish": {{
        "title": "主菜のタイトル",
        "ingredients": ["主菜で使用する食材1", "主菜で使用する食材2", ...]
    }},
    "side_dish": {{
        "title": "副菜のタイトル",
        "ingredients": ["副菜で使用する食材1", "副菜で使用する食材2", ...]
    }},
    "soup": {{
        "title": "汁物のタイトル",
        "ingredients": ["汁物で使用する食材1", "汁物で使用する食材2", ...]
    }},
    "ingredients_used": ["献立全体で使用する食材1", "献立全体で使用する食材2", ...]
}}

注意: 各レシピ（main_dish, side_dish, soup）には、そのレシピで実際に使用する食材のみをingredientsに含めてください。
ingredients_usedは献立全体で使用される食材のリストです。

生成する献立:
"""
        return prompt
    
    def _parse_menu_response(self, response_content: str) -> Dict[str, Any]:
        """LLMレスポンスを解析して献立タイトルを抽出"""
        try:
            import json
            import re
            
            # デバッグ: レスポンス内容をログに記録
            self.logger.debug(f"🔍 [LLM] Parsing response content (length: {len(response_content)}): {response_content[:1000]}")
            
            # まず、マークダウンコードブロック内のJSONを抽出
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    menu_data = json.loads(json_str.strip())
                    self.logger.debug(f"✅ [LLM] Successfully parsed JSON from markdown code block")
                    return self._extract_menu_data(menu_data)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"⚠️ [LLM] マークダウンブロックからのJSON解析に失敗しました: {e}")
            
            # マークダウンコードブロックがない場合、直接JSONを探す（より寛容な正規表現）
            # ネストされたオブジェクトにも対応
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    menu_data = json.loads(json_str.strip())
                    self.logger.debug(f"✅ [LLM] Successfully parsed JSON from direct match")
                    return self._extract_menu_data(menu_data)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"⚠️ [LLM] 直接マッチからのJSON解析に失敗しました: {e}")
            
            # 通常のJSON解析を試行
            try:
                menu_data = json.loads(response_content.strip())
                self.logger.debug(f"✅ [LLM] Successfully parsed JSON from full content")
                return self._extract_menu_data(menu_data)
            except json.JSONDecodeError as e:
                self.logger.warning(f"⚠️ [LLM] 全コンテンツからのJSON解析に失敗しました: {e}")
            
            # すべてのJSON解析に失敗した場合、テキストから抽出を試行
            self.logger.warning(f"⚠️ [LLM] すべてのJSON解析試行が失敗しました。テキスト抽出を試行します")
            self.logger.debug(f"🔍 [LLM] Response content (first 1000 chars): {response_content[:1000]}")
            return self._extract_from_text(response_content)
            
        except Exception as e:
            self.logger.error(f"❌ [LLM] レスポンスの解析に失敗しました: {e}")
            self.logger.debug(f"🔍 [LLM] Response content (first 1000 chars): {response_content[:1000]}")
            return {"main_dish": "", "side_dish": "", "soup": "", "main_dish_ingredients": [], "side_dish_ingredients": [], "soup_ingredients": [], "ingredients_used": []}
    
    def _extract_menu_data(self, menu_data: Dict[str, Any]) -> Dict[str, Any]:
        """menu_dataから献立情報を抽出（新旧形式対応）"""
        # 新しい形式（各レシピがオブジェクト）をチェック
        main_dish_data = menu_data.get("main_dish", {})
        side_dish_data = menu_data.get("side_dish", {})
        soup_data = menu_data.get("soup", {})
        
        # 新しい形式か既存形式かを判定
        is_new_format = (
            isinstance(main_dish_data, dict) and "title" in main_dish_data
        ) or (
            isinstance(side_dish_data, dict) and "title" in side_dish_data
        ) or (
            isinstance(soup_data, dict) and "title" in soup_data
        )
        
        if is_new_format:
            # 新しい形式: 各レシピがオブジェクト
            return {
                "main_dish": main_dish_data.get("title", "") if isinstance(main_dish_data, dict) else str(main_dish_data),
                "side_dish": side_dish_data.get("title", "") if isinstance(side_dish_data, dict) else str(side_dish_data),
                "soup": soup_data.get("title", "") if isinstance(soup_data, dict) else str(soup_data),
                "main_dish_ingredients": main_dish_data.get("ingredients", []) if isinstance(main_dish_data, dict) else [],
                "side_dish_ingredients": side_dish_data.get("ingredients", []) if isinstance(side_dish_data, dict) else [],
                "soup_ingredients": soup_data.get("ingredients", []) if isinstance(soup_data, dict) else [],
                "ingredients_used": menu_data.get("ingredients_used", [])
            }
        else:
            # 既存形式: 各レシピが文字列
            return {
                "main_dish": str(main_dish_data) if main_dish_data else "",
                "side_dish": str(side_dish_data) if side_dish_data else "",
                "soup": str(soup_data) if soup_data else "",
                "main_dish_ingredients": [],
                "side_dish_ingredients": [],
                "soup_ingredients": [],
                "ingredients_used": menu_data.get("ingredients_used", [])
            }
    
    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """テキストから献立タイトルを抽出（フォールバック）"""
        import re
        import json
        
        main_dish = ""
        side_dish = ""
        soup = ""
        main_dish_ingredients = []
        side_dish_ingredients = []
        soup_ingredients = []
        ingredients = []
        
        # パターン1: 新しい形式 "main_dish": {"title": "...", "ingredients": [...]} を試行
        main_dish_obj_match = re.search(r'"main_dish"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', text, re.IGNORECASE | re.DOTALL)
        if main_dish_obj_match:
            main_dish = main_dish_obj_match.group(1)
            # ingredientsも抽出
            main_ingredients_match = re.search(r'"main_dish"\s*:\s*\{[^}]*"ingredients"\s*:\s*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL)
            if main_ingredients_match:
                ingredients_str = main_ingredients_match.group(1)
                main_dish_ingredients = re.findall(r'"([^"]+)"', ingredients_str)
        
        side_dish_obj_match = re.search(r'"side_dish"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', text, re.IGNORECASE | re.DOTALL)
        if side_dish_obj_match:
            side_dish = side_dish_obj_match.group(1)
            side_ingredients_match = re.search(r'"side_dish"\s*:\s*\{[^}]*"ingredients"\s*:\s*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL)
            if side_ingredients_match:
                ingredients_str = side_ingredients_match.group(1)
                side_dish_ingredients = re.findall(r'"([^"]+)"', ingredients_str)
        
        soup_obj_match = re.search(r'"soup"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', text, re.IGNORECASE | re.DOTALL)
        if soup_obj_match:
            soup = soup_obj_match.group(1)
            soup_ingredients_match = re.search(r'"soup"\s*:\s*\{[^}]*"ingredients"\s*:\s*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL)
            if soup_ingredients_match:
                ingredients_str = soup_ingredients_match.group(1)
                soup_ingredients = re.findall(r'"([^"]+)"', ingredients_str)
        
        # パターン2: 既存形式 "main_dish": "タイトル" 形式（JSONライク）
        if not main_dish:
            main_match = re.search(r'"main_dish"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            if main_match:
                main_dish = main_match.group(1)
        
        if not side_dish:
            side_match = re.search(r'"side_dish"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            if side_match:
                side_dish = side_match.group(1)
        
        if not soup:
            soup_match = re.search(r'"soup"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            if soup_match:
                soup = soup_match.group(1)
        
        # パターン3: 主菜: タイトル 形式（コロン区切り）
        if not main_dish:
            main_match = re.search(r'主菜[：:]\s*([^\n]+)', text)
            if main_match:
                main_dish = main_match.group(1).strip()
        
        if not side_dish:
            side_match = re.search(r'副菜[：:]\s*([^\n]+)', text)
            if side_match:
                side_dish = side_match.group(1).strip()
        
        if not soup:
            soup_match = re.search(r'汁物[：:]\s*([^\n]+)', text)
            if soup_match:
                soup = soup_match.group(1).strip()
        
        # パターン4: 行ベースの解析（"主菜"という単語を含む行を探す）
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            # 「主菜」を含み、既に見つかっていない場合
            if "主菜" in line and not main_dish:
                # コロンやダッシュの後の部分を抽出
                match = re.search(r'主菜[：:\-]\s*([^\n]+)', line)
                if match:
                    main_dish = match.group(1).strip()
                else:
                    # コロンがない場合、"主菜"の後の部分を抽出
                    main_dish = re.sub(r'^.*主菜\s*', '', line).strip()
            
            if "副菜" in line and not side_dish:
                match = re.search(r'副菜[：:\-]\s*([^\n]+)', line)
                if match:
                    side_dish = match.group(1).strip()
                else:
                    side_dish = re.sub(r'^.*副菜\s*', '', line).strip()
            
            if "汁物" in line and not soup:
                match = re.search(r'汁物[：:\-]\s*([^\n]+)', line)
                if match:
                    soup = match.group(1).strip()
                else:
                    soup = re.sub(r'^.*汁物\s*', '', line).strip()
        
        # ingredients_usedの抽出を試行
        ingredients_match = re.search(r'"ingredients_used"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ingredients_match:
            ingredients_str = ingredients_match.group(1)
            # 各食材を抽出
            ingredient_matches = re.findall(r'"([^"]+)"', ingredients_str)
            ingredients = ingredient_matches
        
        self.logger.info(f"📝 [LLM] Extracted from text - main_dish: '{main_dish}', side_dish: '{side_dish}', soup: '{soup}'")
        if main_dish_ingredients or side_dish_ingredients or soup_ingredients:
            self.logger.info(f"📝 [LLM] Extracted ingredients - main: {main_dish_ingredients}, side: {side_dish_ingredients}, soup: {soup_ingredients}")
        
        return {
            "main_dish": main_dish,
            "side_dish": side_dish,
            "soup": soup,
            "main_dish_ingredients": main_dish_ingredients,
            "side_dish_ingredients": side_dish_ingredients,
            "soup_ingredients": soup_ingredients,
            "ingredients_used": ingredients
        }
    
    async def generate_main_dish_candidates(
        self, 
        inventory_items: List[str], 
        menu_type: str,
        main_ingredient: str = None,  # 主要食材
        excluded_recipes: List[str] = None,
        count: int = 2
    ) -> Dict[str, Any]:
        """
        主菜候補を複数件生成（主要食材考慮）
        
        後方互換性のため、汎用メソッド `generate_candidates()` を内部で呼び出します。
        """
        return await self.generate_candidates(
            inventory_items=inventory_items,
            menu_type=menu_type,
            category="main",
            main_ingredient=main_ingredient,
            used_ingredients=None,
            excluded_recipes=excluded_recipes,
            count=count
        )

    def _parse_main_dish_response(self, response_content: str) -> List[Dict[str, Any]]:
        """LLMレスポンスを解析して主菜候補を抽出"""
        try:
            import json
            import re
            
            # JSON部分を抽出
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("candidates", [])
            
            return []
        except Exception as e:
            self.logger.error(f"❌ [LLM] Failed to parse main dish response: {e}")
            return []

    async def generate_candidates(
        self, 
        inventory_items: List[str], 
        menu_type: str,
        category: str,  # "main", "sub", "soup", "other"
        main_ingredient: str = None,
        used_ingredients: List[str] = None,  # 副菜・汁物用（主菜で使った食材）
        excluded_recipes: List[str] = None,
        count: int = 2,
        category_detail_keyword: str = None  # otherカテゴリ用
    ) -> Dict[str, Any]:
        """
        汎用候補生成メソッド（主菜・副菜・汁物・その他対応）
        
        Args:
            category: "main", "sub", "soup", "other"
            used_ingredients: すでに使った食材（副菜・汁物で主菜で使った食材を除外）
            inventory_items: 在庫食材リスト
            menu_type: 献立タイプ
            main_ingredient: 主要食材（主菜の場合のみ）
            excluded_recipes: 除外レシピ
            count: 生成件数
            category_detail_keyword: category_detailのキーワード（otherカテゴリ用）
        """
        try:
            # カテゴリ別のプロンプトを構築
            prompt = self._build_candidate_prompt(
                inventory_items, menu_type, category,
                main_ingredient, used_ingredients, excluded_recipes, count,
                category_detail_keyword
            )
            
            self.logger.debug(f"🤖 [LLM] Generating {category} candidates")
            self.logger.debug(f"🔍 [LLM] Count: {count}")
            
            # プロンプトロギング
            log_prompt_with_tokens(prompt, max_tokens=1000, logger_name="mcp.recipe_llm")
            
            # LLM呼び出し
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=1000
            )
            
            # レスポンスを解析
            candidates = self._parse_candidate_response(response.choices[0].message.content)
            
            self.logger.debug(f"✅ [LLM] Generated {category} candidates")
            self.logger.debug(f"📊 [LLM] Generated {len(candidates)} {category} candidates")
            return {"success": True, "data": {"candidates": candidates}}
            
        except Exception as e:
            self.logger.error(f"❌ [LLM] {category} 候補の生成に失敗しました: {e}")
            return {"success": False, "error": str(e)}

    def _build_candidate_prompt(
        self,
        inventory_items: List[str], 
        menu_type: str,
        category: str,
        main_ingredient: str = None,
        used_ingredients: List[str] = None,
        excluded_recipes: List[str] = None,
        count: int = 2,
        category_detail_keyword: str = None
    ) -> str:
        """カテゴリ別の候補生成プロンプトを構築"""
        
        # カテゴリ別のメニュー名
        menu_name_map = {
            "main": "主菜",
            "sub": "副菜",
            "soup": "汁物",
            "other": "その他"
        }
        menu_name = menu_name_map.get(category, "料理")
        
        # 主要食材指定（主菜の場合のみ）
        main_ingredient_text = ""
        if main_ingredient and category == "main":
            main_ingredient_text = f"\n重要: {main_ingredient}を必ず使用してください。"
        
        # 使い残し食材の指定（副菜・汁物）
        used_ingredients_text = ""
        if used_ingredients:
            used_ingredients_text = f"\n重要: 以下の食材は既に使用済みです。これらの食材は使用しないでください。: {', '.join(used_ingredients)}"
        
        # 除外レシピ
        excluded_text = ""
        if excluded_recipes:
            excluded_text = f"\n除外レシピ（提案しないでください）: {', '.join(excluded_recipes)}"
        
        # category_detail_keywordの指定（otherカテゴリ用）
        category_detail_text = ""
        if category_detail_keyword and category == "other":
            # category_detail_keywordから具体的なカテゴリ名を抽出
            if "麺もの" in category_detail_keyword:
                category_detail_text = "\n重要: 麺もの（うどん、そば、ラーメン、そうめんなど）のレシピを提案してください。"
            elif "パスタ" in category_detail_keyword:
                category_detail_text = "\n重要: パスタのレシピを提案してください。"
            elif "丼" in category_detail_keyword or "ご飯もの" in category_detail_keyword:
                category_detail_text = "\n重要: ご飯もの（丼物、チャーハン、カレーライスなど）のレシピを提案してください。"
            else:
                category_detail_text = f"\n重要: {category_detail_keyword}のレシピを提案してください。"
        
        # 条件5のテキストを生成（f-string内でバックスラッシュを使えないため、事前に処理）
        condition_5_text = ""
        if category_detail_text:
            # バックスラッシュを含む文字列リテラルを変数に代入
            newline_important = "\n重要: "
            period = "。"
            cleaned_text = category_detail_text.replace(newline_important, "").replace(period, "")
            condition_5_text = f"5. {cleaned_text}のレシピであること"
        
        prompt = f"""
在庫食材: {', '.join(inventory_items)}
献立タイプ: {menu_type}{main_ingredient_text}{used_ingredients_text}{excluded_text}{category_detail_text}

以下の条件で{menu_name}のタイトルを{count}件生成してください:
1. 在庫食材のみを使用
2. 独創的で新しいレシピタイトル
3. 除外レシピは絶対に使用しない
4. 各提案に使用食材リスト（ingredients）を必ず含める（必須項目）
{condition_5_text}

重要: 各候補には必ず"ingredients"フィールドを含め、在庫食材から使用する食材名のリストを記載してください。

以下のJSON形式で回答してください:
{{
    "candidates": [
        {{"title": "{menu_name}タイトル1", "ingredients": ["食材1", "食材2"]}},
        {{"title": "{menu_name}タイトル2", "ingredients": ["食材1", "食材3"]}}
    ]
}}
"""
        return prompt

    def _parse_candidate_response(self, response_content: str) -> List[Dict[str, Any]]:
        """LLMレスポンスを解析して候補を抽出（汎用版）"""
        try:
            import json
            import re
            
            # JSON部分を抽出
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                candidates = data.get("candidates", [])
                
                # デバッグログ: LLMレスポンスのJSON構造を確認
                self.logger.debug(f"🔍 [LLM] Parsed {len(candidates)} candidates from LLM response")
                
                # ingredientsが含まれていることを確認
                for i, candidate in enumerate(candidates):
                    if "ingredients" not in candidate:
                        self.logger.warning(f"⚠️ [LLM] Candidate {i+1} ('{candidate.get('title', 'N/A')}') missing 'ingredients' field, setting to empty list")
                        candidate["ingredients"] = []  # デフォルト値
                    else:
                        ingredients = candidate.get("ingredients", [])
                        self.logger.debug(f"✅ [LLM] Candidate {i+1} ('{candidate.get('title', 'N/A')}') has {len(ingredients)} ingredients: {ingredients}")
                
                return candidates
            
            self.logger.warning(f"⚠️ [LLM] No JSON found in LLM response")
            return []
        except Exception as e:
            self.logger.error(f"❌ [LLM] 候補レスポンスの解析に失敗しました: {e}")
            return []


if __name__ == "__main__":
    print("✅ Recipe LLM module loaded successfully")
