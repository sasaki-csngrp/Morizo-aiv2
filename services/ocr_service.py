#!/usr/bin/env python3
"""
OCRService - レシートOCRサービス

レシート画像を解析して在庫情報を抽出するサービス
"""

import os
import base64
import json
import re
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv
from config.loggers import GenericLogger

load_dotenv()


class OCRService:
    """レシートOCRサービス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "ocr")
        self.ocr_model = os.getenv("OPENAI_OCR_MODEL", "gpt-4o")
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEYが設定されていません")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.logger.info(f"✅ [OCR] OCRService initialized with model: {self.ocr_model}")
    
    async def analyze_receipt_image(
        self,
        image_bytes: bytes
    ) -> Dict[str, Any]:
        """レシート画像を解析して在庫情報を抽出"""
        try:
            self.logger.info("🔍 [OCR] レシート画像解析を開始しました")
            
            # 画像をbase64エンコード
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # OpenAI Vision APIで解析
            try:
                response = await self.client.chat.completions.create(
                    model=self.ocr_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": """このレシート画像から、在庫管理に必要な食材情報を抽出してください。

【重要】item_nameには、食材名のみを抽出してください。
以下の情報は除外してください：
- ブランド名（例: 「新ＢＰ」「ＢＰ」など）
- 商品名・商品説明（例: 「コクのある」「成分無調整」など）
- サイズ表記（例: 「大」「小」「中」「バラ」など）
- 状態表記（例: 「生」「国産」など、ただし食材の種類を特定するために必要な場合は除く）

【良い例】
- 「じゃがいもバラ」→「じゃがいも」
- 「生しいたけ大」→「しいたけ」
- 「新ＢＰコクのある絹豆腐」→「豆腐」
- 「ＢＰ成分無調整牛乳」→「牛乳」
- 「悠々鶏モモ肉国産」→「鶏もも肉」

【悪い例】
- 「じゃがいもバラ」→「じゃがいもバラ」（「バラ」は不要）
- 「新ＢＰコクのある絹豆腐」→「新ＢＰコクのある絹豆腐」（商品名は不要）

抽出すべき情報:
- 商品名（item_name）: 食材名のみ（上記の除外ルールに従う）
- 数量（quantity）
- 単位（unit）
- 保管場所（storage_location、推測可）
- 消費期限（expiry_date、もし記載されていれば）

レスポンス形式: JSON配列
[
  {
    "item_name": "食材名",
    "quantity": 数量,
    "unit": "単位",
    "storage_location": "保管場所",
    "expiry_date": "YYYY-MM-DD または null"
  }
]

