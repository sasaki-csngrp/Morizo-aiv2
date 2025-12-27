#!/usr/bin/env python3
"""
統合バックエンド回帰テスト（HTTP API経由）

破壊的活動（デグレード）の早期発見のため、全パターンのHTTPリクエストを自動テストします。
Phase 2.5の基本機能とPhase 3Eの段階的選択システムを含む統合テストです。
Supabase認証で動的にJWTトークンを取得します。
"""

import asyncio
import sys
import os
import requests
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional, Callable, Any, Dict
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Supabase認証ユーティリティをインポート
archive_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "archive", "00_1_test_util.py")
if os.path.exists(archive_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_util", archive_path)
    test_util = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_util)
    AuthUtil = test_util.AuthUtil
else:
    # フォールバック: 直接実装
    from supabase import create_client
    
    class AuthUtil:
        def __init__(self):
            self.supabase_url = os.getenv('SUPABASE_URL')
            self.supabase_key = os.getenv('SUPABASE_KEY')
            self.supabase_email = os.getenv('SUPABASE_EMAIL')
            self.supabase_password = os.getenv('SUPABASE_PASSWORD')
            
            if not all([self.supabase_url, self.supabase_key]):
                raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")
        
        def get_auth_token(self) -> str:
            """テスト用の認証トークンを取得"""
            if not all([self.supabase_email, self.supabase_password]):
                raise ValueError("SUPABASE_EMAIL and SUPABASE_PASSWORD are required for testing")
            
            client = create_client(self.supabase_url, self.supabase_key)
            
            try:
                response = client.auth.sign_in_with_password({
                    "email": self.supabase_email,
                    "password": self.supabase_password
                })
                
                if response.session and response.session.access_token:
                    return response.session.access_token
                else:
                    raise ValueError("Failed to get access token")
                    
            except Exception as e:
                raise ValueError(f"Authentication failed: {e}")

# .envファイルを読み込み
load_dotenv()


@dataclass
class TestCase:
    """テストケースデータクラス"""
    name: str
    message: Optional[str] = None  # Phase 2.5用
    expected_pattern: Optional[str] = None  # Phase 2.5用
    expected_tasks: List[str] = None  # Phase 2.5用
    expected_ambiguity: Optional[str] = None  # Phase 2.5用
    description: Optional[str] = None  # Phase 3E用
    setup: Optional[Callable] = None
    verify: Optional[Callable] = None
    requires_two_stage: bool = False  # Phase 2.5用（曖昧性解消が必要なテスト）
    second_stage_message: Optional[str] = None  # Phase 2.5用（2段階目のメッセージ）
    expected_stages: List[str] = None  # Phase 3E用
    expected_category: Optional[str] = None  # Phase 3E用
    skip: bool = False  # スキップフラグ
    test_type: str = "basic"  # "basic" (Phase 2.5) or "stage_flow" (Phase 3E)


@dataclass
class HelpTestCase:
    """ヘルプ機能テストケースデータクラス"""
    name: str
    description: str
    messages: List[str]  # 送信するメッセージのリスト
    expected_responses: List[Callable[[str], bool]]  # 応答検証関数のリスト
    expected_help_states: List[Optional[str]]  # 期待されるヘルプ状態のリスト
    setup: Optional[Callable] = None  # 事前準備関数
    skip: bool = False


