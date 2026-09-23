"""農薬登録情報提供システム（FAMIC）から適用表を取得し pesticide-data.json を生成する。

使い方:  python tools/fetch_pesticides.py
対象の登録番号は REG_NOS を編集する。取得日が confirmed に記録される。
"""
import json
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

REG_NOS = [
    "20102",  # モスピラン液剤
    "23121",  # ベニカベジフルスプレー
    "19616",  # ゼンターリ顆粒水和剤
    "4962",   # 住化スミチオン乳剤（販売元違いあり・要ラベル確認）
    "21939",  # 家庭園芸用スミチオン乳剤（同上）
    "7288",   # ダイアジノン粒剤３（販売元違いあり・要ラベル確認）
    "19523",  # 家庭園芸用ダイアジノン粒剤３（同上）
    "23952",  # ピシロックフロアブル
    "4951",   # ダイン（展着剤）
    "24251",  # パレハ（展着剤）
    "22345",  # ジマンダイセン水和剤
    "21117",  # パンチョＴＦ顆粒水和剤
    "18406",  # コロマイト乳剤
    "22464",  # プレバソンフロアブル５
]
URL = "https://pesticide.maff.go.jp/agricultural-chemicals/details/{}"
OUT = Path(__file__).resolve().parent.parent / "pesticide-data.json"


class Tables(HTMLParser):
    """全tableをセル(rowspan/colspan付き)の行列として集める"""

    def __init__(self):
        super().__init__()
        self.tables, self._t, self._row, self._cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._t = []
        elif tag == "tr" and self._t is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"text": "", "rs": int(a.get("rowspan") or 1), "cs": int(a.get("colspan") or 1)}
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._t.append(self._row)
            self._row = None
        elif tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data


def to_grid(rows):
    grid = {}
    for ri, row in enumerate(rows):
        ci = 0
        for c in row:
            while (ri, ci) in grid:
                ci += 1
            for r in range(c["rs"]):
                for k in range(c["cs"]):
                    grid[(ri + r, ci + k)] = c["text"]
            ci += c["cs"]
    if not grid:
        return []
    nr = max(r for r, _ in grid) + 1
    nc = max(c for _, c in grid) + 1
    return [[grid.get((r, c), "") for c in range(nc)] for r in range(nr)]


_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
_opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"),
                      ("Accept-Language", "ja")]


def get_html(url):
    with _opener.open(url, timeout=30) as res:
        return res.read().decode("utf-8")


def fetch(reg):
    html = get_html(URL.format(reg))
    p = Tables()
    p.feed(html)
    info = {}
    for row in p.tables[0]:
        if len(row) >= 2:
            info[row[0]["text"]] = row[1]["text"]
    comp = [" ".join(x for x in r if x) for r in to_grid(p.tables[1])[1:]]
    app = next((t for t in p.tables if t and "作物名" in "".join(c["text"] for c in t[0])), None)
    g = to_grid(app) if app else []
    head, rows = (g[0], g[1:]) if g else ([], [])

    def col(*keys):
        for i, h in enumerate(head):
            if any(k in h for k in keys):
                return i
        return -1

    i_crop, i_pest, i_place = col("作物名"), col("適用病害虫"), col("適用場所")
    i_dil, i_vol, i_time = col("希釈倍数", "使用量"), col("使用液量"), col("使用時期")
    i_cnt, i_meth = col("本剤の使用回数"), col("使用方法")
    tot_idx = [i for i, h in enumerate(head) if "を含む農薬の総使用回数" in h]
    get = lambda r, i: r[i] if i >= 0 else ""

    groups = {}
    for r in rows:
        if r == head:
            continue
        totals = {head[i].replace("を含む農薬の総使用回数", ""): r[i] for i in tot_idx}
        key = (get(r, i_crop), get(r, i_place), get(r, i_dil), get(r, i_vol), get(r, i_time),
               get(r, i_cnt), get(r, i_meth), json.dumps(totals, ensure_ascii=False))
        pest = get(r, i_pest)
        if key in groups:
            if pest and pest not in groups[key]["pests"]:
                groups[key]["pests"].append(pest)
        else:
            groups[key] = {"crop": key[0], "place": key[1], "pests": [pest] if pest else [],
                           "dil": key[2], "vol": key[3], "timing": key[4], "count": key[5],
                           "method": key[6], "totals": totals}
    return {"regNo": reg, "name": info.get("農薬の名称", ""), "type": info.get("農薬の種類", ""),
            "use": info.get("用途", ""), "comp": comp, "apps": list(groups.values())}


def main():
    get_html("https://pesticide.maff.go.jp/")  # セッションCookie取得
    products = []
    for reg in REG_NOS:
        p = fetch(reg)
        print(f"{reg} {p['name']}: {len(p['apps'])}件", file=sys.stderr)
        products.append(p)
    data = {"source": "農薬登録情報提供システム（FAMIC） https://pesticide.maff.go.jp/",
            "confirmed": date.today().isoformat(), "products": products}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"-> {OUT} ({OUT.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
