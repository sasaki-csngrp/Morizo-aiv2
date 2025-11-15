#!/usr/bin/env python3
"""
API層 - SSE管理

Server-Sent Eventsの管理とメッセージ配信
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from config.loggers import GenericLogger


class SSESender:
    """SSE送信管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("api", "sse")
        self._connections: Dict[str, List[asyncio.Queue]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """クリーンアップタスクの開始"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_connections())
    
    async def _cleanup_connections(self):
        """接続のクリーンアップ"""
        while True:
            try:
                await asyncio.sleep(30)  # 30秒ごとにクリーンアップ
                
                # 空の接続リストを削除
                empty_sessions = [
                    session_id for session_id, queues in self._connections.items()
                    if not queues
                ]
                
                for session_id in empty_sessions:
                    del self._connections[session_id]
                    self.logger.debug(f"🧹 [SSE] Cleaned up empty session: {session_id}")
                
            except Exception as e:
                self.logger.error(f"❌ [SSE] Cleanup task error: {e}")
    
    def add_connection(self, session_id: str) -> str:
        """新しい接続を追加"""
        try:
            if session_id not in self._connections:
                self._connections[session_id] = []
            
            queue = asyncio.Queue()
            connection_id = str(uuid.uuid4())
            self._connections[session_id].append(queue)
            
            total_connections = len(self._connections[session_id])
            self.logger.debug(f"🔗 [SSE] Added connection {connection_id} to session {session_id} (total: {total_connections})")
            return connection_id
            
        except Exception as e:
            self.logger.error(f"❌ [SSE] Failed to add connection: {e}")
            return ""
    
    def remove_connection(self, session_id: str, connection_id: str):
        """接続を削除"""
        try:
            if session_id in self._connections:
                # 接続を削除（実際の実装ではconnection_idで特定）
                if self._connections[session_id]:
                    self._connections[session_id].pop(0)  # 簡易実装
                
                remaining_connections = len(self._connections[session_id])
                self.logger.debug(f"🔌 [SSE] Removed connection from session {session_id} (remaining: {remaining_connections})")
                
        except Exception as e:
            self.logger.error(f"❌ [SSE] Failed to remove connection: {e}")
    
    async def send_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """進捗メッセージを送信"""
        try:
            event_data = {
                "type": "progress",
                "sse_session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "message": progress_data.get("message", ""),
                "progress": {
                    "completed_tasks": progress_data.get("completed_tasks", 0),
                    "total_tasks": progress_data.get("total_tasks", 0),
                    "progress_percentage": progress_data.get("progress_percentage", 0),
                    "current_task": progress_data.get("current_task", ""),
                    "remaining_tasks": progress_data.get("remaining_tasks", 0),
                    "is_complete": progress_data.get("is_complete", False)
                }
            }
            
            # デバッグ用ログ
            self.logger.debug(f"📊 [SSE] Progress message content: {event_data}")
            
            await self._send_to_session(session_id, event_data)
            self.logger.debug(f"📊 [SSE] Sent progress {progress_data.get('progress_percentage', 0)}% to session {session_id}")
            
        except Exception as e:
            self.logger.error(f"❌ [SSE] Failed to send progress: {e}")
    
    async def send_complete(self, session_id: str, response_text: str, menu_data: Optional[Dict[str, Any]] = None, confirmation_data: Optional[Dict[str, Any]] = None):
        """完了メッセージを送信"""
        try:
            event_data = {
                "type": "complete",
                "result": {
                    "response": response_text
                }
            }
            
            # menu_dataがある場合は追加
            if menu_data:
                event_data["result"]["menu_data"] = menu_data
                self.logger.debug(f"📊 [SSE] Menu data included in response: {len(str(menu_data))} characters")
                self.logger.debug(f"🔍 [SSE] Menu data preview: {str(menu_data)[:200]}...")
            else:
                self.logger.debug(f"⚠️ [SSE] No menu data provided")
            
            # confirmation_dataがある場合は追加
            if confirmation_data:
                event_data["result"]["requires_confirmation"] = confirmation_data.get("requires_confirmation", False)
                event_data["result"]["confirmation_session_id"] = confirmation_data.get("confirmation_session_id")
                self.logger.debug(f"🔍 [SSE] Confirmation data included: {confirmation_data}")
            else:
                self.logger.debug(f"⚠️ [SSE] No confirmation data provided")
            
            # 実際の送信処理を追加
            await self._send_to_session(session_id, event_data)
            self.logger.info(f"✅ [SSE] Sent complete to session {session_id}")
            
        except Exception as e:
            self.logger.error(f"❌ [SSE] Failed to send complete: {e}")
    
    async def send_error(self, session_id: str, error_message: str):
        """エラーメッセージを送信"""
        try:
            event_data = {
                "type": "error",
                "message": error_message,
                "timestamp": datetime.now().isoformat()
            }
            
            await self._send_to_session(session_id, event_data)
            self.logger.error(f"❌ [SSE] Sent error to session {session_id}: {error_message}")
            
        except Exception as e:
            self.logger.error(f"❌ [SSE] Failed to send error: {e}")
    
    async def _send_to_session(self, session_id: str, event_data: dict):
        """セッション内の全接続にメッセージを送信"""
        if session_id not in self._connections:
            self.logger.warning(f"⚠️ [SSE] Session {session_id} not found for message sending")
            return
        
        message = f"data: {json.dumps(event_data)}\n\n"
        connection_count = len(self._connections[session_id])
        
        # 各接続にメッセージを送信
        successful_sends = 0
        for queue in self._connections[session_id]:
            try:
                await queue.put(message)
                successful_sends += 1
            except Exception as e:
                self.logger.error(f"❌ [SSE] Failed to send to queue: {e}")
        
        if successful_sends < connection_count:
            self.logger.warning(f"⚠️ [SSE] Only {successful_sends}/{connection_count} connections received message for session {session_id}")


# グローバルSSE送信者インスタンス
_sse_sender: Optional[SSESender] = None


def get_sse_sender() -> SSESender:
    """SSE送信者のシングルトン取得"""
    global _sse_sender
    if _sse_sender is None:
        _sse_sender = SSESender()
    return _sse_sender
