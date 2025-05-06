# -*- coding: utf-8 -*-
"""
KALDI セール監視 & LINE Push
30 分おきに GitHub Actions から呼び出される想定
"""
import os, requests, sqlite3
from bs4 import BeautifulSoup

TARGET_URL = "https://map.kaldi.co.jp/kaldi/articleList?accmd=1&account=kaldi&ftop=1"
MY_STORES  = {
    # ちゅっくの生活圏を列挙
    "カルディコーヒーファーム アトレ大井町2店",
    "カルディコーヒーファーム 荏原町店",
    "カルディコーヒーファーム 戸越銀座店",
    "札幌西岡店",
}

DB_FILE = "seen.db"

def fetch_target_articles():
    html = requests.get(TARGET_URL, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    print("DEBUG li.store count:", len(soup.select("li.store")))
    for li in soup.select("li.store"):
        store = li.select_one(".ttl").text.strip()
        print("DEBUG store_candidate:", store)            
        if store not in MY_STORES:
            continue
        title = li.select_one(".sales_type").text.strip()
        term  = li.select_one(".date").text.strip()
        url   = li.select_one("a")["href"]
        art_id = url.split("/")[-1]
        yield art_id, f"🛒{store}\n{title}（{term}）\n{url}"

def diff_since_last_run(records):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY)")
    new_msgs = []
    for art_id, msg in records:
        cur = conn.execute("SELECT 1 FROM seen WHERE id=?", (art_id,))
        if not cur.fetchone():
            new_msgs.append(msg)
            conn.execute("INSERT INTO seen(id) VALUES(?)", (art_id,))
    conn.commit(); conn.close()
    return new_msgs

def push_line(msgs):
    if not msgs: return
    headers = {
        "Authorization": f"Bearer {os.environ['LINE_TOKEN']}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": os.environ["LINE_USER_ID"],
        "messages": [{"type": "text", "text": "\n\n".join(msgs)}]
    }
    r = requests.post("https://api.line.me/v2/bot/message/push",
                      json=payload, headers=headers, timeout=10)
    r.raise_for_status()

if __name__ == "__main__":
    fresh = diff_since_last_run(fetch_target_articles())
    print("DEBUG fresh_count:", len(fresh))
    push_line(fresh)
