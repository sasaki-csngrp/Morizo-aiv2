#!/usr/bin/env python3
"""
API層 - FastAPIアプリケーション

メインアプリケーションの起動と設定
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import os
from dotenv import load_dotenv
from config.loggers import GenericLogger
from config.logging import setup_logging, get_log_level
from api.middleware import AuthenticationMiddleware, LoggingMiddleware
from api.routes import chat_router, health_router, recipe_router, menu_router, inventory_router, user_router, subscription_router
from api.models import ErrorResponse

# 環境変数の読み込み
load_dotenv()

# ログレベルの取得と確認
log_level = get_log_level()
print(f"🔍 [DEBUG] 取得したログレベル: {log_level}")
print(f"🔍 [DEBUG] 環境変数LOG_LEVEL: {os.getenv('LOG_LEVEL', 'NOT SET')}")
print(f"🔍 [DEBUG] 環境変数ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NOT SET')}")

# ログ設定の初期化とローテーション
setup_logging(log_level=log_level, initialize=True)

# ロガーの初期化
logger = GenericLogger("api", "main")

# DEBUGログのテスト（起動時）
logger.debug("🔍 [DEBUG] これはDEBUGログのテストです")
logger.info("ℹ️ [INFO] これはINFOログのテストです")
logger.warning("⚠️ [WARNING] これはWARNINGログのテストです")
logger.error("❌ [ERROR] これはERRORログのテストです（テスト用なので問題ありません）")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時の処理
    logger.info("🚀 [API] Morizo AI v2 starting...")
    
    try:
        # サービスの初期化
        logger.info("🔧 [API] Initializing services...")
        
        # Core層の初期化確認
        from core.agent import TrueReactAgent
        agent = TrueReactAgent()
        logger.info("✅ [API] Core layer initialized")
        
        # Service層の初期化確認
        from services.tool_router import ToolRouter
        tool_router = ToolRouter()
        logger.info("✅ [API] Service layer initialized")
        
        # MCP層の初期化確認
        from mcp_servers.client import MCPClient
        mcp_client = MCPClient()
        logger.info("✅ [API] MCP layer initialized")
        
        logger.info("🎉 [API] All services initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ [API] Service initialization failed: {e}")
        raise
    
    yield
    
    # 終了時の処理
    logger.info("🛑 [API] Morizo AI v2 shutting down...")


# FastAPIアプリケーションの作成
app = FastAPI(
    title="Morizo AI v2",
    description="Smart Pantry MVPのAIエージェント",
    version="2.0.0"
    # lifespan=lifespan  # 一時的に無効化
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# カスタムミドルウェアの追加
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthenticationMiddleware)

# 静的ファイルの配信設定
app.mount("/static", StaticFiles(directory="static"), name="static")

# ルートの登録
app.include_router(chat_router, prefix="", tags=["chat"])
app.include_router(health_router, prefix="", tags=["health"])
app.include_router(recipe_router, prefix="/api", tags=["recipe"])
app.include_router(menu_router, prefix="/api", tags=["menu"])
app.include_router(inventory_router, prefix="/api", tags=["inventory"])
app.include_router(user_router, prefix="/api", tags=["user"])
app.include_router(subscription_router, prefix="/api", tags=["subscription"])


# エラーハンドラー
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """バリデーションエラーの処理"""
    logger.error(f"❌ [API] Validation error: {exc.errors()}")
    logger.error(f"❌ [API] Request body: {await request.body()}")
    
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=f"バリデーションエラー: {exc.errors()}",
            status_code=422,
            timestamp=datetime.now().isoformat(),
            error_type="validation_error"
        ).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """HTTPエラーの処理"""
    logger.error(f"❌ [API] HTTP error: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            status_code=exc.status_code,
            timestamp=datetime.now().isoformat(),
            error_type="http_error"
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """一般的なエラーの処理"""
    logger.error(f"❌ [API] Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="内部サーバーエラーが発生しました",
            status_code=500,
            timestamp=datetime.now().isoformat(),
            error_type="internal_error"
        ).model_dump()
    )


# ルートエンドポイント
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Morizo AI v2 API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


# アプリケーションの起動確認
if __name__ == "__main__":
    import uvicorn
    import os
    
    # 環境変数から設定を取得
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"🚀 [API] Starting Morizo AI v2 on {host}:{port} (reload={reload})...")
    uvicorn.run(app, host=host, port=port, reload=reload)
