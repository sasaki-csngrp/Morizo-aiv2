#!/usr/bin/env python3
"""
旧ベクトルDBと新ベクトルDBの件数を比較するスクリプト
"""

import os
import sys
from pathlib import Path

# 環境変数の読み込み（dotenvなしで直接確認）
script_dir = Path(__file__).parent
project_root = script_dir.parent

# SQLiteを使用してChromaDBの件数を取得
try:
    import sqlite3
    sqlite_available = True
except ImportError:
    sqlite_available = False
    print("警告: sqlite3モジュールが利用できません。")

# ベクトルDBのパス定義
old_dbs = {
    'main': project_root / 'recipe_vector_db_main',
    'sub': project_root / 'recipe_vector_db_sub',
    'soup': project_root / 'recipe_vector_db_soup'
}

new_dbs = {
    'main': project_root / 'recipe_vector_db_main_2',
    'sub': project_root / 'recipe_vector_db_sub_2',
    'soup': project_root / 'recipe_vector_db_soup_2',
    'other': project_root / 'recipe_vector_db_other_2'
}

def get_vector_db_count(db_path: Path) -> int:
    """ベクトルDBの件数を取得（SQLiteを直接使用）"""
    if not db_path.exists():
        return None
    
    if not sqlite_available:
        # SQLiteが利用できない場合は、ディレクトリの存在のみ確認
        return -1  # 存在するが件数不明
    
    try:
        # ChromaDBは通常、chroma.sqlite3ファイルを持つ
        sqlite_file = db_path / "chroma.sqlite3"
        if sqlite_file.exists():
            # SQLiteファイルが存在する場合は、データベースを直接読み込む
            conn = sqlite3.connect(str(sqlite_file))
            cursor = conn.cursor()
            
            # テーブル名を確認
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # embeddingsテーブルが存在する場合は、その件数を取得
            if 'embeddings' in tables:
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                count = cursor.fetchone()[0]
            else:
                # 他のテーブル名を試す（ChromaDBのバージョンによって異なる可能性）
                # collection_metadataテーブルから情報を取得
                if 'collection_metadata' in tables:
                    # コレクションのメタデータから件数を推測
                    cursor.execute("SELECT COUNT(*) FROM collection_metadata")
                    count = cursor.fetchone()[0]
                else:
                    # 最初に見つかったテーブルの件数を取得
                    if tables:
                        table_name = tables[0]
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                    else:
                        count = 0
            
            conn.close()
            return count
        else:
            # SQLiteファイルが存在しない場合は、ディレクトリのみ存在
            return -1
    except Exception as e:
        print(f"  警告: {db_path.name} の読み込みに失敗: {e}")
        return -1  # 存在するが件数不明

print("=" * 60)
print("ベクトルDB件数比較")
print("=" * 60)

# 旧ベクトルDBの件数
print("\n【旧ベクトルDB】")
old_total = 0
old_counted = 0
for category, db_path in old_dbs.items():
    count = get_vector_db_count(db_path)
    if count is not None:
        if count == -1:
            print(f"  {category:10s}: 存在しますが件数不明 ({db_path.name})")
        else:
            print(f"  {category:10s}: {count:5d}件 ({db_path.name})")
            old_total += count
            old_counted += 1
    else:
        print(f"  {category:10s}: 存在しません ({db_path.name})")
if old_counted > 0:
    print(f"  合計      : {old_total:5d}件")

# 新ベクトルDBの件数
print("\n【新ベクトルDB】")
new_total = 0
new_counted = 0
for category, db_path in new_dbs.items():
    count = get_vector_db_count(db_path)
    if count is not None:
        if count == -1:
            print(f"  {category:10s}: 存在しますが件数不明 ({db_path.name})")
        else:
            print(f"  {category:10s}: {count:5d}件 ({db_path.name})")
            new_total += count
            new_counted += 1
    else:
        print(f"  {category:10s}: 存在しません ({db_path.name})")
if new_counted > 0:
    print(f"  合計      : {new_total:5d}件")

# 比較
print("\n【比較】")
if old_total > 0 and new_total > 0:
    diff = new_total - old_total
    print(f"  差額      : {diff:+5d}件")
    if old_total > 0:
        ratio = (new_total / old_total) * 100
        print(f"  比率      : {ratio:.1f}%")
elif old_total == 0:
    print("  旧ベクトルDBが存在しません")
elif new_total == 0:
    print("  新ベクトルDBが存在しません（まだ構築されていない可能性があります）")

print("=" * 60)

