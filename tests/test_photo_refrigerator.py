#!/usr/bin/env python3
"""
冷蔵庫画像から在庫新規登録（photo-refrigerator）の単体テスト

実行: python tests/test_photo_refrigerator.py
pytest は使用しない。
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_async(coro):
    """同期テストから async 関数を実行"""
    return asyncio.get_event_loop().run_until_complete(coro)


# --- 1. OCRService.analyze_refrigerator_image のユニットテスト ---

async def test_analyze_refrigerator_image_success():
    """冷蔵庫画像解析: OpenAI が正常 JSON を返した場合、success と items が返る"""
    from services.ocr_service import OCRService

    dummy_content = '''```json
[
  {"item_name": "牛乳", "quantity": 1, "unit": "本", "storage_location": "冷蔵庫", "expiry_date": null},
  {"item_name": "じゃがいも 大", "quantity": 2, "unit": "個", "storage_location": "冷蔵庫", "expiry_date": "2025-03-01"}
]
```'''
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = dummy_content

    mock_create = AsyncMock(return_value=mock_response)
    with patch.object(OCRService, '__init__', lambda self: None):
        svc = OCRService()
        svc.logger = MagicMock()
        svc.client = MagicMock()
        svc.client.chat = MagicMock()
        svc.client.chat.completions = MagicMock()
        svc.client.chat.completions.create = mock_create
        svc.ocr_model = "gpt-4o"
        # normalize_item_name は実装を使う（正規化の確認のため）
        from services.ocr_service import OCRService as RealOCR
        svc.normalize_item_name = RealOCR.normalize_item_name.__get__(svc, RealOCR)

    # JPEG のマジックナンバー + 適当なバイト
    image_bytes = b'\xff\xd8\xff' + b'x' * 200
    result = await svc.analyze_refrigerator_image(image_bytes)

    assert result.get("success") is True, result
    items = result.get("items", [])
    assert len(items) == 2, items
    assert items[0].get("item_name") == "牛乳"
    assert items[0].get("quantity") == 1
    assert items[0].get("unit") == "本"
    # 正規化: "じゃがいも 大" -> "じゃがいも" (末尾の「大」が削除される)
    assert items[1].get("item_name") == "じゃがいも", items[1].get("item_name")


async def test_analyze_refrigerator_image_api_error():
    """冷蔵庫画像解析: API がエラーを返した場合、success=False と error が返る"""
    from services.ocr_service import OCRService

    with patch.object(OCRService, '__init__', lambda self: None):
        svc = OCRService()
        svc.logger = MagicMock()
        svc.client = MagicMock()
        svc.client.chat = MagicMock()
        svc.client.chat.completions = MagicMock()
        svc.client.chat.completions.create = AsyncMock(side_effect=Exception("API rate limit"))

    image_bytes = b'\xff\xd8\xff' + b'x' * 100
    result = await svc.analyze_refrigerator_image(image_bytes)

    assert result.get("success") is False
    assert "error" in result
    assert result.get("items") == []


def test_ocr_service_analyze_refrigerator():
    """analyze_refrigerator_image の成功・失敗を同期ラッパーで実行"""
    run_async(test_analyze_refrigerator_image_success())
    run_async(test_analyze_refrigerator_image_api_error())


# --- 2. POST /api/inventory/photo-refrigerator の API テスト ---

def test_photo_refrigerator_no_auth():
    """認証なしで呼ぶと 401（ミドルウェアが raise する場合もあり）"""
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    from main import app

    client = TestClient(app)
    try:
        response = client.post(
            "/api/inventory/photo-refrigerator",
            files={},  # ファイルなし
        )
        assert response.status_code in (401, 422), (response.status_code, response.json())
    except HTTPException as e:
        assert e.status_code == 401, e


def test_photo_refrigerator_no_image():
    """Body に image がない場合は 422（認証通過時）。認証失敗時は 401 もあり得る"""
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    from main import app

    client = TestClient(app)
    try:
        response = client.post(
            "/api/inventory/photo-refrigerator",
            headers={"Authorization": "Bearer dummy-token"},
            data={},
        )
        assert response.status_code in (401, 422), (response.status_code, response.text)
    except HTTPException as e:
        assert e.status_code == 401, e


def test_photo_refrigerator_invalid_image():
    """不正な画像バイナリの場合は 400"""
    from fastapi.testclient import TestClient
    from main import app

    async def fake_middleware_auth(request):
        return {"user_id": "test-user-id"}

    async def fake_route_auth(request):
        return ("test-user-id", MagicMock())

    with patch("api.middleware.auth.AuthenticationMiddleware._authenticate_request", new_callable=AsyncMock, side_effect=fake_middleware_auth):
        with patch("api.routes.inventory.get_authenticated_user_and_client", new_callable=AsyncMock, side_effect=fake_route_auth):
            client = TestClient(app)
            response = client.post(
                "/api/inventory/photo-refrigerator",
                headers={"Authorization": "Bearer test-token"},
                files={"image": ("test.jpg", b"not an image at all", "image/jpeg")},
            )
    assert response.status_code == 400, (response.status_code, response.json())
    assert "画像" in response.json().get("detail", "")


def test_photo_refrigerator_success():
    """認証・有効画像・解析成功時は 200 と OCRReceiptResponse 形式"""
    from fastapi.testclient import TestClient
    from main import app

    async def fake_middleware_auth(request):
        return {"user_id": "test-user-id"}

    async def fake_route_auth(request):
        return ("test-user-id", MagicMock())

    mock_items = [
        {"item_name": "牛乳", "quantity": 1, "unit": "本", "storage_location": "冷蔵庫", "expiry_date": None}
    ]
    mock_service = MagicMock()
    mock_service.analyze_refrigerator_image = AsyncMock(return_value={"success": True, "items": mock_items})

    with patch("api.middleware.auth.AuthenticationMiddleware._authenticate_request", new_callable=AsyncMock, side_effect=fake_middleware_auth):
        with patch("api.routes.inventory.get_authenticated_user_and_client", new_callable=AsyncMock, side_effect=fake_route_auth):
            with patch("services.ocr_service.OCRService", return_value=mock_service):
                client = TestClient(app)
                jpeg_bytes = b'\xff\xd8\xff' + b'\x00' * 500
                response = client.post(
                    "/api/inventory/photo-refrigerator",
                    headers={"Authorization": "Bearer test-token"},
                    files={"image": ("refrigerator.jpg", jpeg_bytes, "image/jpeg")},
                )

    assert response.status_code == 200, (response.status_code, response.text)
    data = response.json()
    assert data.get("success") is True
    assert "items" in data
    assert data.get("registered_count") == 0
    assert "errors" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["item_name"] == "牛乳"


def run_all():
    print("--- OCRService.analyze_refrigerator_image ---")
    test_ocr_service_analyze_refrigerator()
    print("  OK")

    print("--- POST /api/inventory/photo-refrigerator ---")
    test_photo_refrigerator_no_auth()
    print("  test_photo_refrigerator_no_auth OK")
    test_photo_refrigerator_no_image()
    print("  test_photo_refrigerator_no_image OK")
    test_photo_refrigerator_invalid_image()
    print("  test_photo_refrigerator_invalid_image OK")
    test_photo_refrigerator_success()
    print("  test_photo_refrigerator_success OK")

    print("\nすべてのテストが完了しました。")


if __name__ == "__main__":
    run_all()
