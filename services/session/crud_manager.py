#!/usr/bin/env python3
"""
SessionCRUDManager - セッション基本CRUD操作マネージャー

セッションの作成、取得、更新、削除、クリーンアップを担当
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from .models import Session


class SessionCRUDManager:
    """セッション基本CRUD操作マネージャー"""
    
    def __init__(self, session_service):
        """初期化
        
        Args:
            session_service: SessionServiceインスタンスへの参照
        """
        self.session_service = session_service
    
    async def create_session(
        self, 
        user_id: str,
        session_id: Optional[str] = None
    ) -> Session:
        """
        セッションを作成（認証はAPI層で完了済み）
        
        Args:
            user_id: ユーザーID
            session_id: 指定するセッションID（Noneの場合は自動生成）
        
        Returns:
            作成されたセッション
        """
        try:
            self.session_service.logger.debug(f"🔧 [SessionService] Creating session for user: {user_id}")
            
            # セッションIDを生成または指定されたIDを使用
            if session_id is None:
                session_id = str(uuid.uuid4())
            
            # セッションを作成（user_idがNoneの場合は"system"を使用）
            actual_user_id = user_id if user_id else "system"
            session = Session(
                session_id=session_id,
                user_id=actual_user_id
            )
            
            # ユーザー別セッション管理
            if user_id not in self.session_service.user_sessions:
                self.session_service.user_sessions[user_id] = {}
            self.session_service.user_sessions[user_id][session_id] = session
            
            self.session_service.logger.info(f"✅ [SessionService] Session created successfully: {session_id}")
            
            return session
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in create_session: {e}")
            raise
    
    async def get_session(
        self, 
        session_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Session]:
        """
        セッションを取得
        
        Args:
            session_id: セッションID
            user_id: ユーザーID（指定された場合はそのユーザーのセッションのみ検索）
        
        Returns:
            セッション（存在しない場合はNone）
        """
        try:
            self.session_service.logger.debug(f"🔧 [SessionService] Getting session: {session_id}")
            
            session = None
            
            if user_id:
                # 特定ユーザーのセッションを検索
                user_sessions = self.session_service.user_sessions.get(user_id, {})
                session = user_sessions.get(session_id)
            else:
                # 全ユーザーからセッションを検索
                for user_sessions in self.session_service.user_sessions.values():
                    if session_id in user_sessions:
                        session = user_sessions[session_id]
                        break
            
            if session:
                # 最終アクセス時刻の更新
                session.last_accessed = datetime.now()
                self.session_service.logger.debug(f"✅ [SessionService] Session retrieved successfully")
            else:
                self.session_service.logger.warning(f"⚠️ [SessionService] Session not found: {session_id}")
            
            return session
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in get_session: {e}")
            return None
    
    async def update_session(
        self, 
        session_id: str, 
        updates: Dict[str, Any]
    ) -> bool:
        """
        セッションを更新
        
        Args:
            session_id: セッションID
            updates: 更新データ
        
        Returns:
            更新成功の可否
        """
        try:
            self.session_service.logger.debug(f"🔧 [SessionService] Updating session: {session_id}")
            
            # 全ユーザーからセッションを検索
            session = None
            for user_sessions in self.session_service.user_sessions.values():
                if session_id in user_sessions:
                    session = user_sessions[session_id]
                    break
            
            if not session:
                self.session_service.logger.warning(f"⚠️ [SessionService] Session not found for update: {session_id}")
                return False
            
            # セッションデータを更新
            session.data.update(updates)
            session.last_accessed = datetime.now()
            
            self.session_service.logger.info(f"✅ [SessionService] Session updated successfully")
            
            return True
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in update_session: {e}")
            return False
    
    async def delete_session(
        self, 
        session_id: str
    ) -> bool:
        """
        セッションを削除
        
        Args:
            session_id: セッションID
        
        Returns:
            削除成功の可否
        """
        try:
            self.session_service.logger.debug(f"🔧 [SessionService] Deleting session: {session_id}")
            
            # 全ユーザーからセッションを検索して削除
            deleted = False
            for user_id, user_sessions in self.session_service.user_sessions.items():
                if session_id in user_sessions:
                    del user_sessions[session_id]
                    deleted = True
                    break
            
            if deleted:
                self.session_service.logger.info(f"✅ [SessionService] Session deleted successfully")
                return True
            else:
                self.session_service.logger.warning(f"⚠️ [SessionService] Session not found for deletion: {session_id}")
                return False
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in delete_session: {e}")
            return False
    
    async def cleanup_expired_sessions(
        self, 
        max_age_hours: int = 24
    ) -> int:
        """
        期限切れセッションのクリーンアップ
        
        Args:
            max_age_hours: 最大有効時間（時間）
        
        Returns:
            削除されたセッション数
        """
        try:
            self.session_service.logger.info(f"🔧 [SessionService] Cleaning up expired sessions (max_age: {max_age_hours}h)")
            
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            expired_sessions = []
            for user_id, user_sessions in self.session_service.user_sessions.items():
                for session_id, session in user_sessions.items():
                    if session.last_accessed < cutoff_time:
                        expired_sessions.append((user_id, session_id))
            
            for user_id, session_id in expired_sessions:
                del self.session_service.user_sessions[user_id][session_id]
            
            self.session_service.logger.debug(f"✅ [SessionService] Cleaned up {len(expired_sessions)} expired sessions")
            
            return len(expired_sessions)
            
        except Exception as e:
            self.session_service.logger.error(f"❌ [SessionService] Error in cleanup_expired_sessions: {e}")
            return 0

