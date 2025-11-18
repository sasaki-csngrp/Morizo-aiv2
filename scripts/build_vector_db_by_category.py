#!/usr/bin/env python3
"""
レシピベクトルDB構築スクリプト（分類別版）

このスクリプトは、me2you/recipe_data.jsonlからレシピデータを読み込み、
主菜・副菜・汁物別に3つのChromaDBベクトルデータベースを構築します。

使用方法:
    python scripts/build_vector_db_by_category.py

前提条件:
    - me2you/recipe_data.jsonlが存在すること
    - OpenAI APIキーが設定されていること
    - 必要な依存関係がインストールされていること
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv

# LangChain関連のインポート
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 調味料キーワードリスト（検索対象外）
SEASONING_KEYWORDS = [
    # 基本調味料
    '醤油', 'しょうゆ', '砂糖', '塩', '胡椒', 'こしょう', '酒', 'みりん', '酢',
    # 油類
    '油', 'ごま油', 'サラダ油', 'バター', 'マーガリン', 'オリーブオイル',
    # 発酵調味料
    '味噌', 'みそ', 'だし', 'コンソメ', 'ブイヨン',
    # ソース類
    'ケチャップ', 'マヨネーズ', 'マスタード', 'ウスターソース', 'オイスターソース',
    # 香辛料
    'わさび', 'からし', 'しょうが', 'にんにく', 'ねぎ', 'みつば', 'しそ', '大葉',
    # その他
    '片栗粉', '小麦粉', 'パン粉', 'ベーキングパウダー', '重曹',
    # 追加の調味料
    '薄力粉', 'グラニュー糖', '中華スープのもと', '白ワイン', '赤ワイン',
    '一味唐辛子', '鶏がらスープの素', '鶏がらスープのもと', '鶏がらスープ',
    'ウェイパー', '合わせ調味料'
]

def load_recipe_data(file_path: str) -> List[Dict[str, Any]]:
    """
    レシピデータをJSONLファイルから読み込む
    
    Args:
        file_path: JSONLファイルのパス
        
    Returns:
        レシピデータのリスト
    """
    recipes = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    recipe = json.loads(line.strip())
                    recipes.append(recipe)
                except json.JSONDecodeError as e:
                    logger.warning(f"行 {line_num} のJSON解析に失敗: {e}")
                    continue
                    
        logger.info(f"レシピデータ読み込み完了: {len(recipes)}件")
        return recipes
        
    except FileNotFoundError:
        logger.error(f"ファイルが見つかりません: {file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ファイル読み込みエラー: {e}")
        sys.exit(1)

def extract_recipe_info(recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    レシピデータから必要な情報を抽出する（カテゴリ情報追加版）
    
    Args:
        recipe_data: 元のレシピデータ
        
    Returns:
        抽出されたレシピ情報
    """
    text = recipe_data.get('text', '')
    
    # タイトルの抽出
    title_start = text.find('(title)')
    title_end = text.find('(ingredientText)')
    title = ''
    if title_start != -1 and title_end != -1:
        title = text[title_start + 7:title_end].strip()
    
    # 食材リストの抽出
    ingredient_start = text.find('(ingredientText)')
    ingredient_end = text.find('[回答]')
    ingredients_text = ''
    if ingredient_start != -1 and ingredient_end != -1:
        ingredients_text = text[ingredient_start + 16:ingredient_end].strip()
    
    # 分類情報の抽出
    answer_start = text.find('[回答]')
    category = ''
    category_detail = ''
    main_ingredients = []
    if answer_start != -1:
        answer_text = text[answer_start + 4:].strip()
        try:
            # JSON部分を抽出
            json_start = answer_text.find('{')
            json_end = answer_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_text = answer_text[json_start:json_end]
                answer_data = json.loads(json_text)
                category = answer_data.get('レシピ分類', '')
                category_detail = answer_data.get('カテゴリ', '')  # 新規追加
                main_ingredients = answer_data.get('主材料', [])
        except json.JSONDecodeError:
            logger.warning(f"分類情報のJSON解析に失敗: {title}")
    
    return {
        'title': title,
        'ingredients_text': ingredients_text,
        'category': category,
        'category_detail': category_detail,  # 新規追加
        'main_ingredients': main_ingredients,
        'original_text': text
    }

