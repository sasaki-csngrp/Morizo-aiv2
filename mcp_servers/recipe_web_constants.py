"""
Morizo AI v2 - Recipe Web Search Constants

共通定数の定義
"""

# 対応サイトの定義
RECIPE_SITES = {
    'cookpad.com': 'Cookpad',
    'kurashiru.com': 'クラシル',
    'recipe.rakuten.co.jp': '楽天レシピ',
    'delishkitchen.tv': 'デリッシュキッチン'
}

# モック用レシピデータ（課金回避用）
MOCK_RECIPES = [
    {
        'title': '簡単！基本のハンバーグ',
        'url': 'https://cookpad.com/jp/recipes/17546743',
        'description': 'ふわふわでジューシーなハンバーグの作り方。基本のレシピなので初心者でも安心して作れます。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '絶品！オムライス',
        'url': 'https://cookpad.com/jp/recipes/19174499',
        'description': 'ふわふわの卵で包んだオムライス。ケチャップライスと卵の相性が抜群です。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '本格！カレーライス',
        'url': 'https://cookpad.com/jp/recipes/19240768',
        'description': 'スパイスから作る本格カレー。時間をかけて作ることで深い味わいが楽しめます。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '簡単！チキンソテー',
        'url': 'https://cookpad.com/jp/recipes/17426721',
        'description': 'ジューシーで柔らかいチキンソテーの作り方。下味がポイントです。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '絶品！パスタ',
        'url': 'https://cookpad.com/jp/recipes/18584308',
        'description': '本格的なパスタの作り方。アルデンテの麺とソースのバランスが重要です。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '簡単！サラダ',
        'url': 'https://cookpad.com/jp/recipes/17616085',
        'description': '新鮮な野菜を使ったサラダ。ドレッシングの作り方も紹介しています。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '絶品！スープ',
        'url': 'https://cookpad.com/jp/recipes/17563615',
        'description': '体が温まる美味しいスープ。野菜のうま味がたっぷりです。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '簡単！炒飯',
        'url': 'https://cookpad.com/jp/recipes/17832934',
        'description': 'パラパラで美味しい炒飯の作り方。コツを掴めば簡単に作れます。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '絶品！天ぷら',
        'url': 'https://cookpad.com/jp/recipes/17564487',
        'description': 'サクサクで美味しい天ぷらの作り方。衣の作り方がポイントです。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    },
    {
        'title': '簡単！煮物',
        'url': 'https://cookpad.com/jp/recipes/18558350',
        'description': 'ほっこり美味しい煮物。野菜の甘みが引き出されます。',
        'site': 'cookpad.com',
        'source': 'Cookpad'
    }
]

