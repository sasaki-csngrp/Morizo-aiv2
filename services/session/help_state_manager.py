#!/usr/bin/env python3
"""
HelpStateManager - ヘルプ状態管理マネージャー

ヘルプ機能の状態管理を担当
"""

from typing import Optional

from .models import Session


class HelpStateManager:
    """ヘルプ状態管理マネージャー"""
    
    def __init__(self, session_service):
        """初期化
        
        Args:
            session_service: SessionServiceインスタンスへの参照
        """
        self.session_service = session_service
    
    async def set_help_state(
        self,
        sse_session_id: str,
        user_id: str,
        help_state: Optional[str]
    ) -> None:
        """ヘルプ状態を設定
        
        Args:
            sse_session_id: SSEセッションID
            user_id: ユーザーID
            help_state: "overview", "detail_1", "detail_2", "detail_3", "detail_4", または None
        """
        try:
            self.session_service.logger.debug(f"💾 [SessionService] Setting help state: {help_state} for session: {sse_session_id}")
            
            session = await self.session_service.get_session(sse_session_id, user_id)
            if not session:
                # セッションが存在しない場合は作成
                self.session_service.logger.debug(f"🔧 [SESSION] Creating session for help state: {sse_session_id}")
                session = await self.session_service.create_session(user_id, sse_session_id)
            
            if session:
                session.set_context("help_state", help_state)
                self.session_service.logger.info(f"💾 [SESSION] Help state set: {help_state}")
            else:
                self.session_service.logger.warning(f"⚠️ [SESSION] Failed to create session for help state setting: {sse_session_id}")
                
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in set_help_state: {e}")
            raise
    
    async def get_help_state(
        self,
        sse_session_id: Optional[str],
        user_id: str
    ) -> Optional[str]:
        """ヘルプ状態を取得
        
        Args:
            sse_session_id: SSEセッションID（Noneの場合はユーザーID単位で検索）
            user_id: ユーザーID
        
        Returns:
            ヘルプ状態（"overview", "detail_1-4", または None）
        """
        try:
            self.session_service.logger.debug(f"🔍 [SESSION] Getting help state: sse_session_id={sse_session_id}, user_id={user_id}")
            
            # まず指定されたセッションIDで検索
            if sse_session_id:
                session = await self.session_service.get_session(sse_session_id, user_id)
                if session:
                    help_state = session.get_context("help_state", None)
                    if help_state:
                        self.session_service.logger.debug(f"✅ [SESSION] Help state retrieved from session {sse_session_id}: {help_state}")
                        return help_state
            
            # セッションIDで見つからない場合、またはセッションIDがNoneの場合
            # ユーザーID単位で最新のヘルプ状態を持つセッションを検索
            if user_id and user_id in self.session_service.user_sessions:
                user_sessions = self.session_service.user_sessions[user_id]
                # 最新のアクセス時刻でソートして、ヘルプ状態を持つセッションを検索
                for session_id, session in user_sessions.items():
                    if session_id != sse_session_id:  # 既にチェックしたセッションはスキップ
                        help_state = session.get_context("help_state", None)
                        if help_state:
                            self.session_service.logger.debug(f"✅ [SESSION] Help state retrieved from user's other session {session_id}: {help_state}")
                            return help_state
            
            if sse_session_id:
                self.session_service.logger.warning(f"⚠️ [SESSION] Session not found for help state retrieval: {sse_session_id}")
            else:
                self.session_service.logger.info(f"ℹ️ [SESSION] No help state found")
                self.session_service.logger.debug(f"🔍 [SESSION] User ID: {user_id}")
            return None
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in get_help_state: {e}")
            return None
    
    async def clear_help_state(
        self,
        sse_session_id: str,
        user_id: str
    ) -> None:
        """ヘルプ状態をクリア（通常モードに戻る）
        
        Args:
            sse_session_id: SSEセッションID
            user_id: ユーザーID
        """
        try:
            await self.set_help_state(sse_session_id, user_id, None)
            self.session_service.logger.info(f"🧹 [SESSION] Help state cleared")
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in clear_help_state: {e}")
            raise

