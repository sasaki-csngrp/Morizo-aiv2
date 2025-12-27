#!/usr/bin/env python3
"""
API層 - チャットルート

メインのチャット処理とSSE進捗表示
"""

import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from config.loggers import GenericLogger
from ..models import ChatRequest, ChatResponse, ProgressUpdate
from ..utils.sse_manager import get_sse_sender
from core.agent import TrueReactAgent
from ..request_models import UserSelectionRequest
from ..utils.auth_handler import get_auth_handler


async def verify_token_dependency(request: Request):
    """トークン検証の依存関係"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    
    token = auth_header.split(" ")[1]
    auth_handler = get_auth_handler()
    user_info = await auth_handler.verify_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token

router = APIRouter()
logger = GenericLogger("api", "chat")


@router.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    """AIエージェントとの対話"""
    try:
        # リクエストボディからconfirmを取得（プロキシ問題回避）
        logger.debug(f"🔍 [API] 生ヘッダー: {dict(http_request.headers)}")
        
        # リクエストボディを直接読み取り
        raw_body = await http_request.body()
        logger.debug(f"🔍 [API] 生リクエストボディ: {raw_body}")
        
        try:
            import json
            raw_json = json.loads(raw_body)
            logger.debug(f"🔍 [API] 生JSON: {raw_json}")
            confirm_from_body = raw_json.get("confirm", False)
            logger.debug(f"🔍 [API] リクエストボディからのconfirm: {confirm_from_body}")
        except Exception as e:
            logger.error(f"❌ [API] Failed to parse body: {e}")
            confirm_from_body = False
        
        # Pydanticモデルの内容をログ出力
        logger.debug(f"🔍 [API] Parsed request model: {request.model_dump()}")
        
        # Pydanticモデルのフィールドを直接確認
        logger.debug(f"🔍 [API] Pydanticモデルフィールド:")
        logger.debug(f"  message: {request.message}")
        logger.debug(f"  sse_session_id: {request.sse_session_id}")
        logger.debug(f"  confirm: {request.confirm}")
        logger.debug(f"🔍 [API] リクエストボディからのconfirm: {confirm_from_body}")
        
        # 実際に使用する値（リクエストボディを優先）
        actual_confirm = confirm_from_body or request.confirm
        logger.debug(f"🔍 [API] 実際のconfirm値: {actual_confirm}")
        
        # リクエストボディの詳細ログ
        logger.info(f"🔍 [API] チャットリクエストを受信しました")
        logger.debug(f"  メッセージ: {request.message[:100]}...")
        logger.debug(f"  トークン: {'設定済み' if request.token else '未設定'}")
        logger.debug(f"  SSEセッションID: {request.sse_session_id if request.sse_session_id else '未設定'}")
        logger.debug(f"  Confirm: {request.confirm} (型: {type(request.confirm).__name__})")
        
        # ミドルウェアで認証済みのユーザー情報を取得
        user_info = getattr(http_request.state, 'user_info', None)
        user_id = user_info['user_id'] if user_info else "anonymous"
        
        # Authorizationヘッダーからトークンを取得
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        logger.debug(f"🔍 [API] ミドルウェアからのユーザー情報: {user_id}")
        logger.debug(f"🔍 [API] Authorizationヘッダーからのトークン: {'設定済み' if token else '未設定'}")
        
        # メッセージの前処理（空白のみのメッセージを検知）
        message_stripped = request.message.strip() if request.message else ""
        is_whitespace_only = len(message_stripped) == 0
        
        # SSEセッションIDの生成（提供されていない場合）
        sse_session_id = request.sse_session_id or str(uuid.uuid4())
        
        # TrueReactAgentの初期化と実行
        agent = TrueReactAgent()
        
        # Phase 3C-3: 次の段階のリクエストがセッションに保存されている場合はそれを使用
        from services.session_service import session_service
        session = await session_service.get_session(sse_session_id, user_id)
        
        # 空白のみのメッセージの場合、セッションが見つからなくてもユーザーの全セッションからnext_stage_requestを探す
        if is_whitespace_only and not session:
            logger.debug(f"🔍 [API] Whitespace-only message detected, searching for next_stage_request in user's sessions")
            # ユーザーの全セッションからnext_stage_requestを持つセッションを探す
            user_sessions = session_service.user_sessions.get(user_id, {})
            for session_id, candidate_session in user_sessions.items():
                next_stage_request = candidate_session.get_context("next_stage_request")
                if next_stage_request:
                    logger.debug(f"🔄 [API] Next stage request found in session {session_id}: {next_stage_request}")
                    # セッションから削除して実行
                    candidate_session.set_context("next_stage_request", None)
                    # 見つかったセッションIDを使って次の段階のリクエストを実行
                    response_data = await agent.process_request(
                        next_stage_request,
                        user_id,
                        token=token,
                        sse_session_id=session_id,
                        is_confirmation_response=False
                    )
                    break
            else:
                # next_stage_requestが見つからない場合はエラーを返す
                logger.warning(f"⚠️ [API] Whitespace-only message but no next_stage_request found in user's sessions")
                raise HTTPException(
                    status_code=400, 
                    detail="次の段階へのリクエストが見つかりませんでした。セッション情報が無効の可能性があります。"
                )
        elif session:
            next_stage_request = session.get_context("next_stage_request")
            if next_stage_request:
                logger.debug(f"🔄 [API] Next stage request found in session: {next_stage_request}")
                # セッションから削除して実行
                session.set_context("next_stage_request", None)
                # 次の段階のリクエストを実行
                response_data = await agent.process_request(
                    next_stage_request,
                    user_id,
                    token=token,
                    sse_session_id=sse_session_id,
                    is_confirmation_response=False
                )
            elif is_whitespace_only:
                # 空白のみのメッセージで、next_stage_requestが見つからない場合はエラー
                logger.warning(f"⚠️ [API] Whitespace-only message but no next_stage_request in session")
                raise HTTPException(
                    status_code=400, 
                    detail="次の段階へのリクエストが見つかりませんでした。"
                )
            else:
                # 通常のリクエストの処理
                response_data = await agent.process_request(
                    request.message, 
                    user_id,
                    token=token,
                    sse_session_id=sse_session_id,
                    is_confirmation_response=actual_confirm
                )
        else:
            # 空白のみのメッセージでセッションも見つからない場合はエラー
            if is_whitespace_only:
                logger.warning(f"⚠️ [API] Whitespace-only message but session not found")
                raise HTTPException(
                    status_code=400, 
                    detail="セッション情報が無効です。ページを再読み込みしてください。"
                )
            # 通常のリクエストの処理
            response_data = await agent.process_request(
                request.message, 
                user_id,
                token=token,
                sse_session_id=sse_session_id,
                is_confirmation_response=actual_confirm
            )
        
        # レスポンスの生成
        if isinstance(response_data, dict) and response_data.get("requires_selection"):
            # ユーザー選択が必要な場合
            logger.debug(f"🔍 [API] Building selection response: requires_selection={response_data.get('requires_selection')}, candidates_count={len(response_data.get('candidates', []))}")
            response = ChatResponse(
                response=response_data.get("message", "選択してください"),
                success=True,
                model_used="gpt-4o-mini",
                user_id=user_id,
                requires_selection=response_data.get("requires_selection", False),
                candidates=response_data.get("candidates"),
                task_id=response_data.get("task_id"),
                current_stage=response_data.get("current_stage"),
                used_ingredients=response_data.get("used_ingredients"),
                menu_category=response_data.get("menu_category")
            )
            logger.debug(f"🔍 [API] Selection response built: requires_selection={response.requires_selection}, candidates_count={len(response.candidates or [])}")
        elif isinstance(response_data, dict) and "requires_confirmation" in response_data:
            # 曖昧性確認が必要な場合
            logger.debug(f"🔍 [API] Building confirmation response: requires_confirmation={response_data.get('requires_confirmation')}, session_id={response_data.get('confirmation_session_id')}")
            response = ChatResponse(
                response=response_data["response"],
                success=True,
                model_used="gpt-4o-mini",
                user_id=user_id,
                requires_confirmation=response_data.get("requires_confirmation", False),
                confirmation_session_id=response_data.get("confirmation_session_id")
            )
            logger.debug(f"🔍 [API] Confirmation response built: requires_confirmation={response.requires_confirmation}, confirmation_session_id={response.confirmation_session_id}")
        elif isinstance(response_data, dict) and "requires_selection" in response_data:
            # ユーザー選択が必要な場合
            logger.debug(f"🔍 [API] Building selection response: requires_selection={response_data.get('requires_selection')}, candidates_count={len(response_data.get('candidates', []))}")
            response = ChatResponse(
                response=response_data.get("message", "選択してください"),
                success=True,
                model_used="gpt-4o-mini",
                user_id=user_id,
                requires_selection=response_data.get("requires_selection", False),
                candidates=response_data.get("candidates"),
                task_id=response_data.get("task_id"),
                current_stage=response_data.get("current_stage"),
                used_ingredients=response_data.get("used_ingredients"),
                menu_category=response_data.get("menu_category")
            )
            logger.debug(f"🔍 [API] Selection response built: requires_selection={response.requires_selection}, candidates_count={len(response.candidates or [])}")
        else:
            # 通常のレスポンス
            logger.debug(f"🔍 [API] 通常レスポンスを構築中")
            if isinstance(response_data, dict):
                response_text = response_data.get("response", str(response_data))
            else:
                response_text = str(response_data)
            
            response = ChatResponse(
                response=response_text,
                success=True,
                model_used="gpt-4o-mini",
                user_id=user_id,
                requires_confirmation=False,
                confirmation_session_id=None
            )
            logger.debug(f"🔍 [API] 通常レスポンス構築完了: requires_confirmation={response.requires_confirmation}, confirmation_session_id={response.confirmation_session_id}")
        
        logger.debug(f"🔍 [API] 最終レスポンスオブジェクト: {response.dict()}")
        
        # 完了通知はTaskChainManagerで送信されるため、ここでは送信しない
        # await sse_sender.send_complete(sse_session_id, response_text)
        
        logger.info(f"✅ [API] チャットリクエスト完了 ユーザー: {user_id}")
        return response.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Chat request failed: {e}")
        
        # エラー通知（SSEセッションIDがある場合）
        if request.sse_session_id:
            sse_sender = get_sse_sender()
            await sse_sender.send_error(request.sse_session_id, str(e))
        
        raise HTTPException(status_code=500, detail="チャット処理でエラーが発生しました")


@router.get("/chat/stream/{sse_session_id}")
async def stream_progress(sse_session_id: str, request: Request):
    """Server-Sent Eventsによる進捗表示"""
    try:
        logger.info(f"🔍 [API] SSE stream requested for session: {sse_session_id}")
        
        # ミドルウェアで認証済みのユーザー情報を取得
        user_info = getattr(request.state, 'user_info', None)
        if not user_info:
            raise HTTPException(status_code=401, detail="認証が必要です")
        
        logger.info(f"🔍 [API] SSE stream authenticated for user: {user_info['user_id']}")
        
        # SSE接続の確立
        sse_sender = get_sse_sender()
        connection_id = sse_sender.add_connection(sse_session_id)
        
        async def event_generator():
            """SSEイベントジェネレータ"""
            try:
                # 接続確認メッセージ
                yield f"data: {_create_sse_event('connected', {'message': 'SSE接続が確立されました'})}\n\n"
                
                # メッセージループ
                heartbeat_counter = 0
                while True:
                    try:
                        # キューからメッセージを取得（タイムアウト付き）
                        if sse_session_id in sse_sender._connections and sse_sender._connections[sse_session_id]:
                            message = await asyncio.wait_for(
                                sse_sender._connections[sse_session_id][0].get(), 
                                timeout=30.0  # 30秒に延長
                            )
                            yield message
                            
                            # 完了メッセージの場合は接続を終了
                            try:
                                import json
                                message_data = json.loads(message.split('data: ')[1].strip())
                                if message_data.get('type') == 'complete':
                                    logger.info(f"🔚 [API] Processing complete, closing SSE connection for session: {sse_session_id}")
                                    yield f"data: {_create_sse_event('close', {'message': 'Connection will close after completion'})}\n\n"
                                    break
                            except (json.JSONDecodeError, IndexError):
                                # JSON解析エラーは無視
                                pass
                        else:
                            # 接続が存在しない場合は終了
                            logger.warning(f"⚠️ [API] SSE session {sse_session_id} not found, closing connection")
                            break
                    except asyncio.TimeoutError:
                        # タイムアウト時はハートビートを送信
                        heartbeat_counter += 1
                        logger.debug(f"💓 [API] Sending heartbeat #{heartbeat_counter} to session: {sse_session_id}")
                        yield f"data: {_create_sse_event('heartbeat', {'message': 'ping', 'counter': heartbeat_counter})}\n\n"
                        
                        # 接続状態を確認
                        if not sse_sender._connections.get(sse_session_id):
                            logger.warning(f"⚠️ [API] SSE session {sse_session_id} disconnected, closing connection")
                            break
                    except Exception as e:
                        logger.error(f"❌ [API] SSE message error: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"❌ [API] SSE stream error: {e}")
                yield f"data: {_create_sse_event('error', {'message': str(e)})}\n\n"
            finally:
                # 接続のクリーンアップ
                sse_sender.remove_connection(sse_session_id, connection_id)
                logger.info(f"🔌 [API] SSE connection closed for session: {sse_session_id}")
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] SSE stream failed: {e}")
        raise HTTPException(status_code=500, detail="SSEストリームでエラーが発生しました")


def _create_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """SSEイベントの作成"""
    import json
    from datetime import datetime
    
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    return json.dumps(event, ensure_ascii=False)


@router.post("/chat/selection")
async def receive_user_selection(
    selection_request: UserSelectionRequest,
    http_request: Request
):
    """ユーザーの選択結果を受信"""
    try:
        # ミドルウェアで認証済みのユーザー情報を取得
        user_info = getattr(http_request.state, 'user_info', None)
        user_id = user_info['user_id'] if user_info else "anonymous"
        
        # Authorizationヘッダーからトークンを取得
        authorization = http_request.headers.get("Authorization")
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        
        logger.debug(f"🔍 [API] User info from middleware: {user_id}")
        logger.debug(f"🔍 [API] Token from Authorization header: {'SET' if token else 'NOT SET'}")
        
        # バリデーション（基本的な必須項目のみ）
        if not selection_request.task_id:
            raise HTTPException(status_code=400, detail="Task ID is required")
        
        if not selection_request.sse_session_id:
            raise HTTPException(status_code=400, detail="SSE session ID is required")
        
        logger.info(f"📥 [API] Received user selection: task_id={selection_request.task_id}, selection={selection_request.selection}")
        
        # エージェントで選択結果を処理
        agent = TrueReactAgent()
        result = await agent.process_user_selection(
            selection_request.task_id,
            selection_request.selection,
            selection_request.sse_session_id,
            user_id,
            token,
            selection_request.old_sse_session_id  # 旧セッションIDを渡す
        )
        
        # 選択処理の結果をログ出力
        logger.debug(f"📤 [API] Selection processing result: success={result.get('success')}, response_length={len(str(result.get('response', '')))}")
        logger.debug(f"📤 [API] Selection result preview: {str(result)[:200]}...")
        
        # Phase 1F: 追加提案時はsuccessキーがない場合がある
        if result.get("success") is False:
            logger.error(f"❌ [API] Selection processing failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Phase 3C-3: 自動遷移の場合、responseキーがある場合は正常として処理
        if "response" in result and result.get("success") is None:
            logger.debug(f"🔄 [API] Auto-transition detected, returning requires_next_stage flag")
            return {
                "success": True,
                "message": "選択を受け付けました。次段階に自動遷移します。",
                "response": result.get("response", ""),
                "requires_next_stage": True  # フロントエンドに次の段階の提案を要求
            }
        
        # Phase 1F: 追加提案の成功時はそのまま返す（successキーがない場合がある）
        logger.info(f"✅ [API] Selection processing completed successfully")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Failed to receive user selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))
