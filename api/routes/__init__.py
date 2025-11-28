#!/usr/bin/env python3
"""
API層 - ルート定義

チャットとヘルスチェックルートの統合
"""

from .chat import router as chat_router
from .health import router as health_router
from .recipe import router as recipe_router
from .menu import router as menu_router
from .inventory import router as inventory_router
from .user import router as user_router

__all__ = [
    'chat_router',
    'health_router',
    'recipe_router',
    'menu_router',
    'inventory_router',
    'user_router'
]
