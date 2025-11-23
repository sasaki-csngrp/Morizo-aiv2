#!/usr/bin/env python3
"""
古いレシピ履歴を自動削除するスクリプト

削除条件:
- cooked_at から 30日以上経過
- rating が null
- notes が null

全ユーザーのデータを対象とするため、サービスロールキーが必要です。
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

# プロジェクトルートのパスを取得
script_dir = Path(__file__).parent
project_root = script_dir.parent

# 環境変数の読み込み
load_dotenv(dotenv_path=project_root / ".env")


def get_service_role_client() -> Client:
    """
    サービスロールキーを使用してSupabaseクライアントを取得
    
    Returns:
        Supabaseクライアント（サービスロール権限）
        
    Raises:
        ValueError: 必要な環境変数が設定されていない場合
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        raise ValueError("SUPABASE_URL 環境変数が設定されていません")
    
    if not supabase_service_role_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY 環境変数が設定されていません")
    
    client = create_client(supabase_url, supabase_service_role_key)
    return client


def count_target_records(client: Client, days: int = 30) -> int:
    """
    削除対象のレコード数を取得
    
    Args:
        client: Supabaseクライアント
        days: 経過日数（デフォルト: 30日）
    
    Returns:
        削除対象のレコード数
    """
    # 30日前の日時を計算
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    try:
        # 削除対象をカウント
        result = client.table("recipe_historys")\
            .select("id", count="exact")\
            .lt("cooked_at", cutoff_date.isoformat())\
            .is_("rating", "null")\
            .is_("notes", "null")\
            .execute()
        
        return result.count if result.count is not None else 0
    except Exception as e:
        print(f"❌ エラー: レコード数の取得に失敗しました: {e}")
        return -1


def delete_old_records(client: Client, days: int = 30, batch_size: int = 100) -> int:
    """
    古いレシピ履歴を削除
    
    Args:
        client: Supabaseクライアント
        days: 経過日数（デフォルト: 30日）
        batch_size: バッチ処理サイズ（デフォルト: 100件）
    
    Returns:
        削除されたレコード数
    """
    # 30日前の日時を計算
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    deleted_count = 0
    offset = 0
    
    print(f"🗑️  削除処理を開始します...")
    print(f"   削除条件: cooked_at < {cutoff_date.isoformat()}, rating IS NULL, notes IS NULL")
    
    try:
        while True:
            # 削除対象を取得（バッチ処理）
            result = client.table("recipe_historys")\
                .select("id")\
                .lt("cooked_at", cutoff_date.isoformat())\
                .is_("rating", "null")\
                .is_("notes", "null")\
                .range(offset, offset + batch_size - 1)\
                .execute()
            
            if not result.data or len(result.data) == 0:
                break
            
            # 取得したレコードを削除
            for record in result.data:
                record_id = record["id"]
                try:
                    client.table("recipe_historys").delete().eq("id", record_id).execute()
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  警告: レコード {record_id} の削除に失敗しました: {e}")
            
            offset += batch_size
            
            # 進捗表示
            if deleted_count % 100 == 0:
                print(f"   進捗: {deleted_count} 件削除済み...")
        
        return deleted_count
    
    except Exception as e:
        print(f"❌ エラー: 削除処理中にエラーが発生しました: {e}")
        return deleted_count


def main():
    """メイン処理"""
    print("=" * 60)
    print("古いレシピ履歴の自動削除スクリプト")
    print("=" * 60)
    print()
    
    # 環境変数の確認
    try:
        client = get_service_role_client()
        print("✅ Supabaseクライアントの初期化に成功しました")
    except ValueError as e:
        print(f"❌ エラー: {e}")
        print()
        print("環境変数の設定を確認してください:")
        print("  - SUPABASE_URL")
        print("  - SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラー: Supabaseクライアントの初期化に失敗しました: {e}")
        sys.exit(1)
    
    # 削除対象のレコード数を取得
    print()
    print("🔍 削除対象のレコード数を確認中...")
    target_count = count_target_records(client, days=30)
    
    if target_count < 0:
        print("❌ レコード数の取得に失敗しました")
        sys.exit(1)
    
    if target_count == 0:
        print("✅ 削除対象のレコードはありません")
        sys.exit(0)
    
    print(f"📊 削除対象: {target_count} 件")
    print()
    
    # 削除処理を実行
    deleted_count = delete_old_records(client, days=30)
    
    print()
    print("=" * 60)
    if deleted_count > 0:
        print(f"✅ 削除処理が完了しました: {deleted_count} 件削除")
    else:
        print("⚠️  削除されたレコードはありませんでした")
    print("=" * 60)


if __name__ == "__main__":
    main()

