"""
KALDI セール一覧をスクレイピングして、指定キーワードにマッチする
店舗のセール情報を LINE に通知するツール。
"""

import datetime
import os
import sqlite3
import textwrap
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_URL = "https://map.kaldi.co.jp/kaldi/articleList"
DB_FILE = str(Path(__file__).resolve().parent / "seen.db")
JST = datetime.timezone(datetime.timedelta(hours=9))

KEYWORDS = [k.strip() for k in os.environ.get("KEYWORDS", "").split(",") if k.strip()]
if not KEYWORDS:
    raise SystemExit(
        "KEYWORDS が設定されていません。.env に KEYWORDS=目黒,大井町,... を設定してください。"
    )

HEADLINE = "☕️ KALDIの新着セール情報が届いたよ！\n\n"


def build_url() -> str:
    """現在 JST のタイムスタンプを kkw001 に付けた URL を返す。"""
    ts = datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S")
    params = dict(account="kaldi", accmd=1, ftop=1, kkw001=ts)
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch_target_articles():
    """セール一覧ページから KEYWORDS にマッチする店舗情報を抽出する。"""
    url = build_url()
    html = requests.get(url, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.select("table.cz_sp_table tr"):
        name_tag = row.select_one("span.salename")
        if not name_tag:
            continue
        store = name_tag.text.strip()

        if not any(k in store for k in KEYWORDS):
            continue

        addr = row.select_one("span.saleadress").text.strip()
        title = row.select_one("span.saletitle, span.saletitle_f").text.strip()
        term = row.select_one("p.saledate, p.saledate_f").text.strip()
        detail = row.select_one("p.saledetail").text.strip()
        note_el = row.select_one("p.saledetail_notes")
        notes = note_el.text.strip() if note_el else ""

        body = textwrap.dedent(f"""\
            🛒 {store}
            {addr}
            {title}（{term}）
            {detail}
            {notes}""").rstrip()

        yield f"{store}_{term}", body, url


def diff_since_last_run(records):
    """未通知のセール情報だけを返し、通知済みとして DB に記録する。"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY)")
        new_msgs, page_url = [], None
        for art_id, msg, url in records:
            if not conn.execute("SELECT 1 FROM seen WHERE id=?", (art_id,)).fetchone():
                new_msgs.append(msg)
                conn.execute("INSERT INTO seen(id) VALUES(?)", (art_id,))
            page_url = url
        conn.commit()
    return new_msgs, page_url


def push_line(msgs, page_url):
    """新着セール情報を LINE Push Message API で送信する。"""
    if not msgs:
        print("No new sale info.")
        return

    text = HEADLINE + "\n\n".join(msgs) + f"\n\n🔗 一覧ページはこちら\n{page_url}"

    headers = {
        "Authorization": f"Bearer {os.environ['LINE_TOKEN']}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": os.environ["LINE_USER_ID"],
        "messages": [{"type": "text", "text": text}],
    }
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        json=payload, headers=headers, timeout=10,
    )
    resp.raise_for_status()
    print(f"Pushed {len(msgs)} sale(s) to LINE.")


if __name__ == "__main__":
    fresh, page = diff_since_last_run(fetch_target_articles())
    push_line(fresh, page)
