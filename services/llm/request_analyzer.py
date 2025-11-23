#!/usr/bin/env python3
"""
RequestAnalyzer - リクエスト分析

プロンプト肥大化問題を解決するため、リクエストを事前分析する。
パターンマッチング方式でリクエストを判定し、必要な情報を抽出する。
"""

from typing import Dict, Any, List, Optional
import re
from config.loggers import GenericLogger


class RequestAnalyzer:
    """リクエスト分析クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.request_analyzer")
    
    def analyze(
        self, 
        request: str, 
        user_id: str, 
        sse_session_id: str = None, 
        session_context: dict = None
    ) -> Dict[str, Any]:
        """
        リクエストを分析してパターンとパラメータを抽出
        
        Args:
            request: ユーザーリクエスト
            user_id: ユーザーID
            sse_session_id: SSEセッションID
            session_context: セッションコンテキスト
        
        Returns:
            {
                "pattern": str,  # パターン種別
                "params": dict,  # 抽出されたパラメータ
                "ambiguities": list  # 曖昧性リスト
            }
        """
        try:
            self.logger.debug(f"🔍 [RequestAnalyzer] Analyzing request: '{request}'")
            
            # セッションコンテキストのデフォルト値
            if session_context is None:
                session_context = {}
            
            # 1. パターン判定
            pattern = self._detect_pattern(request, sse_session_id, session_context)
            
            # 2. パラメータ抽出
            params = self._extract_params(request, pattern, user_id, session_context)
            
            # 3. 曖昧性チェック
            ambiguities = self._check_ambiguities(pattern, params, sse_session_id, session_context)
            
            result = {
                "pattern": pattern,
                "params": params,
                "ambiguities": ambiguities
            }
            
            self.logger.debug(f"✅ [RequestAnalyzer] Analysis result: pattern={pattern}, ambiguities={len(ambiguities)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ [RequestAnalyzer] Error in analyze: {e}")
            raise
    
    def _detect_pattern(
        self, 
        request: str, 
        sse_session_id: str, 
        session_context: dict
    ) -> str:
        """
        パターン判定（優先順位順にチェック）
        
        Returns:
            pattern: パターン種別
        """
        # 優先度1: 曖昧性解消後の再開
        if self._is_ambiguity_resume(session_context):
            return "ambiguity_resume"
        
        # 優先度2: 追加提案（判定順を 汁物→副菜→主菜→other に変更して誤判定を抑止）
        if self._is_additional_proposal(request, sse_session_id):
            # 汁物を最優先（説明文に主菜/副菜が含まれていても汁物指定を優先）
            if ("汁物" in request or "スープ" in request or "味噌汁" in request or "soup" in request.lower()):
                return "soup_additional"
            # 副菜を次に優先（「主菜で使っていない食材で副菜…」などのケースに対応）
            elif ("副菜" in request or "サブ" in request or "sub" in request.lower()):
                return "sub_additional"
            # otherカテゴリの追加提案をチェック（主菜より優先）
            elif self._is_other_category_request(request):
                return "other_additional"
            # 最後に主菜
            elif ("主菜" in request or "メイン" in request or "main" in request.lower()):
                return "main_additional"
        
        # 優先度3: カテゴリ提案（初回）
        # 注意: 説明文中の「主菜・副菜」などに反応しないよう、汁物・副菜を優先的にチェック
        # 汁物のチェック（最優先：説明文に「主菜・副菜」が含まれる可能性があるため）
        if ("汁物を" in request or "汁物が" in request or "汁物の" in request or 
            "スープを" in request or "スープが" in request or "スープの" in request or
            "味噌汁を" in request or "味噌汁が" in request or "味噌汁の" in request or
            "soup" in request.lower()):
            return "soup"
        # 副菜のチェック（主菜より優先：説明文に「主菜で使っていない」などが含まれる可能性があるため）
        elif ("副菜を" in request or "副菜が" in request or "副菜の" in request or
              "サブを" in request or "sub" in request.lower()):
            return "sub"
        # 主菜のチェック（最後：より具体的な文脈を優先）
        elif ("主菜を" in request or "主菜が" in request or "主菜の" in request or
              "主菜で" in request or "メインを" in request or "メインが" in request or
              "main" in request.lower() or "主菜" in request or "メイン" in request):
            return "main"
        
        # 優先度3.5: otherカテゴリの検出（主菜・副菜・汁物の後、献立生成の前）
        if self._is_other_category_request(request):
            return "other"
        
        # 優先度4: 在庫操作
        if self._is_inventory_operation(request):
            return "inventory"
        
        # 優先度5: 献立生成
        if "献立" in request or "メニュー" in request or "menu" in request.lower():
            return "menu"
        
        # 優先度5.5: 挨拶
        if self._is_greeting(request):
            return "greeting"
        
        # 優先度6: その他
        return "other"
    
    def _is_ambiguity_resume(self, session_context: dict) -> bool:
        """曖昧性解消後の再開判定"""
        # TODO: セッションに確認待ち状態が存在する場合にTrueを返す
        return session_context.get("waiting_confirmation", False)
    
    def _is_additional_proposal(self, request: str, sse_session_id: str) -> bool:
        """追加提案の判定"""
        if not sse_session_id:
            return False
        
        # 「その他」カテゴリのリクエスト（「その他のレシピを教えて」など）は追加提案と判定しない
        # 「その他のレシピをもう5件」などは追加提案として判定される
        if "その他のレシピ" in request or "その他を" in request or "その他が" in request:
            # 「もう」「もっと」などの追加提案キーワードが含まれている場合のみ追加提案と判定
            additional_keywords = ["もう", "もっと", "追加", "あと", "さらに"]
            return any(keyword in request for keyword in additional_keywords)
        
        additional_keywords = ["もう", "他の", "もっと", "追加", "あと", "さらに"]
        return any(keyword in request for keyword in additional_keywords)
    
    def _is_inventory_operation(self, request: str) -> bool:
        """在庫操作の判定"""
        inventory_keywords = ["追加", "削除", "更新", "変えて", "変更", "確認", "在庫"]
        return any(keyword in request for keyword in inventory_keywords)
    
    def _is_greeting(self, request: str) -> bool:
        """挨拶の判定"""
        request_lower = request.lower()
        
        # まず、「その他」カテゴリのリクエストでないことを確認
        # 「その他」カテゴリのリクエストを挨拶と誤判定しないようにする
        if self._is_other_category_request(request):
            return False
        
        # 一般的な挨拶キーワード
        greeting_keywords = [
            "こんにちは", "こんばんは", "おはよう", "おはようございます",
            "お疲れ様", "お疲れさま", "おつかれさま",
            "ありがとう", "ありがとうございます", "どうもありがとう",
            "すみません", "ごめんなさい", "ごめん",
            "やあ", "どうも", "よろしく", "よろしくお願いします",
            "はじめまして", "初めまして",
            "さようなら", "さよなら", "バイバイ",
            "おやすみ", "おやすみなさい",
            "hello", "hi", "hey", "thanks", "thank you", "sorry"
        ]
        
        # 料理関連のキーワード（挨拶と判定しないようにする）
        cooking_keywords = [
            "レシピ", "料理", "献立", "メニュー", "主菜", "副菜", "汁物",
            "在庫", "食材", "追加", "削除", "更新", "提案", "教えて",
            "その他", "その他の", "麺", "パスタ", "丼", "チャーハン",
            "カレー", "おにぎり", "オムライス", "うどん", "そば", "ラーメン"
        ]
        
        # 料理関連のキーワードが含まれている場合は挨拶と判定しない
        has_cooking_keyword = any(keyword in request for keyword in cooking_keywords)
        if has_cooking_keyword:
            return False
        
        # リクエストが短く、挨拶キーワードのみを含む場合
        request_stripped = request.strip()
        if len(request_stripped) <= 20:  # 短いリクエストの場合
            if any(keyword in request for keyword in greeting_keywords):
                return True
        
        # リクエストが挨拶のみで構成されている場合（料理関連キーワードがなく、挨拶キーワードを含む）
        if any(keyword in request for keyword in greeting_keywords):
            return True
        
        return False
    
    def _is_other_category_request(self, request: str) -> bool:
        """otherカテゴリのリクエストかどうかを判定"""
        request_lower = request.lower()
        
        # カテゴリ全体のキーワード
        if any(keyword in request for keyword in ["その他のレシピ", "その他を", "その他が", "その他の"]):
            return True
        
        # ご飯もの系のキーワード
        if any(keyword in request for keyword in [
            "丼のレシピ", "丼を", "丼が", "丼物",
            "チャーハン", "カレーライス", "おにぎり", "オムライス",
            "雑炊", "リゾット", "寿司", "ドリア", "パエリア", "ハヤシライス"
        ]):
            return True
        
        # 麺もの系のキーワード
        if any(keyword in request for keyword in [
            "麺もの", "麺のレシピ", "麺を", "麺が",
            "うどん", "そば", "そうめん", "焼きそば",
            "中華麺", "ラーメン", "ビーフン"
        ]):
            return True
        
        # パスタ系のキーワード
        if any(keyword in request for keyword in [
            "パスタ", "カルボナーラ", "ミートソース", "ナポリタン",
            "ペペロンチーノ", "たらこパスタ", "明太子パスタ"
        ]):
            return True
        
        # その他のキーワード
        if any(keyword in request for keyword in [
            "ソース", "ドレッシング", "たれ",
            "鍋", "ホットプレート", "粉もの", "チヂミ",
            "ハンバーグ", "グラタン", "おでん", "シチュー"
        ]):
            return True
        
        return False
    
    def _extract_category_detail_keyword(self, request: str) -> Optional[str]:
        """リクエストからcategory_detailのキーワードを抽出"""
        # 麺もの系
        if "うどん" in request:
            return "麺ものうどん"
        elif "そば" in request and "パスタ" not in request:
            return "麺ものそば"
        elif "そうめん" in request:
            return "麺ものそうめん"
        elif "焼きそば" in request:
            return "麺もの焼きそば"
        elif "中華麺" in request or "ラーメン" in request:
            return "麺もの中華麺"
        
        # パスタ系
        elif "カルボナーラ" in request:
            return "パスタカルボナーラ"
        elif "ミートソース" in request:
            return "パスタミートソース"
        elif "ナポリタン" in request:
            return "パスタナポリタン"
        elif "トマト" in request and "パスタ" in request:
            return "パスタトマト系"
        elif "パスタ" in request:
            return "パスタ"  # 汎用的なパスタ
        
        # ご飯もの系
        elif "丼" in request:
            return "ご飯もの丼物"
        elif "チャーハン" in request:
            return "ご飯ものチャーハン"
        elif "カレー" in request:
            return "ご飯ものカレーライス"
        elif "おにぎり" in request:
            return "ご飯ものおにぎり"
        
        return None
    
    def _extract_params(
        self, 
        request: str, 
        pattern: str, 
        user_id: str, 
        session_context: dict
    ) -> Dict[str, Any]:
        """パラメータ抽出"""
        params = {
            "user_id": user_id,
            "user_request": request  # user_request を params に追加
        }
        
        # カテゴリ提案の場合
        if pattern in ["main", "sub", "soup", "other", "main_additional", "sub_additional", "soup_additional", "other_additional"]:
            # カテゴリ設定
            category_map = {
                "main": "main",
                "sub": "sub",
                "soup": "soup",
                "other": "other",
                "main_additional": "main",
                "sub_additional": "sub",
                "soup_additional": "soup",
                "other_additional": "other"
            }
            params["category"] = category_map[pattern]
            
            # 主要食材抽出
            if pattern in ["main", "main_additional"]:
                params["main_ingredient"] = self._extract_ingredient(request)
            else:
                params["main_ingredient"] = None
            
            # 使用済み食材（セッションから取得）
            # otherカテゴリは単体動作のため、used_ingredientsは使用しない
            if pattern in ["sub", "soup", "sub_additional", "soup_additional"]:
                params["used_ingredients"] = session_context.get("used_ingredients", [])
            else:
                params["used_ingredients"] = None
            
            # 汁物の献立カテゴリ判定
            if pattern in ["soup", "soup_additional"]:
                params["menu_category"] = session_context.get("menu_category", "japanese")
            else:
                params["menu_category"] = None
            
            # otherカテゴリの場合、category_detail_keywordを抽出
            if pattern in ["other", "other_additional"]:
                # 追加提案の場合はセッションコンテキストから取得を試みる
                if pattern == "other_additional":
                    params["category_detail_keyword"] = session_context.get("category_detail_keyword") or self._extract_category_detail_keyword(request)
                else:
                    params["category_detail_keyword"] = self._extract_category_detail_keyword(request)
            else:
                params["category_detail_keyword"] = None
        
        return params
    
    def _extract_ingredient(self, request: str) -> Optional[str]:
        """主要食材の抽出（簡易版）"""
        # パターン1: 「○○の主菜」「○○で主菜」「○○を使った主菜」
        match = re.search(r'([ぁ-ん一-龥ァ-ヴー]+?)(の|で|を使った)(主菜|副菜|汁物|メイン|サブ|スープ)', request)
        if match:
            return match.group(1)
        
        # パターン2: 「○○主菜」（スペースなし）
        match = re.search(r'([ぁ-ん一-龥ァ-ヴー]{2,})(主菜|副菜|汁物|メイン|サブ|スープ)', request)
        if match:
            return match.group(1)
        
        # パターン3: 「○○を主菜に」「○○でメインを」
        match = re.search(r'([ぁ-ん一-龥ァ-ヴー]+?)(を|で)(主菜|メイン)', request)
        if match:
            return match.group(1)
        
        # パターン4: 「○○で味噌汁を作りたい」「○○でスープを」
        match = re.search(r'([ぁ-ん一-龥ァ-ヴー]+?)(で)(味噌汁|スープ)', request)
        if match:
            return match.group(1)
        
        return None
    
    def _check_ambiguities(
        self, 
        pattern: str, 
        params: dict, 
        sse_session_id: str, 
        session_context: dict
    ) -> List[Dict[str, Any]]:
        """曖昧性チェック"""
        ambiguities = []
        
        # 主菜提案で main_ingredient 未指定
        if pattern == "main" and not params.get("main_ingredient"):
            ambiguities.append({
                "type": "missing_main_ingredient",
                "question": "何か食材を指定しますか？それとも在庫から提案しますか？",
                "options": ["食材を指定する", "在庫から提案する"]
            })
        
        # 追加提案で sse_session_id 不在
        if pattern in ["main_additional", "sub_additional", "soup_additional"] and not sse_session_id:
            # 曖昧性ではなく、初回提案に切り替え
            # ここでは特に処理しない（呼び出し側で対応）
            pass
        
        # 副菜提案で used_ingredients 不在
        if pattern == "sub" and not params.get("used_ingredients"):
            ambiguities.append({
                "type": "missing_used_ingredients",
                "question": "まず主菜を選択しますか？それとも副菜のみ提案しますか？",
                "options": ["主菜から選ぶ", "副菜のみ提案"]
            })
        
        # 汁物提案で used_ingredients 不在
        if pattern == "soup" and not params.get("used_ingredients"):
            # デフォルトで和食（味噌汁）を提案
            # 曖昧性を設けない
            pass
        
        return ambiguities

