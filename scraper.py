# -*- coding: utf-8 -*-
"""
KALDI セール一覧をクロールして
  1. 店名にキーワードが“含まれる”行だけ抽出
  2. (店名 + 開催期間) が未送信なら LINE に Push
想定: GitHub Actions で30分おき実行
"""

import os, sqlite3, urllib.parse, requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
TARGET_URL = (
    "https://map.kaldi.co.jp/kaldi/articleList"
    "?account=kaldi&accmd=1&ftop=1"
)
DB_FILE = "seen.db"

# ★ここに生活圏ワードを好きに並べる（完全一致でなく “部分一致” ！）
TARGET_KEYWORDS = [
    "大井町",
    "荏原町",
    "戸越",
    # 近所でなくてもテストしたい場合は ↓ に追加
    # "各務原",
]

# ──────────────────────────────────────────────
def is_target_store(store: str) -> bool:
    """店名にキーワードが 1 つでも含まれていれば True"""
    return any(k in store for k in TARGET_KEYWORDS)


def fetch_target_articles():
    """yield (unique_id, message_body) for each matched sale row"""
    html = requests.get(TARGET_URL, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.select("table.cz_sp_table tr"):
        name_tag = row.select_one("span.salename")
        if not name_tag:
            continue                        # 見出し列など

        store = name_tag.text.strip()
        if not is_target_store(store):
            continue                        # ◎ 部分一致フィルタ

        title_tag = row.select_one("span.saletitle, span.saletitle_f")
        title = title_tag.text.strip() if title_tag else "セール"

        date_tag = row.select_one("p.saledate, p.saledate_f")
        term = date_tag.text.strip() if date_tag else ""

        link_tag = row.select_one("a[href*='detailMap']")
        url = urllib.parse.urljoin(TARGET_URL, link_tag["href"]) if link_tag else TARGET_URL

        art_id = f"{store}_{term}"          # 店＋期間でユニーク化
        body = f"🛒 {store}\n{title}（{term}）\n{url}"
        yield art_id, body


def diff_since_last_run(records):
    """既に送った id はスキップしてリストを返す"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY)")
    new_msgs = []
    for art_id, msg in records:
        if not conn.execute("SELECT 1 FROM seen WHERE id=?", (art_id,)).fetchone():
            new_msgs.append(msg)
            conn.execute("INSERT INTO seen(id) VALUES(?)", (art_id,))
    conn.commit()
    conn.close()
    return new_msgs


def push_line(msgs):
    """LINE Messaging API Push"""
    if not msgs:
        print("No new sale info.")
        return

    headers = {
        "Authorization": f"Bearer {os.environ['LINE_TOKEN']}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": os.environ["LINE_USER_ID"],
        "messages": [{"type": "text", "text": "\n\n".join(msgs)}],
    }
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        json=payload,
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    print(f"Pushed {len(msgs)} message(s) to LINE.")


if __name__ == "__main__":
    fresh = diff_since_last_run(fetch_target_articles())
    push_line(fresh)
