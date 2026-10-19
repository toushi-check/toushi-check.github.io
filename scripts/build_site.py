"""data/companies.json から静的サイトを site/ に生成する。

ページ:
  /                 検索付きの一覧
  /c/<id>/          業者ごとのページ
  /about/           運営者・出典・免責
  /sitemap.xml, /robots.txt
"""
import datetime as dt
import html
import json
import re
import shutil

from common import COMPANIES_JSON, META_JSON, ROOT, load_config, read_json

SITE = ROOT / "site"
ASSETS = ROOT / "templates"
JST = dt.timezone(dt.timedelta(hours=9))

# 金融庁リストから消えた業者のページを残す日数(過ぎたらページ自体を作らない)
REMOVED_KEEP_DAYS = 180

E = html.escape

# 金融庁の「内容」欄の言葉 -> 一般向けの説明
CATEGORY_HELP = [
    ("店頭デリバティブ", "FX(外国為替証拠金取引)、バイナリーオプション、CFDなどの取引を、日本の登録を受けずに勧誘していたケースです。海外のFX・バイナリーオプション業者が多く含まれます。"),
    ("詐称", "実在する登録業者の名前や登録番号を勝手に使って、本物の業者になりすましていたケースです。名乗られた会社そのものとは無関係です。"),
    ("表示した", "ウェブサイトや勧誘資料に、金融商品取引業者であるかのような表示をしていたケースです。"),
    ("暗号資産", "暗号資産(仮想通貨)を使った取引や投資の勧誘に関わるケースです。"),
    ("有価証券", "株式・社債・ファンドなどの販売や勧誘を、登録を受けずに行っていたケースです。"),
    ("投資助言", "投資の助言(売買のアドバイスやシグナル配信など)を、登録を受けずに行っていたケースです。"),
]

CONTACTS = [
    ("金融庁 金融サービス利用者相談室", "0570-016811", "無登録業者・投資の勧誘についての相談"),
    ("消費者ホットライン", "188", "最寄りの消費生活センターにつながります"),
    ("警察相談専用電話", "#9110", "被害に遭った・お金を振り込んでしまった場合"),
]


def impersonated(name: str):
    """'不明(株式会社◯◯の商号等を詐称)' -> '株式会社◯◯'"""
    m = re.match(r"不明\((.+?)の商号等を詐称", name)
    return m.group(1) if m else None


def display_name(c: dict) -> str:
    imp = impersonated(c["name"])
    return f"「{imp}」を名乗る無登録業者" if imp else c["name"]


def ym_label(ym: str, raw: str) -> str:
    if ym:
        y, m = ym.split("-")
        return f"{int(y)}年{int(m)}月"
    return raw or "不明"


def explain(c: dict) -> list:
    text = c.get("business", "") + c.get("name", "")
    return [desc for key, desc in CATEGORY_HELP if key in text]


def layout(cfg: dict, title: str, desc: str, path: str, body: str, depth: int, noindex: bool = False) -> str:
    rel = "../" * depth
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex else ""
    canonical = cfg["base_url"].rstrip("/") + path
    return f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{robots}<link rel="canonical" href="{E(canonical)}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{E(canonical)}">
