# @cosme 化粧品ランキングデータ

このリポジトリには、@cosme のランキングページから取得した化粧品ランキングデータを保存しています。

対象カテゴリ:

- ファンデーション `item/916`
- 化粧下地 `item/1008`
- コンシーラー `item/1013`
- フェイスパウダー `item/918`
- フィックスミスト `item/964`

現在は、上記 5 カテゴリのランキング 1〜50 位の商品情報と商品画像を収録しています。

## 取得済みデータ

今回取得したデータは以下に保存されています。

```text
data/cosme_foundation_ranking_20260616/
data/cosme_makeup_base_ranking_20260616/
data/cosme_concealer_ranking_20260616/
data/cosme_face_powder_ranking_20260616/
data/cosme_fix_mist_ranking_20260616/
```

ファイル構成:

```text
cosme_foundation_ranking.csv    CSV データ。UTF-8 with BOM のため表計算ソフトで開きやすい形式
cosme_foundation_ranking.json   JSON データ。プログラムでの再利用向け
images/                         商品画像。1 商品につき 1 枚
```

各カテゴリには、50 件の商品情報と 50 枚の商品画像が含まれています。

## 取得項目

出力ファイルには以下の項目が含まれます。

| 項目 | 内容 |
| --- | --- |
| `rank` | ランキング順位 |
| `product_id` | @cosme の商品 ID |
| `brand` | ブランド名 |
| `product_name` | 商品名 |
| `categories` | 商品カテゴリ |
| `rating` | 評価点 |
| `review_count` | クチコミ件数 |
| `attention_count` | 注目人数 |
| `capacity_price` | 容量・税込価格 |
| `release_date` | 発売日 |
| `product_url` | @cosme 商品詳細ページ |
| `shopping_url` | ショッピングページ URL。ページ上にある場合のみ |
| `image_url` | 商品画像の元 URL |
| `image_file` | ダウンロード済み画像のローカルパス |

## データ内容

ランキングページから取得した主な情報:

- ブランド名
- 商品名
- カテゴリ
- 評価点
- クチコミ件数
- 容量・税込価格
- 発売日
- 商品画像

商品詳細ページから補完した主な情報:

- 注目人数
- より高解像度の商品画像 URL
- 詳細ページ上の容量・税込価格、発売日、評価点など

## ディレクトリ構成

```text
  cosme/
  README.md
  cosme_ranking_scraper.py
  data/
    cosme_foundation_ranking_20260616/
      cosme_foundation_ranking.csv
      cosme_foundation_ranking.json
      images/
        001_10290890.jpg
        002_10268836.jpg
        ...
    cosme_makeup_base_ranking_20260616/
      cosme_makeup_base_ranking.csv
      cosme_makeup_base_ranking.json
      images/
        ...
    cosme_concealer_ranking_20260616/
      cosme_concealer_ranking.csv
      cosme_concealer_ranking.json
      images/
        ...
    cosme_face_powder_ranking_20260616/
      cosme_face_powder_ranking.csv
      cosme_face_powder_ranking.json
      images/
        ...
    cosme_fix_mist_ranking_20260616/
      cosme_fix_mist_ranking.csv
      cosme_fix_mist_ranking.json
      images/
        ...
```

## 注意事項

- 個人の調査、データ整理、学習用途での利用を想定しています。
- 利用時は対象サイトの利用規約や robots ルールを確認してください。
- 商品によってはショッピングリンクが存在しないため、`shopping_url` が空になる場合があります。
- 商品画像の権利は元サイトまたはブランド側に帰属します。利用範囲に注意してください。