日本語のレシートを正確に解析してください。食材名は簡潔に、数量と単位も正しく抽出してください。"""
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.3
                )
            except Exception as api_error:
                # OpenAI APIのエラーを適切に処理
                error_message = str(api_error)
                if "image_parse_error" in error_message or "unsupported image" in error_message.lower():
                    self.logger.error(f"❌ [OCR] 画像解析エラー（画像形式が不正）: {error_message}")
                    return {
                        "success": False,
                        "error": "画像ファイルが正しく解析できませんでした。有効なJPEGまたはPNG画像をアップロードしてください。",
                        "items": []
                    }
                elif "invalid_request_error" in error_message:
                    self.logger.error(f"❌ [OCR] リクエストエラー: {error_message}")
                    return {
                        "success": False,
                        "error": "OCR解析リクエストが無効です。画像ファイルを確認してください。",
                        "items": []
                    }
                else:
                    self.logger.error(f"❌ [OCR] OpenAI APIエラー: {error_message}")
                    return {
                        "success": False,
                        "error": f"OCR解析中にエラーが発生しました: {error_message}",
                        "items": []
                    }
            
            content = response.choices[0].message.content
            self.logger.info(f"✅ [OCR] OCR analysis completed: {len(content)} characters")
            
            # JSONを抽出（Markdownコードブロックから）
            # JSONコードブロックを抽出
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # コードブロックがない場合、直接JSONとして解析を試みる
                json_str = content.strip()
            
            # JSON解析
            items = json.loads(json_str)
            
            if not isinstance(items, list):
                raise ValueError("OCR結果が配列形式ではありません")
            
            # 各アイテムのitem_nameを正規化
            for item in items:
                if "item_name" in item and item["item_name"]:
                    original_name = item["item_name"]
                    normalized_name = self.normalize_item_name(original_name)
                    if original_name != normalized_name:
                        self.logger.debug(f"🔧 [OCR] Normalized item name: '{original_name}' -> '{normalized_name}'")
                    item["item_name"] = normalized_name
            
            self.logger.info(f"✅ [OCR] Extracted {len(items)} items from receipt")
            
            return {
                "success": True,
                "items": items,
                "raw_response": content
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ [OCR] JSON解析エラー: {e}")
            self.logger.error(f"   レスポンス内容: {content[:500]}")
            return {
                "success": False,
                "error": f"JSON解析エラー: {str(e)}",
                "items": []
            }
        except Exception as e:
            self.logger.error(f"❌ [OCR] OCR解析エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "items": []
            }

    async def analyze_refrigerator_image(
        self,
        image_bytes: bytes
    ) -> Dict[str, Any]:
        """冷蔵庫画像を解析して在庫候補を抽出"""
        try:
            self.logger.info("🔍 [OCR] 冷蔵庫画像解析を開始しました")

            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            prompt = """この画像は冷蔵庫（または食品の保存場所）の写真です。
写っている食材・食品を在庫管理用に列挙してください。

抽出すべき情報:
- 商品名（item_name）: 食材名・食品名（簡潔に）
- 数量（quantity）: 見た目から推測できる数（不明なら1）
- 単位（unit）: 個、本、パック、袋など
- 保管場所（storage_location）: 冷蔵庫、冷凍庫など推測で可
- 消費期限（expiry_date）: 写っていればYYYY-MM-DD、なければnull

