"""data/new_entries.json の新規掲載業者をXに投稿する。

環境変数(GitHubのSecretsに登録):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
どれかが無い場合は、投稿せずに内容を表示するだけ(ドライラン)。
"""
import os
import sys
import time
import unicodedata

from common import NEW_JSON, load_config, read_json

ENDPOINT = "https://api.x.com/2/tweets"
LIMIT = 280  # Xの文字数上限(日本語は1文字=2として数える)
URL_WEIGHT = 23  # URLは長さに関係なく23として数える


def weight(text: str) -> int:
    w = 0
    for ch in text:
        w += 1 if unicodedata.east_asian_width(ch) in ("Na", "H") or ord(ch) < 0x1100 else 2
    return w


def compose(c: dict, cfg: dict) -> str:
    from build_site import display_name, ym_label  # 表示名の作り方をサイトと揃える
    url = f"{cfg['base_url'].rstrip('/')}/c/{c['id']}/"
    tags = " ".join("#" + t for t in cfg.get("x_hashtags", []))
    head = "【金融庁 無登録業者リストに新規掲載】\n"
    name = display_name(c)
    services = "、".join(c.get("services") or [])
    detail = f"\nサービス名:{services}" if services else ""
    tail = f"\n{c.get('region', '')}/{ym_label(c.get('listed_ym'), c.get('listed'))}掲載\n詳細:"
    footer = f"\n{tags}"

    def total(n, d):
        return weight(head + n + d + tail + footer) + URL_WEIGHT

    # 長すぎる場合は、サービス名 -> 業者名 の順に短くする
    while total(name, detail) > LIMIT and len(detail) > 12:
        detail = detail[:-2] + "…"
    while total(name, detail) > LIMIT and len(name) > 10:
        name = name[:-2] + "…"
    return f"{head}{name}{detail}{tail}{url}{footer}"


def main():
    cfg = load_config()
    entries = read_json(NEW_JSON, default=[]) or []
    if not entries:
        print("新規掲載はありません。投稿なし。")
        return
    entries = entries[: int(cfg.get("max_x_posts_per_run", 5))]

    keys = [os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    dry = not all(keys)
    session = None
    if not dry:
        from requests_oauthlib import OAuth1Session
        session = OAuth1Session(keys[0], client_secret=keys[1],
                                resource_owner_key=keys[2], resource_owner_secret=keys[3])

    failed = 0
    for c in entries:
        text = compose(c, cfg)
        if dry:
            print("---- ドライラン(投稿しません) ----\n" + text)
            continue
        r = session.post(ENDPOINT, json={"text": text}, timeout=30)
        if r.status_code >= 300:
            failed += 1
            print(f"投稿失敗 {r.status_code}: {r.text[:300]}")
        else:
            print(f"投稿しました: {c['name']}")
        time.sleep(5)  # 連投を避ける
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
