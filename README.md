# Morizo AI v2 - Python AIエージェント 再構築

Smart Pantry MVPのAIエージェント

## **重要** **コーデイング支援AIの行動指針**

### **コーデイング支援AIの問題の本質**

### **1. コンテキストウインドウの問題**
- 設計文書を全て読み直す → コンテキストウインドウがパンク
- パンクすると → 重要な情報を忘れる
- 忘れると → 設計思想を無視した提案をする

### **2. 破壊的な行動パターン**
- 「修正」と称して既存の実装を破壊
- 設計思想を無視した「改善」提案
- 段階的実装の意図を理解せずに変更

### **3. 行動指針**
修正作業前：
1. 現在のファイルの内容のみを確認
2. 設計文書は参照のみ（読み直さない）
3. 既存の実装は変更しない
4. 承認なしに実装しない
そして、**破壊的行動を絶対に行わない**

## プロジェクト構成

- **Morizo-ai** - Python AIエージェント（開発を断念した前プロジェクト）
- **Morizo-aiv2** - Python AIエージェント（このリポジトリ）
- **Morizo-web** - Next.js Webアプリ（別リポジトリ）
- **Morizo-mobile** - Expo モバイルアプリ（別リポジトリ）

## クイックスタート

### 1. 環境準備
```bash
cd /app/Morizo-aiv2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 環境変数設定
```bash
# .envファイルに必要な設定を記入
```

### 3. サーバー起動
```bash
python main.py
# または
uvicorn main:app --reload --port 8000
```

### 4. 動作確認
```bash
curl http://localhost:8000/health
```

## テスト  
tests/03_1_test_logging.py 等
フェーズ番号_連番_test_テスト項目.py で命名

## 🔐 認証

### 認証方式
- **方式**: `Authorization: Bearer <supabase-token>`
- **トークン取得**: Supabase認証システム
- **検証**: Supabaseの`getUser(token)`でトークン有効性確認

## 技術スタック

- **フレームワーク**: FastAPI 0.117.1
- **言語**: Python 3.11+
- **AI/ML**: OpenAI API 1.108.1 (GPT-4, Whisper)
- **データベース**: Supabase PostgreSQL 2.19.0
- **認証**: Supabase Auth
- **FastMCP**: Micro-Agent Communication Protocol 2.12.3
- **HTTP**: httpx 0.28.1
- **Web検索**: Google Search API
- **ベクトルDB**: ChromaDB 1.1.0
- **自然言語処理**: spaCy 3.8.7, NLTK 3.9.1
- **データ処理**: pandas 2.3.2, numpy 2.3.3

## ライセンス

このプロジェクトは**プロプライエタリライセンス**の下で提供されています。

- **商用利用**: 別途ライセンス契約が必要
- **改変・再配布**: 禁止
- **個人利用**: 許可（非商用のみ）
- **教育・研究目的**: 許可（適切な帰属表示が必要）

詳細は[LICENSE](LICENSE)ファイルをご確認ください。

