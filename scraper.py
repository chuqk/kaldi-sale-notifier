# -*- coding: utf-8 -*-
"""
KALDI セール一覧をクロールして
  - 自分の関心店舗 (MY_STORES) に該当する行だけ抽出
  - 過去に送った組み合わせ (store + term) はスキップ
  - 新着があれば LINE Messaging API で Push

実行想定: GitHub Actions / 30 分おき
"""

import os, sqlite3, urllib.parse, requests
from bs4 import BeautifulSoup

TARGET_URL = (
    "https://map.kaldi.co.jp/kaldi/articleList"
    "?account=kaldi&accmd=1&ftop=1"
)  # 全店舗分まとめて取得
DB_FILE = "seen.db"

# ======= 自宅圏の店舗を正確な表記で列挙 =======
MY_STORES = {
    "アトレ大井町店",
    "荏原町店",
    "戸越銀座店",
    "各務原店",
    # "○○店", ... 追加可
}


def fetch_target_articles():
    """yield (unique_id, message_body) for each matched row"""
    html = requests.get(TARGET_URL, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")

    # <tr> 単位でセール行を抽出
    for row in soup.select("table.cz_sp_table tr"):
        store_tag = row.select_one("span.salename")
        if not store_tag:
            continue  # 見出し行などをスキップ
        store = store_tag.text.strip()
        print("DEBUG STORE:", store)

        # フィルタ: 自分のリストに無ければ continue
        if store not in MY_STORES:
            continue

        print("DEBUG HIT :", store)

        # セール種別（タイトル）
        title_tag = row.select_one("span.saletitle, span.saletitle_f, span.salettile")
        title = title_tag.text.strip() if title_tag else "セール"

        # 開催期間
        date_tag = row.select_one("p.saledate, p.saledate_f")
        term = date_tag.text.strip() if date_tag else ""

        # 詳細リンク (相対→絶対 URL)
        link_tag = row.select_one("a[href*='detailMap']")
        url = urllib.parse.urljoin(TARGET_URL, link_tag["href"]) if link_tag else TARGET_URL

        # 一意キー: 店舗 + 期間（変更・延長も検知したい場合は +title など足しても可）
        art_id = f"{store}_{term}"

        yield art_id, f"🛒{store}\n{title}（{term}）\n{url}"


def diff_since_last_run(records):
    """新規のみリストで返す & DB に既読を記録"""
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
    r = requests.post("https://api.line.me/v2/bot/message/push", json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    print(f"Pushed {len(msgs)} message(s) to LINE.")


if __name__ == "__main__":
    fresh_msgs = diff_since_last_run(fetch_target_articles())
    push_line(fresh_msgs)