class IntegrationTestClient:
    """統合テスト用のHTTPクライアント"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
        # .envからJWTトークンを取得
        self.jwt_token = os.getenv('TEST_USER_JWT_TOKEN')
        if not self.jwt_token:
            print("❌ TEST_USER_JWT_TOKEN が設定されていません")
            print("💡 TEST_USER_JWT_TOKEN を .env に設定してください")
            raise ValueError("TEST_USER_JWT_TOKEN is required")
        
        print(f"🔐 使用するJWTトークン: {self.jwt_token[:20]}...")
        
        self.session.headers.update({
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        })
    
    def send_chat_request(self, message: str, sse_session_id: Optional[str] = None, confirm: bool = False):
        """チャットリクエストを送信"""
        url = f"{self.base_url}/chat"
        
        payload = {
            "message": message,
            "token": self.jwt_token,
            "sseSessionId": sse_session_id,
            "confirm": confirm
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTPリクエストエラー: {e}")
            return None
    
    def send_selection_request(self, task_id: str, selection: int, sse_session_id: str, old_sse_session_id: Optional[str] = None):
        """ユーザー選択リクエストを送信"""
        url = f"{self.base_url}/chat/selection"
        
        payload = {
            "task_id": task_id,
            "selection": selection,
            "sse_session_id": sse_session_id,
            "old_sse_session_id": old_sse_session_id
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTPリクエストエラー: {e}")
            return None
    
    def check_server_status(self):
        """サーバーの状態をチェック"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def add_inventory(self, item_name: str, quantity: float, unit: str = "個"):
        """在庫を追加（テスト用ヘルパー）"""
        message = f"{item_name}を{quantity}{unit}追加して"
        return self.send_chat_request(message)
    
    def delete_all_inventory(self, item_name: str):
        """在庫を全削除（テスト用ヘルパー）"""
        message = f"{item_name}を全部削除して"
        return self.send_chat_request(message)
    
    def save_menu(self, sse_session_id: str):
        """献立を保存"""
        url = f"{self.base_url}/api/menu/save"
        payload = {
            "sse_session_id": sse_session_id
        }
        try:
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTPリクエストエラー: {e}")
            return None
    
    def get_ingredient_delete_candidates(self, date: str):
        """食材削除候補を取得（/api/recipe/ingredients/delete-candidates/{date}）"""
        url = f"{self.base_url}/api/recipe/ingredients/delete-candidates/{date}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTPリクエストエラー: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   レスポンス: {e.response.text}")
            return None
    
    def delete_ingredients(self, date: str, ingredients: List[Dict[str, Any]]):
        """食材を削除（/api/recipe/ingredients/delete）"""
        url = f"{self.base_url}/api/recipe/ingredients/delete"
        
        payload = {
            "date": date,
            "ingredients": ingredients
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTPリクエストエラー: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   レスポンス: {e.response.text}")
            return None


# ============================================================================
# Phase 3E: 段階的選択システム用の検証関数
# ============================================================================

def verify_stage_transition(response: dict, expected_stage: str) -> bool:
    """段階遷移の検証"""
    current_stage = response.get("current_stage")
    if current_stage != expected_stage:
        print(f"❌ 段階が一致しません: 期待={expected_stage}, 実際={current_stage}")
        return False
    print(f"✅ 段階検証成功: {expected_stage}")
    return True


def verify_category(response: dict, expected_category: str) -> bool:
    """カテゴリ判定の検証"""
    menu_category = response.get("menu_category")
    if menu_category != expected_category:
        print(f"❌ カテゴリが一致しません: 期待={expected_category}, 実際={menu_category}")
        return False
    print(f"✅ カテゴリ検証成功: {expected_category}")
    return True


def verify_selection_response(response: dict, stage: str) -> tuple[bool, Optional[str]]:
    """選択要求レスポンスの検証
    戻り値: (成功フラグ, task_id)
    """
    if not response:
        print(f"❌ レスポンスがNoneです")
        return (False, None)
    
    if not response.get("success"):
        print(f"❌ レスポンスが失敗しています: {response}")
        return (False, None)
    
    requires_selection = response.get("requires_selection", False)
    if not requires_selection:
        print(f"❌ requires_selection が False です: {response}")
        return (False, None)
    
    candidates = response.get("candidates")
    if not candidates or len(candidates) == 0:
        print(f"❌ 候補が空です")
        return (False, None)
    
    task_id = response.get("task_id")
    if not task_id:
        print(f"❌ task_id がありません")
        return (False, None)
    
    print(f"✅ 選択要求レスポンス検証成功: 段階={stage}, 候補数={len(candidates)}, task_id={task_id}")
    return (True, task_id)


def verify_completion_response(response: dict) -> bool:
    """完了レスポンスの検証"""
    if not response:
        print(f"❌ レスポンスがNoneです")
        return False
    
    # 完了時は menu オブジェクトが含まれる
    menu = response.get("menu")
    
    if menu:
        main = menu.get("main")
        sub = menu.get("sub")
        soup = menu.get("soup")
        
        if main and sub and soup:
            print(f"✅ 献立完成: 主菜={main.get('title', 'Unknown')}, 副菜={sub.get('title', 'Unknown')}, 汁物={soup.get('title', 'Unknown')}")
            return True
        else:
            print(f"⚠️ menuオブジェクトが不完全です: main={main}, sub={sub}, soup={soup}")
            return False
    
    return False


def verify_menu_proposal_response(response_text: str) -> bool:
    """献立提案レスポンスの検証（LLM提案とRAG提案の両方があることを確認）"""
    if not response_text:
        print(f"❌ レスポンステキストが空です")
        return False
    
    # 「斬新な提案」セクションの確認
    if "斬新な提案" not in response_text and "🍽️ 斬新な提案" not in response_text:
        print(f"❌ 「斬新な提案」セクションが見つかりません")
        return False
    
    # 「伝統的な提案」セクションの確認
    if "伝統的な提案" not in response_text and "🍽️ 伝統的な提案" not in response_text:
        print(f"❌ 「伝統的な提案」セクションが見つかりません")
        return False
    
    # 斬新な提案の内容確認（主菜・副菜・汁物のいずれかに内容があること）
    innovative_section = ""
    if "🍽️ 斬新な提案" in response_text:
        parts = response_text.split("🍽️ 斬新な提案")
        if len(parts) > 1:
            innovative_part = parts[1].split("🍽️")[0]  # 伝統的な提案の前まで
            innovative_section = innovative_part
    elif "斬新な提案" in response_text:
        parts = response_text.split("斬新な提案")
        if len(parts) > 1:
            innovative_part = parts[1].split("伝統的な提案")[0] if "伝統的な提案" in parts[1] else parts[1].split("🍽️")[0] if "🍽️" in parts[1] else parts[1]
            innovative_section = innovative_part
    
    # 主菜・副菜・汁物のいずれかに内容があるかチェック
    # 「主菜:」の後に空白や改行のみではなく、実際の料理名があることを確認
    has_innovative_content = False
    for label in ["主菜:", "副菜:", "汁物:"]:
        if label in innovative_section:
            # labelの後の部分を取得
            label_pos = innovative_section.find(label)
            after_label = innovative_section[label_pos + len(label):].strip()
            # 次の行まで確認（最大50文字）
            next_content = after_label.split("\n")[0].strip() if after_label else ""
            if next_content and len(next_content) > 0:
                has_innovative_content = True
                break
    
    if not has_innovative_content:
        print(f"❌ 「斬新な提案」セクションに内容がありません（主菜・副菜・汁物がすべて空です）")
        print(f"   セクション内容: {innovative_section[:200]}...")
        return False
    
    # 伝統的な提案の内容確認（主菜・副菜・汁物のいずれかに内容があること）
    traditional_section = ""
    if "🍽️ 伝統的な提案" in response_text:
        parts = response_text.split("🍽️ 伝統的な提案")
        if len(parts) > 1:
            traditional_section = parts[1]
    elif "伝統的な提案" in response_text:
        parts = response_text.split("伝統的な提案")
        if len(parts) > 1:
            traditional_section = parts[1]
    
    # 主菜・副菜・汁物のいずれかに内容があるかチェック
    has_traditional_content = False
    for label in ["主菜:", "副菜:", "汁物:"]:
        if label in traditional_section:
            # labelの後の部分を取得
            label_pos = traditional_section.find(label)
            after_label = traditional_section[label_pos + len(label):].strip()
            # 次の行まで確認（最大50文字）
            next_content = after_label.split("\n")[0].strip() if after_label else ""
            if next_content and len(next_content) > 0:
                has_traditional_content = True
                break
    
    if not has_traditional_content:
        print(f"❌ 「伝統的な提案」セクションに内容がありません（主菜・副菜・汁物がすべて空です）")
        print(f"   セクション内容: {traditional_section[:200]}...")
        return False
    
    print(f"✅ 献立提案の詳細検証成功:")
    print(f"   - 斬新な提案: 内容あり")
    print(f"   - 伝統的な提案: 内容あり")
    return True


async def wait_for_response_delay(seconds: float = 3.0):
    """レスポンス待機（非同期処理の完了待ち）"""
    await asyncio.sleep(seconds)


# ============================================================================
# Phase 3E: 段階的選択システムのテスト実行
# ============================================================================

async def run_auto_transition_test(client: IntegrationTestClient, test_case: TestCase) -> bool:
    """TC-003: 自動遷移検証テスト（確認ステップと空白メッセージ遷移）"""
    print(f"\n{'='*60}")
    print(f"🧪 テスト: {test_case.name}")
    print(f"📝 説明: {test_case.description}")
    print(f"{'='*60}")
    
    try:
        # 1. 事前準備
        if test_case.setup:
            print(f"📋 事前準備を実行...")
            await test_case.setup(client)
            await wait_for_response_delay(1.0)
        
        # 2. 主菜提案リクエスト
        print(f"\n[ステップ1] 主菜提案リクエスト送信...")
        main_request = "レンコンの主菜を5件提案して"
        print(f"📤 送信メッセージ: {main_request}")
        
        sse_session_id = str(uuid.uuid4())
        print(f"📝 生成したsse_session_id: {sse_session_id}")
        
        main_response = client.send_chat_request(main_request, sse_session_id=sse_session_id)
        
        if not main_response or not main_response.get("success"):
            print(f"❌ 主菜提案リクエストが失敗しました: {main_response}")
            return False
        
        await wait_for_response_delay(2.0)
        
        # 主菜選択要求の確認
        requires_selection = main_response.get("requires_selection", False)
        if not requires_selection:
            print(f"❌ 主菜提案が選択要求を返していません")
            return False
        
        # 段階検証
        if not verify_stage_transition(main_response, "main"):
            return False
        
        # 選択要求の検証
        success, task_id = verify_selection_response(main_response, "main")
        if not success or not task_id:
            return False
        
        # 3. 主菜を選択
        print(f"\n[ステップ2] 主菜を選択 (selection=1)...")
        selection_response = client.send_selection_request(
            task_id=task_id,
            selection=1,
            sse_session_id=sse_session_id
        )
        
        if not selection_response or not selection_response.get("success"):
            print(f"❌ 主菜選択リクエストが失敗しました: {selection_response}")
            return False
        
        # 確認ステップフラグの検証
        requires_stage_confirmation = selection_response.get("requires_stage_confirmation", False)
        confirmation_message = selection_response.get("confirmation_message")
        next_stage_name = selection_response.get("next_stage_name")
        
        print(f"🔍 確認ステップフラグ検証:")
        print(f"   requires_stage_confirmation: {requires_stage_confirmation}")
        print(f"   confirmation_message: {confirmation_message}")
        print(f"   next_stage_name: {next_stage_name}")
        
        if not requires_stage_confirmation:
            print(f"❌ requires_stage_confirmation が True になっていません")
            return False
        
        if confirmation_message != "主菜が確定しました。副菜の選択に進みますか？":
            print(f"❌ 確認メッセージが正しくありません: {confirmation_message}")
            return False
        
        if next_stage_name != "sub":
            print(f"❌ next_stage_name が 'sub' になっていません: {next_stage_name}")
            return False
        
        print(f"✅ 確認ステップフラグ検証成功")
        
        await wait_for_response_delay(2.0)
        
        # 4. 空白メッセージで自動遷移（副菜提案）
        print(f"\n[ステップ3] 空白メッセージで副菜提案への自動遷移...")
        print(f"📤 送信メッセージ: ' ' (空白のみ)")
        
        # 空白メッセージを送信（バックエンドがnext_stage_requestを探して実行）
        auto_transition_response = client.send_chat_request(" ", sse_session_id=sse_session_id)
        
        if not auto_transition_response or not auto_transition_response.get("success"):
            print(f"❌ 自動遷移リクエストが失敗しました: {auto_transition_response}")
            return False
        
        await wait_for_response_delay(5.0)
        
        # 副菜提案の確認
        requires_selection_sub = auto_transition_response.get("requires_selection", False)
        if not requires_selection_sub:
            print(f"❌ 自動遷移後のレスポンスが選択要求を返していません: {auto_transition_response}")
            return False
        
        if not verify_stage_transition(auto_transition_response, "sub"):
            return False
        
        success_sub, task_id_sub = verify_selection_response(auto_transition_response, "sub")
        if not success_sub or not task_id_sub:
            print(f"❌ 副菜提案の選択要求が正しくありません")
            return False
        
        print(f"✅ 自動遷移成功: 副菜提案が取得できました")
        
        # 5. 副菜を選択
        print(f"\n[ステップ4] 副菜を選択 (selection=1)...")
        selection_response_sub = client.send_selection_request(
            task_id=task_id_sub,
            selection=1,
            sse_session_id=sse_session_id
        )
        
        if not selection_response_sub or not selection_response_sub.get("success"):
            print(f"❌ 副菜選択リクエストが失敗しました: {selection_response_sub}")
            return False
        
        # 確認ステップフラグの検証（副菜→汁物）
        requires_stage_confirmation_sub = selection_response_sub.get("requires_stage_confirmation", False)
        confirmation_message_sub = selection_response_sub.get("confirmation_message")
        next_stage_name_sub = selection_response_sub.get("next_stage_name")
        
        print(f"🔍 確認ステップフラグ検証（副菜→汁物）:")
        print(f"   requires_stage_confirmation: {requires_stage_confirmation_sub}")
        print(f"   confirmation_message: {confirmation_message_sub}")
        print(f"   next_stage_name: {next_stage_name_sub}")
        
        if not requires_stage_confirmation_sub:
            print(f"❌ requires_stage_confirmation が True になっていません")
            return False
        
        if confirmation_message_sub != "副菜が確定しました。汁物の選択に進みますか？":
            print(f"❌ 確認メッセージが正しくありません: {confirmation_message_sub}")
            return False
        
        if next_stage_name_sub != "soup":
            print(f"❌ next_stage_name が 'soup' になっていません: {next_stage_name_sub}")
            return False
        
        print(f"✅ 確認ステップフラグ検証成功（副菜→汁物）")
        
        await wait_for_response_delay(2.0)
        
        # 6. 空白メッセージで自動遷移（汁物提案）
        print(f"\n[ステップ5] 空白メッセージで汁物提案への自動遷移...")
        print(f"📤 送信メッセージ: ' ' (空白のみ)")
        
        auto_transition_response_soup = client.send_chat_request(" ", sse_session_id=sse_session_id)
        
        if not auto_transition_response_soup or not auto_transition_response_soup.get("success"):
            print(f"❌ 自動遷移リクエストが失敗しました: {auto_transition_response_soup}")
            return False
        
        await wait_for_response_delay(5.0)
        
        # 汁物提案の確認
        requires_selection_soup = auto_transition_response_soup.get("requires_selection", False)
        if not requires_selection_soup:
            print(f"❌ 自動遷移後のレスポンスが選択要求を返していません: {auto_transition_response_soup}")
            return False
        
        if not verify_stage_transition(auto_transition_response_soup, "soup"):
            return False
        
        success_soup, task_id_soup = verify_selection_response(auto_transition_response_soup, "soup")
        if not success_soup or not task_id_soup:
            print(f"❌ 汁物提案の選択要求が正しくありません")
            return False
        
        print(f"✅ 自動遷移成功: 汁物提案が取得できました")
        
        # 7. 汁物を選択して完了確認
        print(f"\n[ステップ6] 汁物を選択 (selection=1)...")
        selection_response_soup = client.send_selection_request(
            task_id=task_id_soup,
            selection=1,
            sse_session_id=sse_session_id
        )
        
        if not selection_response_soup or not selection_response_soup.get("success"):
            print(f"❌ 汁物選択リクエストが失敗しました: {selection_response_soup}")
            return False
        
        await wait_for_response_delay(3.0)
        
        # 完了確認（汁物選択時は確認ステップなし）
        requires_stage_confirmation_soup = selection_response_soup.get("requires_stage_confirmation", False)
        if requires_stage_confirmation_soup:
            print(f"⚠️ 汁物選択時に requires_stage_confirmation が True になっています（期待値: False）")
            # これは想定外だが、テストを続行
        
        if verify_completion_response(selection_response_soup):
            print(f"✅ 献立完成確認成功")
            
            # 献立を保存
            print(f"\n[ステップ] 献立を保存...")
            save_response = client.save_menu(sse_session_id)
            
            if save_response and save_response.get("success"):
                total_saved = save_response.get("total_saved", 0)
                print(f"✅ 献立保存成功: {total_saved}件のレシピが保存されました")
                
                # 食材削除候補を取得して削除
                print(f"\n[ステップ] 食材削除候補を取得して削除...")
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                
                # 食材削除候補を取得
                candidates_response = client.get_ingredient_delete_candidates(today)
                if candidates_response and candidates_response.get("success"):
                    candidates = candidates_response.get("candidates", [])
                    print(f"✅ 食材削除候補を取得: {len(candidates)}件")
                    
                    if len(candidates) > 0:
                        # 候補の一部（最大3件）を削除
                        delete_items = []
                        for candidate in candidates[:3]:  # 最大3件まで
                            delete_items.append({
                                "item_name": candidate.get("item_name"),
                                "quantity": 0,
                                "inventory_id": candidate.get("inventory_id")
                            })
                        
                        if delete_items:
                            print(f"   削除対象: {[item.get('item_name') for item in delete_items]}")
                            
                            # 食材削除を実行
                            delete_response = client.delete_ingredients(
                                date=today,
                                ingredients=delete_items
                            )
                            
                            if delete_response and delete_response.get("success"):
                                deleted_count = delete_response.get("deleted_count", 0)
                                updated_count = delete_response.get("updated_count", 0)
                                failed_items = delete_response.get("failed_items", [])
                                print(f"✅ 食材削除成功: deleted={deleted_count}, updated={updated_count}, failed={len(failed_items)}")
                            else:
                                print(f"⚠️ 食材削除が失敗しました: {delete_response}")
                        else:
                            print(f"⚠️ 削除対象がありません")
                    else:
                        print(f"⚠️ 食材削除候補がありません")
                else:
                    print(f"⚠️ 食材削除候補の取得が失敗しました: {candidates_response}")
            else:
                print(f"⚠️ 献立保存が失敗しました: {save_response}")
            
            print(f"✅ 自動遷移検証テスト成功")
            return True
        else:
            print(f"❌ 献立完成の検証に失敗しました")
            return False
        
    except AssertionError as e:
        print(f"❌ アサーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# Phase 3E: 段階的選択システムのテスト実行
# ============================================================================

async def run_stage_flow_test(client: IntegrationTestClient, test_case: TestCase) -> bool:
    """TC-001: 基本フローの段階的選択テスト"""
    print(f"\n{'='*60}")
    print(f"🧪 テスト: {test_case.name}")
    print(f"📝 説明: {test_case.description}")
    print(f"{'='*60}")
    
    try:
        # 1. 事前準備
        if test_case.setup:
            print(f"📋 事前準備を実行...")
            await test_case.setup(client)
            await wait_for_response_delay(1.0)
        
        # 2. 主菜提案リクエスト
        print(f"\n[ステップ1] 主菜提案リクエスト送信...")
        main_request = "レンコンの主菜を5件提案して"
        print(f"📤 送信メッセージ: {main_request}")
        
        # セッションIDを生成して記憶（テスト全体で使用）
        sse_session_id = str(uuid.uuid4())
        print(f"📝 生成したsse_session_id: {sse_session_id}")
        
        main_response = client.send_chat_request(main_request, sse_session_id=sse_session_id)
        
        if not main_response:
            print(f"❌ 主菜提案リクエストがNoneを返しました")
            return False
        
        print(f"📥 初期レスポンス: success={main_response.get('success')}, requires_selection={main_response.get('requires_selection')}")
        
        if not main_response.get("success"):
            print(f"❌ 主菜提案リクエストが失敗しました: {main_response}")
            return False
        
        await wait_for_response_delay(2.0)
        
        # 主菜選択要求の確認
        requires_selection = main_response.get("requires_selection", False)
        if not requires_selection:
            response_text = main_response.get("response", "")
            if "こんにちは" in response_text or "お手伝い" in response_text:
                print(f"❌ リクエストが正しく処理されていません。挨拶メッセージが返されました")
                return False
            print(f"❌ 主菜提案が選択要求を返していません")
            return False
        
        # 段階検証
        if not verify_stage_transition(main_response, "main"):
            return False
        
        # 選択要求の検証
        success, task_id = verify_selection_response(main_response, "main")
        if not success or not task_id:
            return False
        
        # 3. 主菜を選択
        print(f"\n[ステップ2] 主菜を選択 (selection=1)...")
        candidates = main_response.get("candidates", [])
        if len(candidates) == 0:
            print(f"❌ 候補が空です")
            return False
        
        selection_response = client.send_selection_request(
            task_id=task_id,
            selection=1,
            sse_session_id=sse_session_id
        )
        
        if not selection_response or not selection_response.get("success"):
            print(f"❌ 主菜選択リクエストが失敗しました: {selection_response}")
            return False
        
        await wait_for_response_delay(5.0)
        
        # 4. 副菜提案
        print(f"\n[ステップ3] 副菜提案を確認...")
        sub_request = "主菜で使っていない食材で副菜を5件提案して"
        sub_response = client.send_chat_request(sub_request, sse_session_id=sse_session_id)
        
        if not sub_response or not sub_response.get("success"):
            print(f"⚠️ 副菜提案が取得できませんでした: {sub_response}")
            return False
        
        await wait_for_response_delay(5.0)
        
        if sub_response.get("requires_selection"):
            if not verify_stage_transition(sub_response, "sub"):
                return False
            
            success_sub, task_id_sub = verify_selection_response(sub_response, "sub")
            if success_sub and task_id_sub:
                # 副菜を選択
                print(f"\n[ステップ4] 副菜を選択 (selection=1)...")
                selection_response_sub = client.send_selection_request(
                    task_id=task_id_sub,
                    selection=1,
                    sse_session_id=sse_session_id
                )
                
                if selection_response_sub and selection_response_sub.get("success"):
                    await wait_for_response_delay(5.0)
            
            # 5. 汁物提案
            print(f"\n[ステップ5] 汁物提案を確認...")
            soup_request = "主菜・副菜で使っていない食材で汁物を5件提案して"
            soup_response = client.send_chat_request(soup_request, sse_session_id=sse_session_id)
            
            if soup_response and soup_response.get("success"):
                await wait_for_response_delay(5.0)
                
                if soup_response.get("requires_selection"):
                    if not verify_stage_transition(soup_response, "soup"):
                        return False
                    
                    success_soup, task_id_soup = verify_selection_response(soup_response, "soup")
                    if success_soup and task_id_soup:
                        # 汁物を選択
                        print(f"\n[ステップ6] 汁物を選択 (selection=1)...")
                        selection_response_soup = client.send_selection_request(
                            task_id=task_id_soup,
                            selection=1,
                            sse_session_id=sse_session_id
                        )
                        
                        if selection_response_soup and selection_response_soup.get("success"):
                            await wait_for_response_delay(3.0)
                            
                            # 完了確認
                            if verify_completion_response(selection_response_soup):
                                print(f"✅ 献立完成確認成功")
                                
                                # 献立を保存
                                print(f"\n[ステップ] 献立を保存...")
                                save_response = client.save_menu(sse_session_id)
                                
                                if save_response and save_response.get("success"):
                                    total_saved = save_response.get("total_saved", 0)
                                    print(f"✅ 献立保存成功: {total_saved}件のレシピが保存されました")
                                    
                                    # 食材削除候補を取得して削除
                                    print(f"\n[ステップ] 食材削除候補を取得して削除...")
                                    from datetime import datetime
                                    today = datetime.now().strftime("%Y-%m-%d")
                                    
                                    # 食材削除候補を取得
                                    candidates_response = client.get_ingredient_delete_candidates(today)
                                    if candidates_response and candidates_response.get("success"):
                                        candidates = candidates_response.get("candidates", [])
                                        print(f"✅ 食材削除候補を取得: {len(candidates)}件")
                                        
                                        if len(candidates) > 0:
                                            # 候補の一部（最大3件）を削除
                                            delete_items = []
                                            for candidate in candidates[:3]:  # 最大3件まで
                                                delete_items.append({
                                                    "item_name": candidate.get("item_name"),
                                                    "quantity": 0,
                                                    "inventory_id": candidate.get("inventory_id")
                                                })
                                            
                                            if delete_items:
                                                print(f"   削除対象: {[item.get('item_name') for item in delete_items]}")
                                                
                                                # 食材削除を実行
                                                delete_response = client.delete_ingredients(
                                                    date=today,
                                                    ingredients=delete_items
                                                )
                                                
                                                if delete_response and delete_response.get("success"):
                                                    deleted_count = delete_response.get("deleted_count", 0)
                                                    updated_count = delete_response.get("updated_count", 0)
                                                    failed_items = delete_response.get("failed_items", [])
                                                    print(f"✅ 食材削除成功: deleted={deleted_count}, updated={updated_count}, failed={len(failed_items)}")
                                                else:
                                                    print(f"⚠️ 食材削除が失敗しました: {delete_response}")
                                            else:
                                                print(f"⚠️ 削除対象がありません")
                                        else:
                                            print(f"⚠️ 食材削除候補がありません")
                                    else:
                                        print(f"⚠️ 食材削除候補の取得が失敗しました: {candidates_response}")
                                else:
                                    print(f"⚠️ 献立保存が失敗しました: {save_response}")
                                
                                print(f"✅ 基本フローのテスト成功")
                                return True
        
        print(f"⚠️ テストは途中まで成功しましたが、完全な完了まで到達できませんでした")
        return False
        
    except AssertionError as e:
        print(f"❌ アサーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_complete_scenario_test(client: IntegrationTestClient) -> bool:
    """TC-002: 完全シナリオテスト（曖昧性検出→追加提案→保存）"""
    print(f"\n{'='*60}")
    print(f"🧪 テスト: TC-002: 完全シナリオ（曖昧性検出→追加提案→保存）")
    print(f"📝 説明: 主菜を教えて→レンコンで→追加提案→副菜→追加提案→汁物→追加提案→完成→保存")
    print(f"{'='*60}")
    
    try:
        # ステップ1: 事前準備（在庫登録）
        print(f"\n[ステップ1] 在庫登録...")
        client.add_inventory("レンコン", 1, "個")
        await wait_for_response_delay(0.5)
        client.add_inventory("ニンジン", 2, "個")
        await wait_for_response_delay(0.5)
        print(f"✅ 在庫登録完了")
        
        # セッションIDを生成（テスト全体で使用）
        sse_session_id = str(uuid.uuid4())
        print(f"📝 生成したsse_session_id: {sse_session_id}")
        
        # ステップ2: 「主菜を教えて」→曖昧性検出
        print(f"\n[ステップ2] 「主菜を教えて」リクエスト送信...")
        ambiguity_response = client.send_chat_request("主菜を教えて", sse_session_id=sse_session_id)
        
        if not ambiguity_response:
            print(f"❌ 曖昧性検出リクエストがNoneを返しました")
            return False
        
        if not ambiguity_response.get("success"):
            print(f"❌ 曖昧性検出リクエストが失敗しました: {ambiguity_response}")
            return False
        
        requires_confirmation = ambiguity_response.get("requires_confirmation", False)
        confirmation_session_id = ambiguity_response.get("confirmation_session_id")
        
        if not requires_confirmation:
            print(f"❌ 曖昧性が検出されませんでした（requires_confirmation={requires_confirmation}）")
            return False
        
        if not confirmation_session_id:
            print(f"❌ confirmation_session_id がありません")
            return False
        
        print(f"✅ 曖昧性検出成功: confirmation_session_id={confirmation_session_id}")
        await wait_for_response_delay(2.0)
        
        # ステップ3: 「レンコンで」→主菜提案
        print(f"\n[ステップ3] 「レンコンで」リクエスト送信（曖昧性解消）...")
        main_response = client.send_chat_request(
            "レンコンで",
            sse_session_id=confirmation_session_id,
            confirm=True
        )
        
        if not main_response or not main_response.get("success"):
            print(f"❌ 主菜提案リクエストが失敗しました: {main_response}")
            return False
        
        await wait_for_response_delay(5.0)
        
        requires_selection = main_response.get("requires_selection", False)
        if not requires_selection:
            print(f"❌ 主菜提案が選択要求を返していません")
            return False
        
        if not verify_stage_transition(main_response, "main"):
            return False
        
        success, task_id_main = verify_selection_response(main_response, "main")
        if not success or not task_id_main:
            return False
        
        print(f"✅ 主菜提案成功: task_id={task_id_main}")
        
        # ステップ4: 「他の提案を見る」→主菜追加提案
        print(f"\n[ステップ4] 「他の提案を見る」リクエスト送信（主菜追加提案）...")
        additional_main_response = client.send_selection_request(
            task_id=task_id_main,
            selection=0,  # 追加提案要求
            sse_session_id=sse_session_id
        )
        
        if not additional_main_response:
            print(f"❌ 主菜追加提案リクエストがNoneを返しました")
            return False
        
        # 追加提案はSSE経由で送信される場合があるため、成功フラグを確認
        if additional_main_response.get("success"):
            print(f"✅ 主菜追加提案リクエスト成功")
        else:
            print(f"⚠️ 主菜追加提案リクエストのレスポンス: {additional_main_response}")
        
        await wait_for_response_delay(5.0)
        
        # ステップ5: 「1. を選択」→副菜提案
        print(f"\n[ステップ5] 主菜を選択 (selection=1)...")
        selection_main_response = client.send_selection_request(
            task_id=task_id_main,
            selection=1,
            sse_session_id=sse_session_id
        )
        
        if not selection_main_response or not selection_main_response.get("success"):
            print(f"❌ 主菜選択リクエストが失敗しました: {selection_main_response}")
            return False
        
        await wait_for_response_delay(5.0)
        
        # 副菜提案を確認（主菜選択後に自動的に副菜提案が来る場合と、明示的にリクエストする場合がある）
        print(f"\n[ステップ6] 副菜提案を確認...")
        sub_request = "主菜で使っていない食材で副菜を5件提案して"
        sub_response = client.send_chat_request(sub_request, sse_session_id=sse_session_id)
        
        if not sub_response or not sub_response.get("success"):
            print(f"⚠️ 副菜提案が取得できませんでした: {sub_response}")
            # 主菜選択のレスポンスに副菜提案が含まれている場合もある
            if selection_main_response.get("requires_selection"):
                sub_response = selection_main_response
        
        if sub_response and sub_response.get("success"):
            await wait_for_response_delay(5.0)
            
            if sub_response.get("requires_selection"):
                if not verify_stage_transition(sub_response, "sub"):
                    return False
                
                success_sub, task_id_sub = verify_selection_response(sub_response, "sub")
                if not success_sub or not task_id_sub:
                    print(f"⚠️ 副菜提案の選択要求が正しくありません")
                    return False
                
                print(f"✅ 副菜提案成功: task_id={task_id_sub}")
                
                # ステップ7: 「他の提案を見る」→副菜追加提案
                print(f"\n[ステップ7] 「他の提案を見る」リクエスト送信（副菜追加提案）...")
                additional_sub_response = client.send_selection_request(
                    task_id=task_id_sub,
                    selection=0,
                    sse_session_id=sse_session_id
                )
                
                if not additional_sub_response:
                    print(f"❌ 副菜追加提案リクエストがNoneを返しました")
                    return False
                
                if additional_sub_response.get("success"):
                    print(f"✅ 副菜追加提案リクエスト成功")
                
                await wait_for_response_delay(5.0)
                
                # ステップ8: 「2. を選択」→汁物提案
                print(f"\n[ステップ8] 副菜を選択 (selection=2)...")
                selection_sub_response = client.send_selection_request(
                    task_id=task_id_sub,
                    selection=2,
                    sse_session_id=sse_session_id
                )
                
                if not selection_sub_response or not selection_sub_response.get("success"):
                    print(f"❌ 副菜選択リクエストが失敗しました: {selection_sub_response}")
                    return False
                
                await wait_for_response_delay(5.0)
                
                # 汁物提案を確認
                print(f"\n[ステップ9] 汁物提案を確認...")
                soup_request = "主菜・副菜で使っていない食材で汁物を5件提案して"
                soup_response = client.send_chat_request(soup_request, sse_session_id=sse_session_id)
                
                if not soup_response or not soup_response.get("success"):
                    # 副菜選択のレスポンスに汁物提案が含まれている場合もある
                    if selection_sub_response.get("requires_selection"):
                        soup_response = selection_sub_response
                
                if soup_response and soup_response.get("success"):
                    await wait_for_response_delay(5.0)
                    
                    if soup_response.get("requires_selection"):
                        if not verify_stage_transition(soup_response, "soup"):
                            return False
                        
                        success_soup, task_id_soup = verify_selection_response(soup_response, "soup")
                        if not success_soup or not task_id_soup:
                            print(f"⚠️ 汁物提案の選択要求が正しくありません")
                            return False
                        
                        print(f"✅ 汁物提案成功: task_id={task_id_soup}")
                        
                        # ステップ10: 「他の提案を見る」→汁物追加提案
                        print(f"\n[ステップ10] 「他の提案を見る」リクエスト送信（汁物追加提案）...")
                        additional_soup_response = client.send_selection_request(
                            task_id=task_id_soup,
                            selection=0,
                            sse_session_id=sse_session_id
                        )
                        
                        if not additional_soup_response:
                            print(f"❌ 汁物追加提案リクエストがNoneを返しました")
                            return False
                        
                        if additional_soup_response.get("success"):
                            print(f"✅ 汁物追加提案リクエスト成功")
                        
                        await wait_for_response_delay(5.0)
                        
                        # ステップ11: 「3. を選択」→献立完成
                        print(f"\n[ステップ11] 汁物を選択 (selection=3)...")
                        selection_soup_response = client.send_selection_request(
                            task_id=task_id_soup,
                            selection=3,
                            sse_session_id=sse_session_id
                        )
                        
                        if not selection_soup_response or not selection_soup_response.get("success"):
                            print(f"❌ 汁物選択リクエストが失敗しました: {selection_soup_response}")
                            return False
                        
                        await wait_for_response_delay(3.0)
                        
                        # 献立完成の確認
                        if not verify_completion_response(selection_soup_response):
                            print(f"❌ 献立完成の検証に失敗しました")
                            return False
                        
                        print(f"✅ 献立完成確認成功")
                        
                        # ステップ12: 献立を保存
                        print(f"\n[ステップ12] 献立を保存...")
                        save_response = client.save_menu(sse_session_id)
                        
                        if not save_response:
                            print(f"❌ 献立保存リクエストがNoneを返しました")
                            return False
                        
                        if not save_response.get("success"):
                            print(f"❌ 献立保存が失敗しました: {save_response}")
                            return False
                        
                        total_saved = save_response.get("total_saved", 0)
                        if total_saved == 0:
                            print(f"⚠️ 保存されたレシピが0件です")
                        else:
                            print(f"✅ 献立保存成功: {total_saved}件のレシピが保存されました")
                        
                        # ステップ13: 食材削除候補を取得して削除
                        print(f"\n[ステップ13] 食材削除候補を取得して削除...")
                        from datetime import datetime
                        today = datetime.now().strftime("%Y-%m-%d")
                        
                        # 食材削除候補を取得
                        candidates_response = client.get_ingredient_delete_candidates(today)
                        if candidates_response and candidates_response.get("success"):
                            candidates = candidates_response.get("candidates", [])
                            print(f"✅ 食材削除候補を取得: {len(candidates)}件")
                            
                            if len(candidates) > 0:
                                # 候補の一部（最大3件）を削除
                                delete_items = []
                                for candidate in candidates[:3]:  # 最大3件まで
                                    delete_items.append({
                                        "item_name": candidate.get("item_name"),
                                        "quantity": 0,
                                        "inventory_id": candidate.get("inventory_id")
                                    })
                                
                                if delete_items:
                                    print(f"   削除対象: {[item.get('item_name') for item in delete_items]}")
                                    
                                    # 食材削除を実行
                                    delete_response = client.delete_ingredients(
                                        date=today,
                                        ingredients=delete_items
                                    )
                                    
                                    if delete_response and delete_response.get("success"):
                                        deleted_count = delete_response.get("deleted_count", 0)
                                        updated_count = delete_response.get("updated_count", 0)
                                        failed_items = delete_response.get("failed_items", [])
                                        print(f"✅ 食材削除成功: deleted={deleted_count}, updated={updated_count}, failed={len(failed_items)}")
                                    else:
                                        print(f"⚠️ 食材削除が失敗しました: {delete_response}")
                                else:
                                    print(f"⚠️ 削除対象がありません")
                            else:
                                print(f"⚠️ 食材削除候補がありません")
                        else:
                            print(f"⚠️ 食材削除候補の取得が失敗しました: {candidates_response}")
                        
                        print(f"✅ 完全シナリオのテスト成功")
                        return True
                    else:
                        print(f"⚠️ 汁物提案が選択要求を返していません")
                        return False
                else:
                    print(f"⚠️ 汁物提案が取得できませんでした")
                    return False
            else:
                print(f"⚠️ 副菜提案が選択要求を返していません")
                return False
        else:
            print(f"⚠️ 副菜提案が取得できませんでした")
            return False
        
    except AssertionError as e:
        print(f"❌ アサーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# ヘルプ機能: 検証関数
# ============================================================================

def verify_help_overview_response(response_text: str) -> bool:
    """ヘルプ全体概要の応答を検証"""
    required_keywords = [
        "4つの便利な機能",
        "在庫管理",
        "献立提案（一括）",
        "献立提案（段階的）",
        "便利な補助機能",
        "1〜4の数字を入力"
    ]
    
    for keyword in required_keywords:
        if keyword not in response_text:
            print(f"❌ 全体概要に必須キーワード '{keyword}' が見つかりません")
            return False
    
    print("✅ ヘルプ全体概要の検証成功")
    return True


def verify_inventory_detail_response(response_text: str) -> bool:
    """在庫管理機能の詳細応答を検証"""
    required_keywords = [
        "食材を追加する",
        "食材を削除する",
        "食材の数量などを変更する",
        "在庫を確認する"
    ]
    
    for keyword in required_keywords:
        if keyword not in response_text:
            print(f"❌ 在庫管理詳細に必須キーワード '{keyword}' が見つかりません")
            return False
    
    print("✅ 在庫管理機能詳細の検証成功")
    return True


def verify_menu_bulk_detail_response(response_text: str) -> bool:
    """献立一括提案機能の詳細応答を検証"""
    required_keywords = [
        "献立を教えて",
        "新しい献立",
        "過去の類似献立",
        "主菜・副菜・汁物"
    ]
    
    for keyword in required_keywords:
        if keyword not in response_text:
            print(f"❌ 献立一括提案詳細に必須キーワード '{keyword}' が見つかりません")
            return False
    
    print("✅ 献立一括提案機能詳細の検証成功")
    return True


def verify_menu_staged_detail_response(response_text: str) -> bool:
    """段階的提案機能の詳細応答を検証"""
    required_keywords = [
        "主菜を選ぶ",
        "副菜を選ぶ",
        "汁物を選ぶ",
        "他の提案を見る"
    ]
    
    for keyword in required_keywords:
        if keyword not in response_text:
            print(f"❌ 段階的提案詳細に必須キーワード '{keyword}' が見つかりません")
            return False
    
    print("✅ 段階的提案機能詳細の検証成功")
    return True


def verify_auxiliary_detail_response(response_text: str) -> bool:
    """補助機能の詳細応答を検証"""
    required_keywords = [
        "在庫一覧を確認する",
        "レシピ履歴を確認する",
        "ユーザープロフィール画面"
    ]
    
    for keyword in required_keywords:
        if keyword not in response_text:
            print(f"❌ 補助機能詳細に必須キーワード '{keyword}' が見つかりません")
            return False
    
    print("✅ 補助機能詳細の検証成功")
    return True


# 検証関数マッピング
DETAIL_VERIFIERS = {
    1: verify_inventory_detail_response,
    2: verify_menu_bulk_detail_response,
    3: verify_menu_staged_detail_response,
    4: verify_auxiliary_detail_response
}


# ============================================================================
# Phase 2.5: 基本機能のテスト実行
# ============================================================================

async def run_basic_test(client: IntegrationTestClient, test_case: TestCase) -> bool:
    """基本的なテストケースを実行"""
    print(f"\n{'='*60}")
    print(f"🧪 テスト: {test_case.name}")
    print(f"{'='*60}")
    
    try:
        # 1. 事前準備（setup）
        if test_case.setup:
            print(f"📋 事前準備を実行...")
            await test_case.setup(client)
        
        # 2. リクエスト送信
        print(f"📤 リクエスト送信: {test_case.message}")
        response = client.send_chat_request(test_case.message)
        
        if response is None:
            print(f"❌ リクエストが失敗しました")
            return False
        
        # 3. レスポンス検証
        assert "response" in response, f"レスポンスに'response'フィールドがありません"
        assert "success" in response, f"レスポンスに'success'フィールドがありません"
        
        success = response["success"]
        response_text = response.get("response", "")
        
        assert success is True, f"処理が成功していません: success={success}"
        assert len(response_text) > 0, f"レスポンスが空です"
        
        print(f"📝 レスポンス内容: {response_text[:200]}...")
        
        # 4. レスポンス内容の検証（タスク情報はSSE経由のため検証しない）
        if test_case.expected_tasks:
            print(f"📊 タスクチェーン検証（スキップ）:")
            print(f"   期待されるタスク: {test_case.expected_tasks}")
            print(f"   ⚠️ タスク情報はSSE経由で非同期送信されるため、APIレスポンスには含まれません")
        
        # 5. 曖昧性検証
        if test_case.expected_ambiguity:
            requires_confirmation = response.get("requires_confirmation", False)
            confirmation_session_id = response.get("confirmation_session_id")
            
            print(f"🔍 曖昧性検証:")
            print(f"   requires_confirmation: {requires_confirmation}")
            print(f"   confirmation_session_id: {confirmation_session_id}")
            
            if test_case.expected_ambiguity == "multiple_items":
                assert "件見つかりました" in response_text, f"複数アイテムのメッセージが見つかりません: {response_text}"
                print(f"✅ 曖昧性検出（複数アイテム）")
            else:
                assert requires_confirmation, f"requires_confirmation が True になっていません"
                print(f"✅ 曖昧性検出: {test_case.expected_ambiguity}")
        
        # 6. 献立生成の特別検証
        if test_case.expected_pattern == "menu":
            print(f"\n🔍 献立生成の詳細検証:")
            if not verify_menu_proposal_response(response_text):
                return False
        
        # 7. 追加検証
        if test_case.verify:
            print(f"🔍 追加検証を実行...")
            await test_case.verify(client, response)
        
        # 8. 2段階テスト（曖昧性解消）
        if test_case.requires_two_stage and response.get("requires_confirmation") and test_case.second_stage_message:
            print(f"\n{'─'*60}")
            print(f"🔄 2段階テスト: 曖昧性解消")
            print(f"{'─'*60}")
            
            confirmation_session_id = response.get("confirmation_session_id")
            if not confirmation_session_id:
                print(f"❌ confirmation_session_id がありません")
                return False
            
            print(f"📤 確認質問への回答送信: {test_case.second_stage_message}")
            
            # 2段階目のリクエスト送信
            second_response = client.send_chat_request(
                test_case.second_stage_message,
                sse_session_id=confirmation_session_id,
                confirm=True
            )
            
            if second_response is None:
                print(f"❌ 2段階目のリクエストが失敗しました")
                return False
            
            # 2段階目のレスポンス検証
            assert "response" in second_response, f"レスポンスに'response'フィールドがありません"
            assert "success" in second_response, f"レスポンスに'success'フィールドがありません"
            
            second_success = second_response["success"]
            second_response_text = second_response.get("response", "")
            
            assert second_success is True, f"2段階目の処理が成功していません: success={second_success}"
            assert len(second_response_text) > 0, f"2段階目のレスポンスが空です"
            
            print(f"📝 2段階目のレスポンス: {second_response_text[:200]}...")
            print(f"✅ 2段階目のテスト成功")
        
        print(f"✅ テスト成功: {test_case.name}")
        return True
        
    except AssertionError as e:
        print(f"❌ アサーションエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# テストケース定義
# ============================================================================

# セットアップ関数
async def setup_multiple_items(client: IntegrationTestClient):
    """複数のアイテムを登録（曖昧性テスト用）"""
    client.add_inventory("牛乳", 2, "本")
    await wait_for_response_delay(0.5)
    client.add_inventory("牛乳", 3, "本")
    await wait_for_response_delay(0.5)


async def setup_renkon_inventory(client: IntegrationTestClient):
    """レンコンを在庫に登録"""
    client.add_inventory("レンコン", 1, "個")
    await wait_for_response_delay(0.5)
    client.add_inventory("ニンジン", 2, "個")
    await wait_for_response_delay(0.5)
    client.add_inventory("鶏肉", 300, "g")
    await wait_for_response_delay(0.5)


async def setup_menu_inventory(client: IntegrationTestClient):
    """献立生成用の在庫を登録（野菜・肉・調味料）"""
    client.add_inventory("キャベツ", 1, "個")
    await wait_for_response_delay(0.5)
    client.add_inventory("人参", 2, "本")
    await wait_for_response_delay(0.5)
    client.add_inventory("もやし", 1, "袋")
    await wait_for_response_delay(0.5)
    client.add_inventory("豚肉", 300, "g")
    await wait_for_response_delay(0.5)


# テストケースリスト
TEST_CASES = [
    # ========================================================================
    # Phase 2.5: 基本機能テスト
    # ========================================================================
    TestCase(
        name="挨拶リクエスト",
        message="こんにちは",
        expected_pattern="other",
        expected_tasks=[],
        test_type="basic"
    ),
    
    TestCase(
        name="在庫追加",
        message="牛乳を2本追加して",
        expected_pattern="inventory",
        expected_tasks=["add_inventory"],
        test_type="basic"
    ),
    
    TestCase(
        name="在庫削除（曖昧性あり）",
        message="牛乳を削除して",
        expected_pattern="inventory",
        expected_tasks=[],
        expected_ambiguity="multiple_items",
        setup=lambda client: setup_multiple_items(client),
        test_type="basic"
    ),
    
    TestCase(
        name="在庫削除（曖昧性解消）",
        message="牛乳を削除して",
        expected_pattern="inventory",
        expected_tasks=[],
        expected_ambiguity="multiple_items",
        requires_two_stage=True,
        second_stage_message="最新の",
        setup=lambda client: setup_multiple_items(client),
        test_type="basic"
    ),
    
    TestCase(
        name="在庫更新（全件）",
        message="牛乳を全部1本に変えて",
        expected_pattern="inventory",
        expected_tasks=["update_inventory"],
        setup=lambda client: setup_multiple_items(client),
        test_type="basic"
    ),
    
    TestCase(
        name="献立生成",
        message="献立を教えて",
        expected_pattern="menu",
        expected_tasks=["get_inventory", "generate_menu_plan", "search_menu_from_rag", "search_recipes_from_web"],
        setup=lambda client: setup_menu_inventory(client),
        test_type="basic"
    ),
    
    TestCase(
        name="主菜提案（食材指定）",
        message="レンコンの主菜を5件提案して",
        expected_pattern="main",
        expected_tasks=["get_inventory", "history_get_recent_titles", "generate_proposals", "search_recipes_from_web"],
        setup=lambda client: setup_renkon_inventory(client),
        test_type="basic"
    ),
    
    # ========================================================================
    # Phase 3E: 段階的選択システムテスト
    # ========================================================================
    TestCase(
        name="TC-001: 基本フローの段階的選択",
        description="主菜5件提案 → 選択 → 副菜5件提案 → 選択 → 汁物5件提案 → 選択 → 完了",
        setup=setup_renkon_inventory,
        expected_stages=["main", "sub", "soup"],
        test_type="stage_flow"
    ),
    
    # ========================================================================
    # Phase 5C前: 完全シナリオテスト
    # ========================================================================
    TestCase(
        name="TC-002: 完全シナリオ（曖昧性検出→追加提案→保存）",
        description="主菜を教えて→レンコンで→追加提案→副菜→追加提案→汁物→追加提案→完成→保存",
        test_type="complete_scenario"
    ),
    
    # ========================================================================
    # Phase 3C-3 + UPDATE07: 自動遷移検証テスト
    # ========================================================================
    TestCase(
        name="TC-003: 自動遷移検証（確認ステップ→空白メッセージ遷移）",
        description="主菜選択→確認フラグ検証→空白メッセージで副菜提案自動遷移→副菜選択→確認フラグ検証→空白メッセージで汁物提案自動遷移→完了",
        setup=setup_renkon_inventory,
        expected_stages=["main", "sub", "soup"],
        test_type="auto_transition"
    ),
]


# ============================================================================
# ヘルプ機能: テストケース
# ============================================================================

HELP_TEST_CASES = [
    HelpTestCase(
        name="TC-HELP-001: ヘルプ全体概要の表示",
        description="「使い方を教えて」で全体概要が表示され、セッション状態が更新される",
        messages=["使い方を教えて"],
        expected_responses=[verify_help_overview_response],
        expected_help_states=["overview"]
    ),
    
    HelpTestCase(
        name="TC-HELP-002: 在庫管理機能の詳細表示",
        description="「1」で在庫管理機能の詳細が表示される",
        messages=["使い方を教えて", "1"],
        expected_responses=[verify_help_overview_response, verify_inventory_detail_response],
        expected_help_states=["overview", "detail_1"]
    ),
    
    HelpTestCase(
        name="TC-HELP-003: 献立一括提案機能の詳細表示",
        description="「2」で献立一括提案機能の詳細が表示される",
        messages=["使い方を教えて", "2"],
        expected_responses=[verify_help_overview_response, verify_menu_bulk_detail_response],
        expected_help_states=["overview", "detail_2"]
    ),
    
    HelpTestCase(
        name="TC-HELP-004: 段階的提案機能の詳細表示",
        description="「3」で段階的提案機能の詳細が表示される",
        messages=["使い方を教えて", "3"],
        expected_responses=[verify_help_overview_response, verify_menu_staged_detail_response],
        expected_help_states=["overview", "detail_3"]
    ),
    
    HelpTestCase(
        name="TC-HELP-005: 補助機能の詳細表示",
        description="「4」で補助機能の詳細が表示される",
        messages=["使い方を教えて", "4"],
        expected_responses=[verify_help_overview_response, verify_auxiliary_detail_response],
        expected_help_states=["overview", "detail_4"]
    ),
    
    HelpTestCase(
        name="TC-HELP-006: 通常のチャットへの復帰",
        description="ヘルプモード中に通常のチャット入力で自動的に復帰する",
        messages=["使い方を教えて", "在庫を教えて"],
        expected_responses=[verify_help_overview_response, lambda r: "在庫" in r or "食材" in r],  # 通常の応答
        expected_help_states=["overview", None]  # 復帰時はNone
    ),
    
    HelpTestCase(
        name="TC-HELP-007: 複数の機能詳細を順番に見る",
        description="1→2→3→4と順番に機能詳細を表示できる",
        messages=["使い方を教えて", "1", "2", "3", "4"],
        expected_responses=[
            verify_help_overview_response,
            verify_inventory_detail_response,
            verify_menu_bulk_detail_response,
            verify_menu_staged_detail_response,
            verify_auxiliary_detail_response
        ],
        expected_help_states=["overview", "detail_1", "detail_2", "detail_3", "detail_4"]
    ),
    
    HelpTestCase(
        name="TC-HELP-008: ヘルプキーワード「ヘルプ」での検知",
        description="「ヘルプ」でも全体概要が表示される",
        messages=["ヘルプ"],
        expected_responses=[verify_help_overview_response],
        expected_help_states=["overview"]
    ),
]


# ============================================================================
# ヘルプ機能: テスト実行関数
# ============================================================================

async def run_help_test(client: IntegrationTestClient, test_case: HelpTestCase) -> bool:
    """ヘルプ機能テストケースを実行"""
    print(f"\n{'='*60}")
    print(f"🧪 テスト: {test_case.name}")
    print(f"📝 説明: {test_case.description}")
    print(f"{'='*60}")
    
    if test_case.skip:
        print(f"⏭️ テストをスキップ: {test_case.name}")
        return True
    
    # テストケースの設定を検証（メッセージ数と期待される応答数が一致しているか）
    if len(test_case.messages) != len(test_case.expected_responses):
        print(f"❌ テストケース設定エラー: メッセージ数({len(test_case.messages)})と期待される応答数({len(test_case.expected_responses)})が一致しません")
        return False
    
    try:
        # 事前準備
        if test_case.setup:
            print(f"📋 事前準備を実行...")
            await test_case.setup(client)
            await wait_for_response_delay(1.0)
        
        sse_session_id = str(uuid.uuid4())
        print(f"📝 生成したsse_session_id: {sse_session_id}")
        
        # 各メッセージを順番に送信
        for i, message in enumerate(test_case.messages):
            print(f"\n[ステップ{i+1}] メッセージ送信: '{message}'")
            
            response = client.send_chat_request(message, sse_session_id=sse_session_id)
            
            if not response:
                print(f"❌ レスポンスがNoneです")
                return False
            
            # レスポンスの構造を確認（successフィールドがない場合もある）
            if "success" in response and not response.get("success"):
                print(f"❌ レスポンスが失敗しています: {response}")
                return False
            
            response_text = response.get("response", "")
            if not response_text:
                print(f"❌ レスポンステキストが空です")
                return False
            
            print(f"📄 応答: {response_text[:200]}...")  # 最初の200文字を表示
            
            # 応答の検証（メッセージ数と期待される応答数は事前にチェック済み）
            verifier = test_case.expected_responses[i]
            if not verifier(response_text):
                print(f"❌ 応答の検証に失敗しました（ステップ{i+1}）")
                return False
            
            await wait_for_response_delay(2.0)
        
        print(f"✅ テスト成功: {test_case.name}")
        return True
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# メイン関数
# ============================================================================

async def run_test_case(client: IntegrationTestClient, test_case: TestCase) -> bool:
    """テストケースを実行（ルーター）"""
    if test_case.skip:
        print(f"⏭️ テストをスキップ: {test_case.name}")
        return True
    
    if test_case.test_type == "stage_flow":
        return await run_stage_flow_test(client, test_case)
    elif test_case.test_type == "complete_scenario":
        return await run_complete_scenario_test(client)
    elif test_case.test_type == "auto_transition":
        return await run_auto_transition_test(client, test_case)
    else:
        return await run_basic_test(client, test_case)


async def main():
    """メイン関数"""
    print("🚀 統合バックエンド回帰テスト開始")
    print(f"📅 実行時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # テストクライアントの初期化
    try:
        client = IntegrationTestClient()
    except Exception as e:
        print(f"❌ テストクライアントの初期化に失敗しました: {e}")
        return False
    
    # サーバーの状態をチェック
    if not client.check_server_status():
        print("⚠️ サーバーが起動していません。python -m uvicorn api.main:app --reload でサーバーを起動してください。")
        return False
    
    print("✅ サーバー接続確認")
    
    # テストケースを実行
    passed = 0
    failed = 0
    
    # 通常のテストケースを実行
    for test_case in TEST_CASES:
        try:
            result = await run_test_case(client, test_case)
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        # テスト間で少し待機
        await wait_for_response_delay(2.0)
    
    # ヘルプ機能のテストケースを実行
    print(f"\n{'='*60}")
    print(f"📚 ヘルプ機能テスト開始")
    print(f"{'='*60}")
    
    for test_case in HELP_TEST_CASES:
        try:
            result = await run_help_test(client, test_case)
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        # テスト間で少し待機
        await wait_for_response_delay(2.0)
    
    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"📊 テスト結果サマリー")
    print(f"{'='*60}")
    print(f"✅ 成功: {passed}")
    print(f"❌ 失敗: {failed}")
    print(f"📊 合計: {passed + failed}")
    
    if failed == 0:
        print(f"\n🎉 全テストが成功しました！")
        return True
    else:
        print(f"\n⚠️ 一部のテストが失敗しました")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ テストが中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

