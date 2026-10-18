"""共通処理: 設定の読み込み、文字列の正規化、和暦の変換、スラッグ生成。"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
COMPANIES_JSON = DATA_DIR / "companies.json"
NEW_JSON = DATA_DIR / "new_entries.json"
META_JSON = DATA_DIR / "meta.json"


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def clean(text: str) -> str:
    """改行・連続空白をまとめる。全角英数は半角に寄せる(NFKC)。"""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(name: str) -> str:
    """業者名から、実行のたびに変わらないURL用IDを作る。"""
    key = clean(name).lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


_ERA = {"令和": 2018, "平成": 1988}


def wareki_to_ym(text: str) -> str:
    """'令和8年9月' -> '2026-09'。変換できなければ空文字。"""
    t = clean(text)
    m = re.search(r"(令和|平成)\s*(元|\d+)\s*年\s*(\d+)\s*月", t)
    if not m:
        return ""
    era, y, mo = m.groups()
    year = _ERA[era] + (1 if y == "元" else int(y))
    return f"{year:04d}-{int(mo):02d}"


def extract_service_names(note: str) -> list:
    """備考の『サービスの名称は「A」、「B」である』からサービス名を取り出す。"""
    t = clean(note)
    m = re.search(r"サービス(?:の)?名称は(.+?)(?:である|であり|。|$)", t)
    if not m:
        return []
    names = re.findall(r"「([^」]+)」", m.group(1))
    out = []
    for n in names:
        for part in re.split(r"[、,]", n):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
