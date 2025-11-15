#!/usr/bin/env python3
"""
ConfirmationManager - 確認状態管理マネージャー

曖昧性解決の状態管理を担当
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .models import Session


class ConfirmationManager:
    """確認状態管理マネージャー"""
    
    def __init__(self, session_service):
        """初期化
        
        Args:
            session_service: SessionServiceインスタンスへの参照
        """
        self.session_service = session_service
    
    async def save_confirmation_state(
        self,
        sse_session_id: str,
        user_id: str,
        state_data: Dict[str, Any]
    ) -> None:
        """
        曖昧性解決の状態を保存
        
        Args:
            sse_session_id: SSEセッションID
            user_id: ユーザーID
            state_data: {
                'task_chain_manager': TaskChainManager,
                'execution_result': ExecutionResult,
                'original_tasks': List[Task],
                'ambiguity_info': AmbiguityInfo,
                'created_at': datetime
            }
        """
        try:
            self.session_service.logger.debug(f"💾 [SessionService] Saving confirmation state for session: {sse_session_id}")
            
            # セッションを取得または作成
            session = await self.session_service.get_session(sse_session_id)
            if not session:
                session = Session(sse_session_id, user_id)
                # ユーザー別セッション管理
                if user_id not in self.session_service.user_sessions:
                    self.session_service.user_sessions[user_id] = {}
                self.session_service.user_sessions[user_id][sse_session_id] = session
                self.session_service.logger.info(f"📝 [SessionService] Created new session for confirmation state")
            
            # 曖昧性解決状態を保存
            session.data['confirmation_state'] = state_data
            session.data['state_type'] = 'awaiting_confirmation'
            session.last_accessed = datetime.now()
            
            # デバッグログ: 保存された状態の詳細
            self.session_service.logger.debug(f"🔍 [SessionService] Saved state keys: {list(state_data.keys())}")
            self.session_service.logger.debug(f"🔍 [SessionService] Session data keys: {list(session.data.keys())}")
            self.session_service.logger.debug(f"✅ [SessionService] Confirmation state saved successfully")
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in save_confirmation_state: {e}")
            raise
    
    async def get_confirmation_state(
        self,
        sse_session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        曖昧性解決の状態を取得
        
        Args:
            sse_session_id: SSEセッションID
        
        Returns:
            保存された状態データ（存在しない場合はNone）
        """
        try:
            self.session_service.logger.debug(f"🔍 [SessionService] Getting confirmation state for session: {sse_session_id}")
            
            session = await self.session_service.get_session(sse_session_id)
            if not session:
                self.session_service.logger.warning(f"⚠️ [SessionService] Session not found: {sse_session_id}")
                return None
            
            if 'confirmation_state' not in session.data:
                self.session_service.logger.warning(f"⚠️ [SessionService] No confirmation_state in session data for: {sse_session_id}")
                self.session_service.logger.debug(f"🔍 [SessionService] Available session data keys: {list(session.data.keys())}")
                return None
            
            state_data = session.data.get('confirmation_state')
            self.session_service.logger.debug(f"🔍 [SessionService] Retrieved state keys: {list(state_data.keys()) if state_data else 'None'}")
            self.session_service.logger.debug(f"✅ [SessionService] Confirmation state retrieved successfully")
            
            return state_data
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in get_confirmation_state: {e}")
            return None
    
    async def clear_confirmation_state(
        self,
        sse_session_id: str
    ) -> None:
        """
        曖昧性解決の状態をクリア
        
        Args:
            sse_session_id: SSEセッションID
        """
        try:
            self.session_service.logger.debug(f"🧹 [SessionService] Clearing confirmation state for session: {sse_session_id}")
            
            session = await self.session_service.get_session(sse_session_id)
            if session and 'confirmation_state' in session.data:
                del session.data['confirmation_state']
                if 'state_type' in session.data:
                    del session.data['state_type']
                session.last_accessed = datetime.now()
                self.session_service.logger.info(f"✅ [SessionService] Confirmation state cleared successfully")
            else:
                self.session_service.logger.warning(f"⚠️ [SessionService] No confirmation state to clear for session: {sse_session_id}")
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in clear_confirmation_state: {e}")