レスポンス形式: JSON配列のみ。Markdownのコードブロックで囲んでください。
[
  {"item_name": "食材名", "quantity": 数量, "unit": "単位", "storage_location": "保管場所", "expiry_date": "YYYY-MM-DD または null"}
]"""

            try:
                response = await self.client.chat.completions.create(
                    model=self.ocr_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.3
                )
            except Exception as api_error:
                error_message = str(api_error)
                if "image_parse_error" in error_message or "unsupported image" in error_message.lower():
                    self.logger.error(f"❌ [OCR] 冷蔵庫画像解析エラー（画像形式が不正）: {error_message}")
                    return {
                        "success": False,
                        "error": "画像ファイルが正しく解析できませんでした。有効なJPEGまたはPNG画像をアップロードしてください。",
                        "items": []
                    }
                elif "invalid_request_error" in error_message:
                    self.logger.error(f"❌ [OCR] リクエストエラー: {error_message}")
                    return {
                        "success": False,
                        "error": "画像解析リクエストが無効です。画像ファイルを確認してください。",
                        "items": []
                    }
                self.logger.error(f"❌ [OCR] OpenAI APIエラー: {error_message}")
                return {
                    "success": False,
                    "error": f"冷蔵庫画像解析中にエラーが発生しました: {error_message}",
                    "items": []
                }

            content = response.choices[0].message.content
            self.logger.info(f"✅ [OCR] 冷蔵庫画像解析完了: {len(content)} characters")

            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = content.strip()

            items = json.loads(json_str)
            if not isinstance(items, list):
                raise ValueError("解析結果が配列形式ではありません")

            for item in items:
                if "item_name" in item and item["item_name"]:
                    original_name = item["item_name"]
                    normalized_name = self.normalize_item_name(original_name)
                    if original_name != normalized_name:
                        self.logger.debug(f"🔧 [OCR] Normalized item name: '{original_name}' -> '{normalized_name}'")
                    item["item_name"] = normalized_name

            self.logger.info(f"✅ [OCR] 冷蔵庫画像から {len(items)} 件のアイテムを抽出しました")
            return {"success": True, "items": items, "raw_response": content}

        except json.JSONDecodeError as e:
            self.logger.error(f"❌ [OCR] 冷蔵庫画像JSON解析エラー: {e}")
            self.logger.error(f"   レスポンス内容: {content[:500]}")
            return {"success": False, "error": f"JSON解析エラー: {str(e)}", "items": []}
        except Exception as e:
            self.logger.error(f"❌ [OCR] 冷蔵庫画像解析エラー: {e}")
            return {"success": False, "error": str(e), "items": []}

    def normalize_item_name(self, item_name: str) -> str:
        """
        商品名を正規化して食材名のみを抽出
        
        Args:
            item_name: OCRで読み取られた商品名
            
        Returns:
            正規化された食材名
        """
        if not item_name:
            return item_name
        
        normalized = item_name.strip()
        
        # サイズ表記を削除（末尾）
        size_patterns = [
            r'\s*バラ\s*$',
            r'\s*大\s*$',
            r'\s*小\s*$',
            r'\s*中\s*$',
            r'\s*特大\s*$',
            r'\s*特小\s*$',
        ]
        for pattern in size_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # 状態表記を削除（先頭・末尾）
        state_patterns = [
            r'^生\s*',
            r'^国産\s*',
            r'\s*国産\s*$',
            r'^成分無調整\s*',
            r'\s*成分無調整\s*$',
        ]
        for pattern in state_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # ブランド名を削除（先頭）
        brand_patterns = [
            r'^新ＢＰ\s*',
            r'^ＢＰ\s*',
            r'^新\s*',
        ]
        for pattern in brand_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # 商品説明を削除（中間・末尾）
        description_patterns = [
            r'\s*コクのある\s*',
            r'\s*もっちり\s*',
            r'\s*仕込み\s*',
        ]
        for pattern in description_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # 余分な空白を削除
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    async def apply_item_mappings(
        self,
        items: List[Dict[str, Any]],
        client: Any,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        OCR結果に変換テーブルを適用
        
        Args:
            items: OCR解析結果のアイテムリスト
            client: Supabaseクライアント
            user_id: ユーザーID
            
        Returns:
            変換テーブル適用後のアイテムリスト
        """
        try:
            from mcp_servers.ocr_mapping_crud import OCRMappingCRUD
            
            mapping_crud = OCRMappingCRUD()
            
            # 各アイテムのitem_nameを変換テーブルで検索
            for item in items:
                if "item_name" in item and item["item_name"]:
                    original_name = item["item_name"]
                    
                    # 変換テーブルから取得
                    mapping_result = await mapping_crud.get_mapping(
                        client=client,
                        user_id=user_id,
                        original_name=original_name
                    )
                    
                    if mapping_result.get("success") and mapping_result.get("data"):
                        normalized_name = mapping_result["data"]["normalized_name"]
                        if original_name != normalized_name:
                            self.logger.debug(
                                f"🔧 [OCR] Applied mapping: '{original_name}' -> '{normalized_name}'"
                            )
                            item["item_name"] = normalized_name
                    
        except Exception as e:
            # 変換テーブル適用が失敗しても、既存の処理は継続
            self.logger.warning(f"⚠️ [OCR] アイテムマッピングの適用に失敗しました: {e}")
        
        return items
    
    async def extract_inventory_items(
        self,
        image_bytes: bytes
    ) -> List[Dict[str, Any]]:
        """レシート画像から在庫アイテムのリストを抽出"""
        result = await self.analyze_receipt_image(image_bytes)
        
        if result.get("success"):
            return result.get("items", [])
        else:
            raise Exception(result.get("error", "OCR解析に失敗しました"))

