# Morizo AI - データベース設計 (DDL)

## Smart Pantry MVP用テーブル設計

### 1. 基本テーブル構成

```sql
-- 在庫管理テーブル
CREATE TABLE inventory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL DEFAULT '個',
    storage_location VARCHAR(100), -- '冷蔵庫', '冷凍庫', '常温倉庫', '野菜室'
    expiry_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 料理履歴テーブル（過去に作ったレシピの保存）
CREATE TABLE recipe_historys (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    source VARCHAR(100), -- 'web', 'rag', 'manual'
    url TEXT, -- レシピのURL
    cooked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5), -- 評価
    notes TEXT, -- メモ
    ingredients JSONB, -- 利用食材リスト（食材削除機能用）
    ingredients_deleted BOOLEAN DEFAULT FALSE, -- 食材削除済みフラグ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ユーザー設定テーブル
CREATE TABLE user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- OCR商品名変換テーブル（レシートOCR読み取り精度向上用）
CREATE TABLE ocr_item_mappings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,  -- OCRで読み取られた元の名前（例: "もっちり仕込み"）
    normalized_name VARCHAR(255) NOT NULL, -- 正規化後の名前（例: "食パン"）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, original_name)  -- 同一ユーザー内で元の名前は一意
);

-- ユーザーサブスクリプションテーブル（収益化機能用）
CREATE TABLE user_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    plan_type VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (plan_type IN ('free', 'pro', 'ultimate')),
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (subscription_status IN ('active', 'expired', 'cancelled')),
    subscription_id VARCHAR(255), -- ストアのサブスクリプションID
    platform VARCHAR(10) CHECK (platform IN ('ios', 'android')), -- 'ios' or 'android'
    purchased_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 利用回数制限テーブル（収益化機能用）
CREATE TABLE usage_limits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    date DATE NOT NULL, -- 日本時間の日付（YYYY-MM-DD形式）
    menu_bulk_count INTEGER NOT NULL DEFAULT 0, -- 献立一括提案の利用回数
    menu_step_count INTEGER NOT NULL DEFAULT 0, -- 段階的提案の利用回数
    ocr_count INTEGER NOT NULL DEFAULT 0, -- OCR読み取りの利用回数
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date) -- 1ユーザー1日1レコード
);
```

### 3. インデックスと制約

```sql
-- インデックス作成
CREATE INDEX idx_inventory_user_id ON inventory(user_id);
CREATE INDEX idx_inventory_item_name ON inventory(item_name);
CREATE INDEX idx_inventory_storage_location ON inventory(storage_location);
CREATE INDEX idx_recipe_historys_user_id ON recipe_historys(user_id);
CREATE INDEX idx_recipe_historys_title ON recipe_historys(title);
CREATE INDEX idx_ocr_item_mappings_user_id ON ocr_item_mappings(user_id);
CREATE INDEX idx_ocr_item_mappings_original_name ON ocr_item_mappings(original_name);
CREATE INDEX idx_ocr_item_mappings_normalized_name ON ocr_item_mappings(normalized_name);
CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(subscription_status);
CREATE INDEX idx_usage_limits_user_id ON usage_limits(user_id);
CREATE INDEX idx_usage_limits_date ON usage_limits(date);
CREATE INDEX idx_usage_limits_user_date ON usage_limits(user_id, date);

-- 更新日時自動更新のトリガー
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_inventory_updated_at BEFORE UPDATE ON inventory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_recipe_historys_updated_at BEFORE UPDATE ON recipe_historys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ocr_item_mappings_updated_at BEFORE UPDATE ON ocr_item_mappings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_subscriptions_updated_at BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_usage_limits_updated_at BEFORE UPDATE ON usage_limits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 4. Row Level Security (RLS) 設定

```sql
-- RLS有効化
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipe_historys ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_item_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_limits ENABLE ROW LEVEL SECURITY;

-- ポリシー作成（ユーザーは自分のデータのみアクセス可能）
CREATE POLICY "Users can view own inventory" ON inventory
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own inventory" ON inventory
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own inventory" ON inventory
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own inventory" ON inventory
    FOR DELETE USING (auth.uid() = user_id);

-- recipe_historysテーブル用ポリシー
CREATE POLICY "Users can view own recipe_historys" ON recipe_historys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own recipe_historys" ON recipe_historys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own recipe_historys" ON recipe_historys
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own recipe_historys" ON recipe_historys
    FOR DELETE USING (auth.uid() = user_id);

-- user_settingsテーブル用ポリシー
CREATE POLICY "Users can view own settings" ON user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own settings" ON user_settings
    FOR DELETE USING (auth.uid() = user_id);

