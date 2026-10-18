# 投資業者チェック(金融庁 無登録業者リストの自動サイト)

毎朝9:15に自動で:
1. 金融庁の「無登録で金融商品取引業を行う者」リストを取り込む
2. 業者ごとのページ・検索付き一覧・sitemapを生成して公開する
3. 新しく掲載された業者をXに投稿する(1回最大5件)

費用:独自ドメイン代だけ(GitHubは無料枠で動きます)。

---

## セットアップ手順(30分くらい)

### 1. GitHubに置く
1. GitHubで新しいリポジトリを作る(Public。Privateだと無料プランではPagesが使えません)
2. このフォルダの中身を全部アップロードする

### 2. 公開の設定(GitHub Pages)
1. リポジトリの **Settings → Pages**
2. 「Source」を **GitHub Actions** にする

### 3. 初回実行
1. **Actions** タブ → 「daily-update」→ **Run workflow**
2. 数分で完了。Settings → Pages に表示されるURLでサイトが見られます
3. 初回は「全件取り込み」だけで、Xには投稿しません(1000件近く連投しないための安全装置)

### 4. 独自ドメインをつなぐ
1. お名前.com などでドメインを取得
2. Settings → Pages → **Custom domain** にドメインを入力し、表示される指示どおりDNSを設定
3. `config.json` の `base_url` を `https://取得したドメイン` に書き換える(ページのURL・sitemap・X投稿のリンクに使われます)

### 5. Googleに登録
1. [Google Search Console](https://search.google.com/search-console) にドメインを登録
2. 「サイトマップ」に `sitemap.xml` を送信

### 6. X自動投稿(任意)
1. [X Developer Portal](https://developer.x.com/) でアプリを作り、**Read and Write** 権限にしてキーを発行
2. リポジトリの **Settings → Secrets and variables → Actions** に4つ登録
   - `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_SECRET`
3. 未登録の間は「投稿内容を表示するだけ」で動きます
4. ※XのAPIは料金・無料枠が頻繁に変わるので、登録時に最新条件を確認してください

---

## 手元で試す
```
pip install -r requirements.txt
cd scripts
python fetch_fsa.py --file ../tests/day1.html --today 2026-10-18   # 初回
python fetch_fsa.py --file ../tests/day2.html --today 2026-10-19   # 1件追加
python build_site.py      # site/ にページが出来る
python post_x.py          # 投稿内容の確認(ドライラン)
```
※テスト後は `data/` の中身を消してからGitHubに上げてください。

## 安全装置
- 取り込み件数が前回の半分未満なら、更新を中止(金融庁ページの構成変更で壊れたデータを公開しないため)。Actionsが失敗し、GitHubからメールが届きます
- リストから消えた業者も「過去に掲載」としてページを残します
- 「◯◯を詐称」の業者は、実在の会社と無関係である旨をページ上部に表示します
- 全ページに「詐欺と断定するものではない」「金融庁・警察とは無関係」と明記しています

## ファイル
| ファイル | 役割 |
|---|---|
| `config.json` | サイト名・URL・投稿件数の上限 |
| `scripts/fetch_fsa.py` | 金融庁リストの取り込み・新規検知 |
| `scripts/build_site.py` | ページ生成 |
| `scripts/post_x.py` | X投稿 |
| `templates/style.css` | 見た目 |
| `.github/workflows/daily.yml` | 毎日の自動実行 |