def preprocess_recipes(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    レシピデータを前処理してベクトル化用のデータに変換する
    
    Args:
        recipes: 元のレシピデータのリスト
        
    Returns:
        前処理済みレシピデータのリスト
    """
    processed_recipes = []
    
    for i, recipe in enumerate(recipes):
        try:
            # レシピ情報を抽出
            recipe_info = extract_recipe_info(recipe)
            
            # 基本的な検証
            if not recipe_info['title'] or not recipe_info['category']:
                logger.warning(f"レシピ {i+1}: タイトルまたは分類が空です")
                continue
            
            # 食材リストを正規化
            ingredients = normalize_ingredients(recipe_info['ingredients_text'])
            
            # 結合テキストを作成（ベクトル化用）
            combined_text = create_combined_text(
                recipe_info['title'],
                ingredients,
                recipe_info['category']
            )
            
            # 前処理済みデータを作成
            processed_recipe = {
                'id': f"recipe_{i+1:04d}",
                'title': recipe_info['title'],
                'ingredients': ingredients,
                'combined_text': combined_text,
                'metadata': {
                    'title': recipe_info['title'],  # タイトルをメタデータに追加
                    'recipe_category': recipe_info['category'],
                    'category_detail': recipe_info['category_detail'],  # 新規追加
                    'main_ingredients': ', '.join(recipe_info['main_ingredients'][:3]),  # リストを文字列に変換
                    'original_index': i,  # 元のJSONLファイルでのインデックス
                    'category_index': len(processed_recipes)  # カテゴリ内でのインデックス
                }
            }
            
            # デバッグ出力（最初の10件のみ）
            if i < 10:
                print(f"=== レシピ {i+1} の処理 ===")
                print(f"タイトル: {recipe_info['title']}")
                print(f"レシピ分類: {recipe_info['category']}")
                print(f"カテゴリ: {recipe_info['category_detail']}")
                print(f"元のインデックス: {i}")
                print(f"カテゴリ内インデックス: {len(processed_recipes)}")
                print(f"元の食材テキスト: {recipe_info['ingredients_text'][:200]}...")
                print(f"正規化後食材: {ingredients}")
                print(f"結合テキスト: {combined_text}")
                print()
            
            processed_recipes.append(processed_recipe)
            
        except Exception as e:
            logger.error(f"レシピ {i+1} の前処理に失敗: {e}")
            continue
    
    logger.info(f"前処理完了: {len(processed_recipes)}件")
    return processed_recipes

def normalize_ingredients(ingredients_text: str) -> List[str]:
    """
    食材リストを正規化する
    
    Args:
        ingredients_text: 食材テキスト
        
    Returns:
        正規化された食材リスト
    """
    if not ingredients_text:
        return []
    
    # 基本的な正規化
    ingredients = []
    
    # スペースで分割（改行ではなく）
    parts = ingredients_text.split()
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # 食材名を抽出（分量情報を除去）
        # 例: "◎牛乳50ｃｃ（67ｃｃ）" → "牛乳"
        ingredient = extract_ingredient_name(part)
        if ingredient:
            ingredients.append(ingredient)
    
    # 重複を除去
    ingredients = list(set(ingredients))
    
    # 調味料を除外
    ingredients = filter_seasonings(ingredients)
    
    return ingredients

def extract_ingredient_name(ingredient_line: str) -> str:
    """
    食材行から食材名を抽出する（改善版）
    
    Args:
        ingredient_line: 食材行（例: "◎牛乳50ｃｃ（67ｃｃ）"）
        
    Returns:
        食材名（例: "牛乳"）
    """
    import re
    
    # より慎重なノイズ除去
    ingredient = ingredient_line
    
    # 1. 括弧内の内容を除去（分量情報）
    ingredient = re.sub(r'[（(][^）)]*[）)]', '', ingredient)
    
    # 2. 数字と単位を除去
    ingredient = re.sub(r'\d+[a-zA-Zａ-ｚＡ-Ｚ]*', '', ingredient)
    
    # 3. 記号を除去
    ingredient = re.sub(r'[◎★●※【】]', '', ingredient)
    
    # 4. よくあるノイズ語を除去
    noise_words = [
        '小さじ', '大さじ', '大匙', '小匙', '約', '適量', '適宜', '少々', '少量',
        'お好みにより', '好みで', 'なんでも', 'または', 'ＯＫ', '好きなだけ',
        'カット', 'カップ', '切れ', '切り', '位', '丁', '㏄', '㌘', 'グラム',
        '㎝', 'ｍｌ', 'センチ', 'チューブ', 'パック', '缶缶', 'でも', 'くらい',
        'たっぷり', 'あるもの', 'あれば', 'なくても', '何でも', '無くても可',
        'OK', '各', '又は', 'など', 'ほど', 'ふり', 'ひとつまみ', '握り',
        '人分', '人数分', '半分', '私は', 'タップリ', '×', '一', '○',
        # 追加の単位
        '本', '節', '袋', '個', '枚', '束', '滴', '片', 'かけ', 'カケ',
    # 追加の不要語
    '仕上げ', '黄金比率の煮汁', '大なら', '小なら', '大きめ'
    # 注: '個'は残す（「個」は食材名に含まれにくい）
    # 注: 'コ'と'大'は削除（食材名の一部として使われるため）
    ]
    
    for word in noise_words:
        ingredient = ingredient.replace(word, '')
    
    # 5. 余分な記号を除去（改善）
    ingredient = re.sub(r'[～/／・！？▲✿◆☆）））]', '', ingredient)
    
    # 6. 複数食材の結合を防止（新規追加）
    # 「・」で分割して最初の食材のみを取得
    if '・' in ingredient:
        ingredient = ingredient.split('・')[0]
    
    # 7. 文字化けの修正（新規追加）
    ingredient = re.sub(r'[ｸﾞﾗﾑ]', '', ingredient)
    
    ingredient = ingredient.strip()
    
    # 空文字列のみ除外
    if len(ingredient) == 0:
        return ''
    
    return ingredient

def filter_seasonings(ingredients: List[str]) -> List[str]:
    """
    調味料を除外して食材のみを抽出する
    
    Args:
        ingredients: 食材リスト
        
    Returns:
        調味料を除外した食材リスト
    """
    filtered = []
    for ingredient in ingredients:
        # 調味料かどうかをチェック
        is_seasoning = any(keyword in ingredient for keyword in SEASONING_KEYWORDS)
        if not is_seasoning:
            filtered.append(ingredient)
    
    logger.info(f"調味料除外: {len(ingredients)} → {len(filtered)} (除外: {len(ingredients) - len(filtered)})")
    return filtered

def create_combined_text(title: str, ingredients: List[str], category: str) -> str:
    """
    ベクトル化用の結合テキストを作成する（食材のみ）（改善版）
    
    Args:
        title: レシピタイトル（使用しない）
        ingredients: 食材リスト（調味料除外済み）
        category: レシピ分類（使用しない）
        
    Returns:
        食材のみの結合テキスト
    """
    # 食材リストの前処理（新規追加）
    cleaned_ingredients = []
    for ingredient in ingredients:
        # 不要な文字を除去
        cleaned = ingredient.strip()
        # 空文字列や不要な文字のみの場合は除外
        if cleaned and cleaned not in ['）', '））', '仕上げ', '黄金比率の煮汁']:
            cleaned_ingredients.append(cleaned)
    
    # 食材リストを文字列に変換（調味料は既に除外済み）
    ingredients_str = ' '.join(cleaned_ingredients)
    
    # 余分なスペースを除去
    ingredients_str = ' '.join(ingredients_str.split())
    
    return ingredients_str

def filter_recipes_by_category(processed_recipes: List[Dict[str, Any]], category_type: str) -> List[Dict[str, Any]]:
    """
    レシピを分類別にフィルタリングする
    
    Args:
        processed_recipes: 前処理済みレシピデータ
        category_type: 'main', 'sub', 'soup'
        
    Returns:
        フィルタリング済みレシピデータ
    """
    filtered_recipes = []
    
    for recipe in processed_recipes:
        metadata = recipe['metadata']
        recipe_category = metadata.get('recipe_category', '')
        category_detail = metadata.get('category_detail', '')
        
        if category_type == 'main' and recipe_category == '主菜':
            filtered_recipes.append(recipe)
        elif category_type == 'sub' and recipe_category == '副菜':
            filtered_recipes.append(recipe)
        elif category_type == 'soup' and '汁もの' in category_detail:
            filtered_recipes.append(recipe)
    
    return filtered_recipes

def build_vector_database(processed_recipes: List[Dict[str, Any]], output_dir: str):
    """
    ベクトルデータベースを構築する
    
    Args:
        processed_recipes: 前処理済みレシピデータ
        output_dir: 出力ディレクトリ
    """
    try:
        logger.info("ベクトルデータベース構築開始...")
        
        # OpenAI Embeddingsの初期化（環境変数からモデルを取得）
        embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # テキストとメタデータを準備
        texts = [recipe['combined_text'] for recipe in processed_recipes]
        metadatas = [recipe['metadata'] for recipe in processed_recipes]
        
        # ChromaDBベクトルストアを作成
        vectorstore = Chroma.from_texts(
            texts=texts,
            metadatas=metadatas,
            embedding=embeddings,
            persist_directory=output_dir
        )
        
        # 永続化
        vectorstore.persist()
        
        logger.info(f"ベクトルデータベース構築完了: {len(processed_recipes)}件")
        logger.info(f"出力先: {output_dir}")
        
        return vectorstore
        
    except Exception as e:
        logger.error(f"ベクトルデータベース構築エラー: {e}")
        raise

def main():
    """メイン処理"""
    # .envファイルの読み込み
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_path = project_root / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f".envファイルを読み込みました: {env_path}")
    else:
        logger.warning(f".envファイルが見つかりません: {env_path}")
    
    # OpenAI APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEYが設定されていません。.envファイルを確認してください。")
        sys.exit(1)
    
    # パスの設定
    recipe_data_path = project_root / "me2you" / "recipe_data.jsonl"
    
    logger.info("=== レシピベクトルDB構築開始（分類別版） ===")
    logger.info(f"元データ: {recipe_data_path}")
    
    # 1. レシピデータの読み込み
    logger.info("ステップ1: レシピデータの読み込み")
    recipes = load_recipe_data(str(recipe_data_path))
    
    # 2. 前処理
    logger.info("ステップ2: レシピデータの前処理")
    processed_recipes = preprocess_recipes(recipes)
    
    # 3. 分類別フィルタリング + ベクトルDB構築
    logger.info("ステップ3: 分類別ベクトルDB構築")
    categories = [
        ('main', 'recipe_vector_db_main', '主菜'),
        ('sub', 'recipe_vector_db_sub', '副菜'),
        ('soup', 'recipe_vector_db_soup', '汁物')
    ]
    
    for category_type, output_dir_name, category_name in categories:
        logger.info(f"=== {category_name}用ベクトルDB構築開始 ===")
        
        # 分類別フィルタリング
        filtered_recipes = filter_recipes_by_category(processed_recipes, category_type)
        logger.info(f"{category_name}用レシピ: {len(filtered_recipes)}件")
        
        if len(filtered_recipes) == 0:
            logger.warning(f"{category_name}用レシピが見つかりません。スキップします。")
            continue
        
        # ベクトルDB構築
        output_dir = project_root / output_dir_name
        vectorstore = build_vector_database(filtered_recipes, str(output_dir))
        
        # 簡単なテスト
        try:
            test_results = vectorstore.similarity_search("牛乳", k=3)
            logger.info(f"{category_name}用テスト検索結果: {len(test_results)}件")
            for i, result in enumerate(test_results):
                metadata = result.metadata
                title = metadata.get('title', 'Unknown')
                category = metadata.get('recipe_category', 'Unknown')
                logger.info(f"  {i+1}. {title} ({category})")
        except Exception as e:
            logger.warning(f"{category_name}用テスト検索に失敗: {e}")
        
        logger.info(f"=== {category_name}用ベクトルDB構築完了 ===")
    
    # 4. 完了報告
    logger.info("=== レシピベクトルDB構築完了（分類別版） ===")
    logger.info(f"処理件数: {len(processed_recipes)}件")
    logger.info("出力先:")
    for _, output_dir_name, category_name in categories:
        output_dir = project_root / output_dir_name
        logger.info(f"  {category_name}: {output_dir}")

if __name__ == "__main__":
    main()