-- ocr_item_mappingsテーブル用ポリシー
CREATE POLICY "Users can view own ocr_item_mappings" ON ocr_item_mappings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own ocr_item_mappings" ON ocr_item_mappings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own ocr_item_mappings" ON ocr_item_mappings
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own ocr_item_mappings" ON ocr_item_mappings
    FOR DELETE USING (auth.uid() = user_id);

-- user_subscriptionsテーブル用ポリシー
CREATE POLICY "Users can view own subscription" ON user_subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own subscription" ON user_subscriptions
    FOR UPDATE USING (auth.uid() = user_id);

-- サービスロール用ポリシー（バックエンドから更新可能にする）
CREATE POLICY "Service role can manage subscriptions" ON user_subscriptions
    FOR ALL USING (auth.role() = 'service_role');

-- usage_limitsテーブル用ポリシー
CREATE POLICY "Users can view own usage" ON usage_limits
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own usage" ON usage_limits
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own usage" ON usage_limits
    FOR UPDATE USING (auth.uid() = user_id);

-- サービスロール用ポリシー
CREATE POLICY "Service role can manage usage" ON usage_limits
    FOR ALL USING (auth.role() = 'service_role');
```

## 実行手順

1. **Supabaseダッシュボード** → **SQL Editor**
2. **上記のSQLを順番に実行**
3. **テーブル作成確認**

## テーブル設計の特徴

### inventory テーブル
- **item_name**: 食材名（必須）
- **quantity**: 数量（小数点対応）
- **unit**: 単位（個、kg、L等）
- **storage_location**: 保管場所（冷蔵庫、冷凍庫、常温倉庫、野菜室等）
- **expiry_date**: 消費期限

### recipe_historys テーブル（料理履歴）
- **title**: レシピタイトル
- **source**: レシピの出典（web, rag, manual）
- **url**: レシピのURL（Web検索で見つけた場合）
- **cooked_at**: 実際に作った日時
- **rating**: 評価（1-5段階）
- **notes**: メモ・感想
- **ingredients**: 利用食材リスト（JSONB形式、食材削除機能用）
- **ingredients_deleted**: 食材削除済みフラグ（BOOLEAN）

### user_settings テーブル
- **preferences**: JSONB形式でユーザー設定
- **user_id**: ユニーク制約で1ユーザー1設定

### ocr_item_mappings テーブル（OCR商品名変換）
- **original_name**: OCRで読み取られた元の商品名（例: "もっちり仕込み"、"新ＢＰコクのある絹豆腐"）
- **normalized_name**: 正規化後の食材名（例: "食パン"、"豆腐"）
- **user_id**: ユーザーID（ユーザーごとに変換テーブルを管理）
- **UNIQUE(user_id, original_name)**: 同一ユーザー内で元の名前は一意（同じ元の名前に対して複数の変換を登録できない）

### user_subscriptions テーブル（収益化機能 - サブスクリプション管理）
- **user_id**: ユーザーID（UNIQUE制約で1ユーザー1プラン）
- **plan_type**: プランタイプ（'free', 'pro', 'ultimate'）
- **subscription_status**: サブスクリプション状態（'active', 'expired', 'cancelled'）
- **subscription_id**: ストアのサブスクリプションID（Google Play / App Store）
- **platform**: プラットフォーム（'ios', 'android'）
- **purchased_at**: 購入日時
- **expires_at**: 有効期限

### usage_limits テーブル（収益化機能 - 利用回数制限）
- **user_id**: ユーザーID
- **date**: 日本時間の日付（YYYY-MM-DD形式）
- **menu_bulk_count**: 献立一括提案の利用回数
- **menu_step_count**: 段階的提案の利用回数
- **ocr_count**: OCR読み取りの利用回数
- **UNIQUE(user_id, date)**: 1ユーザー1日1レコード

#### MVP段階での想定設定例
```json
{
  "taste_preferences": {
    "spicy_level": 3,
    "sweet_preference": 2,
    "garlic_love": true,
    "cuisine_preferences": ["中華料理", "和食", "イタリアン"]
  }
}
```

#### 将来の一般公開時の拡張案
- **アレルギー情報**: 小麦、乳製品、卵等
- **調理器具制限**: オーブンなし、電子レンジのみ等
- **食事制限**: ベジタリアン、ビーガン、ハラル等
- **調理時間制限**: 15分以内、1時間以内等
- **難易度制限**: 初心者向け、上級者向け等

## セキュリティ
- **RLS**: ユーザーは自分のデータのみアクセス可能
- **CASCADE DELETE**: ユーザー削除時に関連データも削除
- **UUID**: セキュアなID生成