<link rel="stylesheet" href="{rel}style.css">
</head><body>
<header class="top"><a class="brand" href="{rel}">{E(cfg['site_name'])}</a></header>
<main>{body}</main>
<footer><p>出典:<a href="{E(cfg['source_page_url'])}" rel="nofollow noopener">金融庁「無登録で金融商品取引業を行う者の名称等について」</a>を加工して作成しています。
本サイトは金融庁・警察とは関係のない個人運営の情報サイトです。</p>
<p><a href="{rel}about/">運営者・免責事項</a></p></footer>
</body></html>"""


def company_page(cfg: dict, c: dict, related: list, fetched: str) -> str:
    name = display_name(c)
    imp = impersonated(c["name"])
    services = "、".join(c.get("services") or [])
    listed = ym_label(c.get("listed_ym"), c.get("listed"))
    region = c.get("region") or "不明"

    title = f"{name}" + (f"({services})" if services else "") + "|金融庁の無登録業者リスト掲載情報"
    desc = (f"{name}" + (f"(サービス名:{services})" if services else "")
            + f"は、金融庁の「無登録で金融商品取引業を行う者」のリストに{listed}付で掲載されています。掲載内容と相談先をまとめています。")

    imp_box = ""
    if imp:
        imp_box = (f'<div class="notice"><strong>ご注意:</strong>このページは「{E(imp)}」の名前を<strong>勝手に使っていた</strong>業者についての情報です。'
                   f'実在する「{E(imp)}」とは無関係です。</div>')

    removed = ""
    lead = (f'<p class="lead">この業者は、金融庁が公表している<strong>「無登録で金融商品取引業を行う者」のリスト</strong>に掲載されています({E(listed)}掲載)。</p>')
    if c.get("removed"):
        removed = (f'<div class="notice"><strong>掲載終了:</strong>この業者は、{E(c["removed"])}時点で金融庁の公表リストから確認できなくなりました。'
                   "現在の状況は金融庁のページでご確認ください。このページは一定期間後に削除されます。</div>")
        lead = (f'<p class="lead">この業者は、金融庁が公表している<strong>「無登録で金融商品取引業を行う者」のリスト</strong>に掲載されていました({E(listed)}掲載)。</p>')

    rows = [
        ("名称", c["name"]),
        ("サービス名", services or "記載なし"),
        ("金融庁の掲載内容", c.get("business") or "記載なし"),
        ("備考", c.get("note") or "記載なし"),
        ("掲載時期", listed),
        ("所在", region),
    ]
    table = "".join(f"<tr><th>{E(k)}</th><td>{E(v)}</td></tr>" for k, v in rows)
    help_html = "".join(f"<p>{E(t)}</p>" for t in explain(c)) or "<p>金融商品取引業の登録を受けずに業務を行っていたとして、金融庁が公表しています。</p>"
    contacts = "".join(f"<li><strong>{E(n)}</strong>:<a href=\"tel:{E(t)}\">{E(t)}</a><br><span>{E(d)}</span></li>" for n, t, d in CONTACTS)
    rel_html = "".join(f'<li><a href="../{E(r["id"])}/">{E(display_name(r))}</a></li>' for r in related)

    body = f"""
<nav class="crumb"><a href="../../">トップ</a> › 業者情報</nav>
<h1>{E(name)}</h1>
{f'<p class="sub">サービス名:{E(services)}</p>' if services else ''}
{lead}
{imp_box}{removed}
<table class="info">{table}</table>
<h2>どういう意味?</h2>
{help_html}
<p>日本の居住者に投資の勧誘をするには、金融庁(財務局)への登録が必要です。登録のない業者とのトラブルは、法的な保護を受けにくく、出金できないなどの被害が多く報告されています。</p>
<h2>勧誘を受けたら</h2>
<ul class="checks">
<li>お金を振り込む前に、相手の登録を<a href="https://www.fsa.go.jp/menkyo/menkyo.html" rel="nofollow noopener">金融庁の登録業者一覧</a>で確認する</li>
<li>「出金するには手数料・税金を先に払って」と言われたら、払わずに相談する</li>
<li>「被害を取り戻せる」と持ちかける業者は、二次被害の可能性があります</li>
</ul>
<h2>相談先</h2>
<ul class="contacts">{contacts}</ul>
{f'<h2>同じ種類の掲載業者</h2><ul class="related">{rel_html}</ul>' if rel_html else ''}
<p class="small">掲載情報は金融庁の公表内容(最終確認:{E(fetched)})に基づきます。本ページは業者が詐欺であると断定するものではありません。最新情報は必ず<a href="{E(cfg['source_page_url'])}" rel="nofollow noopener">金融庁のページ</a>でご確認ください。</p>
"""
    return layout(cfg, title, desc, f"/c/{c['id']}/", body, depth=2, noindex=bool(c.get("removed")))


def index_page(cfg: dict, companies: list, fetched: str) -> str:
    items = sorted(companies, key=lambda c: (c.get("listed_ym") or "", c["first_seen"]), reverse=True)
    data = [{"i": c["id"], "n": display_name(c), "s": " ".join(c.get("services") or []),
             "r": c.get("region", ""), "l": ym_label(c.get("listed_ym"), c.get("listed"))} for c in items]
    latest = "".join(
        f'<li><a href="c/{E(c["id"])}/">{E(display_name(c))}</a> <span class="meta">{E(ym_label(c.get("listed_ym"), c.get("listed")))}・{E(c.get("region", ""))}</span></li>'
        for c in items[:20])
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    body = f"""
<h1>{E(cfg['site_name'])}</h1>
<p class="lead">{E(cfg['site_tagline'])}。勧誘してきた業者の名前やサービス名を入れてください。</p>
<input id="q" type="search" placeholder="業者名・サービス名(例:Babafx)" autocomplete="off">
<p id="count" class="small"></p>
<ul id="results" class="results"></ul>
<h2>最近掲載された業者</h2>
<ul class="related">{latest}</ul>
<p class="small">掲載件数:{len(companies)}件/最終確認:{E(fetched)}<br>
ここに無いからといって、安全な業者とは限りません。金融庁が把握していない業者も多数あります。</p>
<script id="d" type="application/json">{data_json}</script>
<script>
const D=JSON.parse(document.getElementById('d').textContent);
const norm=s=>s.normalize('NFKC').toLowerCase().replace(/\\s+/g,'');
const q=document.getElementById('q'),ul=document.getElementById('results'),cnt=document.getElementById('count');
q.addEventListener('input',()=>{{
  const k=norm(q.value);ul.innerHTML='';
  if(!k){{cnt.textContent='';return;}}
  const hit=D.filter(x=>norm(x.n+x.s).includes(k)).slice(0,50);
  cnt.textContent=hit.length?hit.length+'件見つかりました(金融庁リストに掲載あり)':'リストには見つかりませんでした。ただし、安全とは限りません。';
  for(const x of hit){{const li=document.createElement('li');const a=document.createElement('a');
    a.href='c/'+x.i+'/';a.textContent=x.n+(x.s?' ('+x.s+')':'');li.append(a);
    const m=document.createElement('span');m.className='meta';m.textContent=' '+x.l+'・'+x.r;li.append(m);ul.append(li);}}
}});
</script>"""
    desc = f"金融庁の無登録業者リスト({len(companies)}件)を、業者名・サービス名で検索できます。投資の勧誘を受けたら、まず確認を。"
    return layout(cfg, f"{cfg['site_name']}|金融庁の無登録業者を検索", desc, "/", body, depth=0)


def about_page(cfg: dict) -> str:
    body = f"""
