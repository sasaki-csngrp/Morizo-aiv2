#!/usr/bin/env python3
"""
UserResponseParser - ユーザー応答解析

ユーザーの入力を解析し、意図を判定するロジックを提供
ConfirmationServiceから分離された責任
"""

import re
from typing import Dict, Any, List, Optional
from config.loggers import GenericLogger


class UserResponseParser:
    """ユーザー応答解析クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "response_parser")
    
    def parse_response(self, user_response: str) -> Dict[str, Any]:
        """
        ユーザー応答の解析（キーワードマッチング強化版）
        
        Args:
            user_response: ユーザー応答
        
        Returns:
            解析結果
        """
        try:
            self.logger.info(f"🔧 [UserResponseParser] Parsing user response")
            
            # 1. キャンセル判定（強化版）
            is_cancelled = self.check_cancellation(user_response)
            
            # 2. 戦略判定（強化版）
            strategy = self.determine_strategy(user_response)
            
            # 3. 追加パラメータ抽出
            additional_params = self.extract_additional_params(user_response)
            
            parsed_response = {
                "is_cancelled": is_cancelled,
                "strategy": strategy,
                "additional_params": additional_params,
                "raw_response": user_response
            }
            
            self.logger.info(f"✅ [UserResponseParser] User response parsed successfully")
            
            return parsed_response
            
        except Exception as e:
            self.logger.error(f"❌ [UserResponseParser] Error in parse_response: {e}")
            return {"is_cancelled": True, "strategy": "by_id", "raw_response": user_response}
    
    def check_cancellation(self, user_response: str) -> bool:
        """
        キャンセル判定（強化版）
        
        Args:
            user_response: ユーザー応答
        
        Returns:
            キャンセル判定結果
        """
        # より多くのキャンセルキーワードを追加
        cancel_keywords = [
            "キャンセル", "やめる", "中止", "止める", "やめ", 
            "やっぱり", "やっぱ", "やめとく", "やめときます",
            "やめます", "やめましょう", "やめよう", "やめようか",
            "やめ", "やめろ", "やめて", "やめない", "やめないで"
        ]
        
        return any(keyword in user_response for keyword in cancel_keywords)
    
    def determine_strategy(self, user_response: str) -> str:
        """
        戦略判定（強化版）
        
        Args:
            user_response: ユーザー応答
        
        Returns:
            戦略
        """
        # より詳細なキーワードマッチング
        latest_keywords = ["最新", "新しい", "一番新しい", "新", "最新の", "新しいの", "一番新"]
        oldest_keywords = ["古い", "古", "一番古い", "古いの", "古の", "一番古"]
        all_keywords = ["全部", "すべて", "全て", "全部の", "すべての", "全ての", "全部で", "すべてで"]
        id_keywords = ["ID", "id", "アイディー", "アイディ", "番号"]
        
        if any(keyword in user_response for keyword in latest_keywords):
            return "by_name_latest"
        elif any(keyword in user_response for keyword in oldest_keywords):
            return "by_name_oldest"
        elif any(keyword in user_response for keyword in all_keywords):
            return "by_name"
        elif any(keyword in user_response for keyword in id_keywords):
            return "by_id"
        else:
            # デフォルトは by_name（曖昧性チェック削除）
            return "by_name"
    
    def extract_additional_params(self, user_response: str) -> Dict[str, Any]:
        """
        追加パラメータの抽出
        
        Args:
            user_response: ユーザー応答
        
        Returns:
            追加パラメータ
        """
        additional_params = {}
        
        # 数量の抽出（正規表現使用）
        quantity_patterns = [
            r'(\d+)\s*個',
            r'(\d+)\s*本',
            r'(\d+)\s*枚',
            r'(\d+)\s*つ',
            r'(\d+)\s*パック',
            r'(\d+)\s*袋',
            r'(\d+)\s*箱',
            r'(\d+)\s*缶',
            r'(\d+)\s*瓶'
        ]
        
        for pattern in quantity_patterns:
            match = re.search(pattern, user_response)
            if match:
                additional_params["quantity"] = int(match.group(1))
                break
        
        return additional_params
    
    async def process_main_ingredient_confirmation(
        self,
        ambiguity_info: Dict[str, Any],
        user_response: str,
        original_tasks: List[Any]
    ) -> Dict[str, Any]:
        """主要食材選択の確認プロセス処理"""
        
        # パターン1: 指定せずに進める
        proceed_keywords = ["いいえ", "そのまま", "提案して", "在庫から", "このまま", "進めて", "指定しない", "2"]
        if any(keyword in user_response for keyword in proceed_keywords):
            self.logger.info(f"✅ [ResponseParser] User chose to proceed without specifying ingredient")
            return {
                "is_confirmed": True,
                "updated_tasks": original_tasks,  # main_ingredient: null のまま
                "message": "在庫から作れる主菜を提案します。"
            }
        
        # パターン2: 食材を指定する
        specify_keywords = ["はい", "指定", "1"]
        if any(keyword in user_response for keyword in specify_keywords):
            # 食材名を抽出（次のユーザー入力を待つ）
            self.logger.debug(f"🔍 [ResponseParser] User chose to specify ingredient")
            return {
                "is_confirmed": False,
                "updated_tasks": [],
                "message": "どの食材を使いたいですか？食材名を教えてください。",
                "needs_follow_up": True
            }
        
        # パターン3: 直接食材名を入力
        # 簡易的な食材認識（実際には既存の食材認識ロジックを活用）
        # ここでは、キーワードに該当しない場合は食材名として扱う
        if user_response and len(user_response) < 20:  # 短い入力は食材名の可能性
            specified_ingredient = user_response.strip()
            updated_tasks = self._update_task_with_main_ingredient(
                original_tasks,
                ambiguity_info.get("task_id"),
                specified_ingredient
            )
            self.logger.debug(f"✅ [ResponseParser] Ingredient specified: {specified_ingredient}")
            return {
                "is_confirmed": True,
                "updated_tasks": updated_tasks,
                "message": f"主要食材を「{specified_ingredient}」に設定しました。"
            }
        
        # パターン4: 認識できない応答
        self.logger.warning(f"⚠️ [ResponseParser] Could not understand response: {user_response}")
        return {
            "is_confirmed": False,
            "updated_tasks": [],
            "message": "すみません、理解できませんでした。食材名を指定するか、「そのまま提案して」とお答えください。"
        }

    def _update_task_with_main_ingredient(
        self, 
        tasks: List[Any], 
        task_id: str, 
        main_ingredient: str
    ) -> List[Any]:
        """主要食材を設定してタスクを更新"""
        updated_tasks = []
        
        for task in tasks:
            if task.id == task_id:
                # 主要食材を設定
                task.parameters["main_ingredient"] = main_ingredient
                updated_tasks.append(task)
            else:
                updated_tasks.append(task)
        
        return updated_tasks