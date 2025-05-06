# -*- coding: utf-8 -*-
"""
KALDI セール一覧をクロールして 近所ワード含む行だけ LINE へ Push
"""

import os, sqlite3, urllib.parse, requests, datetime
from bs4 import BeautifulSoup

BASE_URL = "https://map.kaldi.co.jp/kaldi/articleList"
DB_FILE  = "seen.db"

# 検索キーワード（部分一致）
KEYWORDS = ["大井町", "荏原町", "戸越", "各務原"]

# ─────────────────────────────────────────────
def build_url() -> str:
    """現在の JST を kk w001 に付けた URL を返す"""
    jst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    ts = jst_now.strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "account": "kaldi",
        "accmd": 1,
        "ftop": 1,
        "kkw001": ts,          # ★ここがポイント！
    }
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"

def fetch_target_articles():
    url  = build_url()
    html = requests.get(url, timeout=15).text

    # 先頭だけログに残す（後で off にして OK）
    print("HTML_HEAD:", html[:500].replace("\n", "\\n")[:300], "...")

    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("table.cz_sp_table tr"):
        name_tag = row.select_one("span.salename")
        if not name_tag:
            continue
        store = name_tag.text.strip()
        if not any(k in store for k in KEYWORDS):
            continue

        title_tag = row.select_one("span.saletitle, span.saletitle_f")
        title = title_tag.text.strip() if title_tag else "セール"

        date_tag  = row.select_one("p.saledate, p.saledate_f")
        term = date_tag.text.strip() if date_tag else ""

        link_tag = row.select_one("a[href*='detailMap']")
        url_abs  = urllib.parse.urljoin(url, link_tag["href"]) if link_tag else url

        art_id = f"{store}_{term}"
        msg    = f"🛒 {store}\n{title}（{term}）\n{url_abs}"
        yield art_id, msg

# 既読管理・LINE Push は前回と同じ -------------------------------
def diff_since_last_run(records):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY)")
    new_msgs = []
    for art_id, msg in records:
        if not conn.execute("SELECT 1 FROM seen WHERE id=?", (art_id,)).fetchone():
            new_msgs.append(msg)
            conn.execute("INSERT INTO seen(id) VALUES(?)", (art_id,))
    conn.commit(); conn.close()
    return new_msgs

def push_line(msgs):
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
    r = requests.post("https://api.line.me/v2/bot/message/push",
                      json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    print(f"Pushed {len(msgs)} message(s) to LINE.")

# ─────────────────────────────────────────────
if __name__ == "__main__":
    fresh = diff_since_last_run(fetch_target_articles())
    push_line(fresh)
