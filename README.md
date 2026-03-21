# kaldi-sale-notifier

KALDIのセール情報をスクレイピングして、指定した店舗のセール情報をLINEに通知するツール。

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. LINE Messaging API の準備

1. [LINE Developers](https://developers.line.biz/) でMessaging APIチャネルを作成
2. チャネルアクセストークン（長期）を発行
3. 通知先のIDを確認:
   - **個人宛**: チャネル基本設定の「あなたのユーザーID」（`U` で始まる文字列）
   - **グループ宛**: Bot をグループに招待し、Webhook イベントの `source.groupId`（`C` で始まる文字列）

### 3. 設定

`.env.example` をコピーして `.env` を作成:

```bash
cp .env.example .env
```

`.env` を編集:

```
LINE_TOKEN=your_channel_access_token
LINE_USER_ID=your_user_or_group_id
KEYWORDS=目黒,大井町,五反田
```

`KEYWORDS` にはカンマ区切りで、通知したい店舗名のキーワードを設定してください（部分一致）。

### 4. 実行

```bash
python scraper.py
```

一度通知済みのセール情報は `seen.db` に記録され、同じ内容が重複送信されることはありません。

## 定期実行

### cron / タスクスケジューラ

```bash
# 例: 毎日9時に実行
0 9 * * * cd /path/to/kaldi-sale-notifier && python scraper.py
```

### GitHub Actions

リポジトリを fork して、Settings > Secrets に `LINE_TOKEN`・`LINE_USER_ID`・`KEYWORDS` を設定すれば、`.github/workflows/kaldi.yml` で毎日自動実行されます。
