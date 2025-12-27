#!/usr/bin/env python3
"""
LLMClient - LLM API呼び出し

LLMServiceから分離したLLM API呼び出し専用クラス
OpenAI API呼び出しとフォールバック処理を担当
"""

import os
from typing import Dict, Any, List
from dotenv import load_dotenv
from openai import AsyncOpenAI
from config.loggers import GenericLogger, log_prompt_with_tokens

# 環境変数を読み込み
load_dotenv()


class LLMClient:
    """LLM API呼び出しクラス"""
    
    MAX_TOKENS = 3000  # マックストークン数
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.client")
        
        # OpenAI設定を環境変数から取得
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.8"))
        
        # OpenAIクライアントを初期化
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            self.logger.debug(f"✅ [LLMClient] OpenAIクライアントを初期化しました: モデル={self.openai_model}")
        else:
            self.openai_client = None
            self.logger.warning("⚠️ [LLMClient] OPENAI_API_KEYが見つかりません。LLM呼び出しは無効になります")
    
    async def call_openai_api(self, prompt: str) -> str:
        """
        OpenAI APIを呼び出してレスポンスを取得
        
        Args:
            prompt: 送信するプロンプト
        
        Returns:
            LLMからのレスポンス
        """
        try:
            if not self.openai_client:
                raise Exception("OpenAI client not initialized")
            
            self.logger.debug(f"🔧 [LLMClient] OpenAI APIを呼び出し中: モデル={self.openai_model}")
            
            # プロンプトとトークン数をログ出力（5行省略表示）
            log_prompt_with_tokens(prompt, max_tokens=self.MAX_TOKENS, logger_name="service.llm")
            
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "あなたは優秀なタスク分解アシスタントです。ユーザーの要求を適切なサービスクラスのメソッド呼び出しに分解してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.openai_temperature,
                max_tokens=self.MAX_TOKENS
            )
            
            content = response.choices[0].message.content
            self.logger.debug(f"✅ [LLMClient] OpenAI APIレスポンスを受信しました: {len(content)}文字")
            
            # LLMレスポンスを改行付きでログ出力
            self.logger.debug(f"📄 [LLMClient] LLMレスポンス:\n{content}")
            
            return content
            
        except Exception as e:
            self.logger.error(f"❌ [LLMClient] OpenAI API呼び出しに失敗しました: {e}")
            raise
    
    def get_fallback_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """
        フォールバック用のタスク（LLM呼び出し失敗時）
        
        Args:
            user_id: ユーザーID
        
        Returns:
            フォールバックタスクリスト
        """
        self.logger.debug(f"🔄 [LLMClient] フォールバックタスクを使用中: ユーザー={user_id}")
        
        return [
            {
                "service": "InventoryService",
                "method": "get_inventory",
                "parameters": {"user_id": user_id},
                "dependencies": []
            }
        ]
    
