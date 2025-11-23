#!/usr/bin/env python3
"""
PromptManager 基本クラス

パターン別にプロンプトを構築する統合クラス
"""

from typing import Dict, Any
from .patterns.inventory import build_inventory_prompt
from .patterns.menu import build_menu_prompt
from .patterns.main_proposal import build_main_proposal_prompt
from .patterns.sub_proposal import build_sub_proposal_prompt
from .patterns.soup_proposal import build_soup_proposal_prompt
from .patterns.other_proposal import build_other_proposal_prompt
from .patterns.additional_proposal import build_additional_proposal_prompt
from config.loggers import GenericLogger


def build_base_prompt_from_legacy(user_request: str, sse_session_id: str = None) -> str:
    """既存のbuild_planning_promptの内容を直接実装（循環参照回避）"""
    from .utils import build_base_prompt
    
    sse_info = ""
    if sse_session_id:
        sse_info = f"\n**現在のSSEセッションID**: {sse_session_id}"
    
    base = build_base_prompt()
    
    return f"""
ユーザー要求を分析し、適切なサービスクラスのメソッド呼び出しに分解してください。

ユーザー要求: "{user_request}"
{sse_info}

{base}
"""


class PromptManager:
    """プロンプト管理クラス（モジュール化版）"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.prompt")
    
    def build_planning_prompt(
        self, 
        user_request: str, 
        sse_session_id: str = None
    ) -> str:
        """
        タスク分解用のプロンプトを構築
        
        Args:
            user_request: ユーザーリクエスト
            sse_session_id: SSE session ID
        
        Returns:
            構築されたプロンプト
        """
        # Phase 2.5C では、build_prompt は使わず、build_planning_prompt を使う
        # これは既存の310行プロンプトを使用
        # Phase 2.5D 以降で動的プロンプト構築を完全実装
        return build_base_prompt_from_legacy(user_request, sse_session_id)
    
    def build_prompt(
        self, 
        analysis_result: Dict[str, Any], 
        user_id: str, 
        sse_session_id: str = None
    ) -> str:
        """
        分析結果に基づいてプロンプトを動的に構築（Phase 2.5C で使用）
        
        Args:
            analysis_result: RequestAnalyzer の分析結果
            user_id: ユーザーID
            sse_session_id: SSEセッションID
        
        Returns:
            構築されたプロンプト
        """
        pattern = analysis_result["pattern"]
        params = analysis_result["params"]
        
        # パターン別にプロンプト構築
        pattern_map = {
            "inventory": lambda: build_inventory_prompt(params.get("user_request", "")),
            "menu": lambda: build_menu_prompt(params.get("user_request", ""), user_id),
            "main": lambda: build_main_proposal_prompt(
                params.get("user_request", ""), 
                user_id,
                params.get("main_ingredient")
            ),
            "main_additional": lambda: build_additional_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                sse_session_id,
                "main"
            ),
            "sub": lambda: build_sub_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                params.get("used_ingredients")
            ),
            "soup": lambda: build_soup_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                params.get("used_ingredients"),
                params.get("menu_category", "japanese")
            ),
            "other": lambda: build_other_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                params.get("main_ingredient"),
                params.get("category_detail_keyword")
            ),
            "other_additional": lambda: build_additional_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                sse_session_id,
                "other"
            ),
            "sub_additional": lambda: build_additional_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                sse_session_id,
                "sub"
            ),
            "soup_additional": lambda: build_additional_proposal_prompt(
                params.get("user_request", ""),
                user_id,
                sse_session_id,
                "soup"
            ),
            "greeting": lambda: self._build_default_prompt(),
        }
        
        builder = pattern_map.get(pattern)
        if builder:
            return builder()
        
        # デフォルトプロンプト（その他の未定義パターン）
        return self._build_default_prompt()
    
    def _build_default_prompt(self) -> str:
        """デフォルトプロンプト"""
        return """
ユーザー要求をタスクに分解してください。

挨拶や一般的な会話の場合、タスクは生成せず、**必ず以下のJSON形式**で空の配列を返してください：

{
    "tasks": []
}

**重要な注意事項**:
- タスクが生成できない場合でも、**必ずJSON形式で回答**してください
- 自然言語での説明は一切不要です
- 空の配列を返す場合でも、上記のJSON形式を厳守してください
"""
    
    def create_dynamic_prompt(
        self, 
        base_prompt: str, 
        tool_descriptions: str,
        user_context: Dict[str, Any]
    ) -> str:
        """
        動的プロンプト生成（既存メソッド）
        
        Args:
            base_prompt: ベースプロンプト
            tool_descriptions: ツール説明
            user_context: ユーザーコンテキスト
        
        Returns:
            動的プロンプト
        """
        try:
            self.logger.info(f"🔧 [PromptManager] Creating dynamic prompt")
            
            dynamic_prompt = f"""
{base_prompt}

{tool_descriptions}

ユーザーコンテキスト:
- ユーザーID: {user_context.get('user_id', 'N/A')}
- セッションID: {user_context.get('session_id', 'N/A')}
- リクエスト時刻: {user_context.get('timestamp', 'N/A')}
"""
            
            self.logger.info(f"✅ [PromptManager] Dynamic prompt created successfully")
            
            return dynamic_prompt
            
        except Exception as e:
            self.logger.error(f"❌ [PromptManager] Error in create_dynamic_prompt: {e}")
            return base_prompt