<h1>運営者・免責事項</h1>
<h2>このサイトについて</h2>
<p>金融庁が公表している「無登録で金融商品取引業を行う者の名称等について」のリストを、業者名やサービス名で調べやすくするための個人運営サイトです。リストは毎日自動で確認・更新しています。</p>
<h2>免責事項</h2>
<ul>
<li>掲載内容は金融庁の公表情報に基づきますが、正確性・最新性を保証するものではありません。</li>
<li>掲載された業者が詐欺であると断定するものではありません。</li>
<li>リストに載っていないことは、安全であることを意味しません。</li>
<li>本サイトは金融庁・警察・その他の公的機関とは関係ありません。</li>
<li>被害の回復や返金の代行・あっせんは一切行っていません。</li>
</ul>
<h2>出典</h2>
<p><a href="{E(cfg['source_page_url'])}" rel="nofollow noopener">金融庁「無登録で金融商品取引業を行う者の名称等について」</a></p>
"""
    return layout(cfg, f"運営者・免責事項|{cfg['site_name']}", "本サイトの運営方針と免責事項。", "/about/", body, depth=1)


def related_for(c: dict, companies: list, n: int = 6) -> list:
    keys = [k for k, _ in CATEGORY_HELP if k in c.get("business", "") + c["name"]]
    pool = [x for x in companies if x["id"] != c["id"] and not x.get("removed")
            and (any(k in x.get("business", "") + x["name"] for k in keys) or x.get("region") == c.get("region"))]
    pool.sort(key=lambda x: x.get("listed_ym") or "", reverse=True)
    return pool[:n]


def removed_expired(c: dict, today: dt.date) -> bool:
    try:
        return (today - dt.date.fromisoformat(c["removed"])).days > REMOVED_KEEP_DAYS
    except (KeyError, ValueError):
        return False


def main():
    cfg = load_config()
    all_companies = read_json(COMPANIES_JSON, default=[])
    if not all_companies:
        raise SystemExit("data/companies.json がありません。先に fetch_fsa.py を実行してください。")
    today = dt.datetime.now(JST).date()
    # 掲載中の業者 / 掲載終了(ページは残すが検索・一覧・sitemapから外す) / 期限切れ(ページを作らない)
    active = [c for c in all_companies if not c.get("removed")]
    ended = [c for c in all_companies if c.get("removed") and not removed_expired(c, today)]
    meta = read_json(META_JSON, default={}) or {}
    fetched = (meta.get("fetched_at") or "")[:10]

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "c").mkdir(parents=True)
    shutil.copy(ASSETS / "style.css", SITE / "style.css")

    (SITE / "index.html").write_text(index_page(cfg, active, fetched), encoding="utf-8")
    (SITE / "about").mkdir()
    (SITE / "about" / "index.html").write_text(about_page(cfg), encoding="utf-8")

    for c in active + ended:
        d = SITE / "c" / c["id"]
        d.mkdir()
        (d / "index.html").write_text(company_page(cfg, c, related_for(c, active), fetched), encoding="utf-8")

    base = cfg["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/about/"] + [f"{base}/c/{c['id']}/" for c in active]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print(f"サイト生成完了: 掲載中 {len(active)} 件 / 掲載終了 {len(ended)} 件 -> site/")


if __name__ == "__main__":
    main()
