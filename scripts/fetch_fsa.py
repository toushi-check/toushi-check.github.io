"""金融庁「無登録で金融商品取引業を行う者の名称等について(HTML版)」を取り込む。

使い方:
  python scripts/fetch_fsa.py                 # 金融庁サイトから取得
  python scripts/fetch_fsa.py --file x.html   # 手元のHTMLで試す(テスト用)

出力:
  data/companies.json   全業者(初回掲載を検知した日 first_seen を保持)
  data/new_entries.json 今回新しく増えた業者(X投稿用)
  data/meta.json        取得日時・件数など
"""
import argparse
import datetime as dt
import sys

import requests
from bs4 import BeautifulSoup

from common import (COMPANIES_JSON, META_JSON, NEW_JSON, clean,
                    extract_service_names, load_config, read_json, slugify,
                    wareki_to_ym, write_json)

JST = dt.timezone(dt.timedelta(hours=9))

# 列見出しに含まれる文字 -> 内部のキー
COLUMN_KEYS = [
    ("商号", "name"),
    ("内容", "business"),
    ("備考", "note"),
    ("掲載時期", "listed"),
    ("所在", "region"),
]


def download(url: str) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; fsa-list-checker/1.0)"}
    last = None
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:  # 一時的な失敗は再試行
            last = e
    raise SystemExit(f"取得に失敗しました: {last}")


def parse(html: bytes) -> list:
    soup = BeautifulSoup(html, "html.parser")  # 文字コードはmetaタグから自動判定
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]
        if not any("商号" in h for h in header):
            continue
        index = {}
        for i, h in enumerate(header):
            for needle, key in COLUMN_KEYS:
                if needle in h and key not in index:
                    index[key] = i
        if "name" not in index:
            continue
        out = []
        for tr in rows[1:]:
            cells = [clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
            if not cells or not any(cells):
                continue

            def col(key):
                i = index.get(key)
                return cells[i] if i is not None and i < len(cells) else ""

            name = col("name")
            if not name:
                continue
            note = col("note")
            out.append({
                "id": slugify(name),
                "name": name,
                "business": col("business"),
                "note": note,
                "services": extract_service_names(note),
                "listed": col("listed"),
                "listed_ym": wareki_to_ym(col("listed")),
                "region": col("region"),
            })
        return out
    raise SystemExit("業者一覧の表が見つかりません。ページの構成が変わった可能性があります。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="ネットから取らず、手元のHTMLを読む")
    ap.add_argument("--today", help="日付を固定する(テスト用, YYYY-MM-DD)")
    args = ap.parse_args()

    cfg = load_config()
    html = open(args.file, "rb").read() if args.file else download(cfg["source_url"])
    rows = parse(html)

    today = args.today or dt.datetime.now(JST).date().isoformat()
    prev = read_json(COMPANIES_JSON, default=None)
    prev_by_id = {c["id"]: c for c in (prev or [])}

    # 安全装置: 件数が前回の半分未満なら、ページが壊れていると見なして上書きしない
    if prev and len(rows) < len(prev) * 0.5:
        print(f"件数が急減しました(前回{len(prev)} -> 今回{len(rows)})。更新を中止します。")
        sys.exit(2)

    merged, seen, new_entries = [], set(), []
    for r in rows:
        if r["id"] in seen:  # 同名の重複行はまとめる
            continue
        seen.add(r["id"])
        old = prev_by_id.get(r["id"])
        r["first_seen"] = old["first_seen"] if old else today
        if prev is not None and not old:
            new_entries.append(r)
        merged.append(r)

    # 一覧から消えた業者も、過去に掲載された事実としてページを残す
    for cid, old in prev_by_id.items():
        if cid not in seen:
            old["removed"] = old.get("removed") or today
            merged.append(old)

    write_json(COMPANIES_JSON, merged)
    write_json(NEW_JSON, new_entries)
    write_json(META_JSON, {
        "fetched_at": dt.datetime.now(JST).isoformat(timespec="seconds"),
        "count": len(rows),
        "new_count": len(new_entries),
        "baseline": prev is None,
    })
    label = "初回取り込み(新規投稿なし)" if prev is None else f"新規 {len(new_entries)} 件"
    print(f"取り込み完了: {len(rows)} 件 / {label}")


if __name__ == "__main__":
    main()
