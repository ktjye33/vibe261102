"""마켓컬리 상품 후기 감성 분석기 (PyQt6 GUI).

컬리 상품 페이지 주소를 넣으면 후기를 수집(기본 300개)하고, Pandas로
긍정 · 부정 · 중립을 분석해 matplotlib 파이 차트로 보여준다.

컬리 상품 페이지는 자바스크립트로 후기를 그리기 때문에 HTML에는 후기가 없다.
그래서 페이지가 내부적으로 호출하는 후기 JSON API(api.kurly.com/product-review)를
커서(after) 방식으로 넘겨가며 가져온다. 컬리 후기에는 별점이 없으므로
감성은 한국어 감성 사전(긍정/부정 표현)으로 점수를 매겨 판정한다.

사용:
    python kurly_review/kurly_review_analyzer.py
"""
import os
import re
import sys
import time

import matplotlib
import pandas as pd
import requests
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False

DEFAULT_URL = "https://www.kurly.com/goods/1000572062?collectionCode=2611-blackweek-home-01"
REVIEWS_API = "https://api.kurly.com/product-review/v4/contents-products/{}/reviews"
COUNT_API = "https://api.kurly.com/product-review/v1/contents-products/{}/count"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.kurly.com/",
}
PAGE_SIZE = 50        # 한 번에 받는 후기 수
REQUEST_DELAY = 0.3   # 서버 부담을 줄이려고 요청 사이에 쉬는 시간(초)
SORT_TYPES = {"추천순": "RECOMMEND", "최신순": "RECENTLY"}

# ---------------------------------------------------------------- 감성 사전
# 위에서부터 차례로 찾고, 찾은 부분은 지워서 아래 단계에서 다시 세지 않는다.
# (예: "안 좋아요"를 부정으로 센 뒤 "좋"이 긍정으로 또 잡히지 않게)
# 정규식 → 화면에 보일 키워드
NEGATED_POSITIVE = {   # 긍정 단어가 들어있지만 부정인 표현
    r"안\s*좋": "안 좋음", r"좋지\s*(않|않았|않네|못)": "좋지 않음",
    r"맛\s*없": "맛없음", r"맛있지\s*(않|않았|는\s*않)": "맛있지 않음",
    r"별로": "별로", r"그닥|그다지": "그닥", r"글쎄": "글쎄",
    r"만족\s*(못|스럽지\s*않)|불만": "불만족", r"추천\s*(안|하지\s*않|은\s*안|못)": "비추천",
    r"재구매\s*(안|는\s*안|하지\s*않|의사\s*없|없)": "재구매 안 함",
    r"다시는|두\s*번\s*다시": "다시는 안 삼",
    r"(스타일|스탈)\s*(은|이)?\s*(아니|아닌|아님)|입맛\s*(에|엔|에는)?\s*안\s*맞": "입맛에 안 맞음",
}
NEGATED_NEGATIVE = {   # 부정 단어가 들어있지만 긍정인 표현
    r"안\s*짜": "안 짬", r"짜지\s*않": "안 짬", r"안\s*느끼|느끼하지\s*않": "안 느끼함",
    r"나쁘지\s*않": "나쁘지 않음", r"실패\s*(없|없는|없어)": "실패 없음",
    r"후회\W*(가|는|도)?\W*(없|안)": "후회 없음", r"부족함\s*(없|이\s*없)|부족하지\s*않": "부족함 없음",
    r"질기지\s*않|안\s*질기": "안 질김",
    r"비리지\s*않|안\s*비리|(잡내|냄새)\s*(도|가|는)?\s*(없|안)": "잡내 없음",
    r"아쉬운\s*(점|게)\s*없|아쉬움\s*없": "아쉬움 없음", r"비싸지\s*않|안\s*비싸": "안 비쌈",
    r"달지\s*않|안\s*달": "안 달음",
}
POSITIVE = {
    r"맛있|맛\s*(은|도)\s*있|맛나|맛이\s*좋|존맛|꿀맛|JMT": "맛있음", r"좋아|좋네|좋습|좋음|좋았|좋고|좋은|좋을": "좋음",
    r"최고|100점|💯|보증수표": "최고", r"만족": "만족", r"추천": "추천", r"괜찮": "괜찮음",
    r"재구매|또\s*(사|구매|주문|시켜)|번째|자주\s*(사|주문|구매|시키)|여러\s*번|(주문|구매)\s*중": "재구매",
    r"부드럽|부들부들|연하": "부드러움", r"든든": "든든함", r"간편|편하|편리|간단": "간편함",
    r"푸짐|넉넉|양\s*(이|도)?\s*많|배부르|충분": "푸짐함", r"적당": "적당함", r"딱\s*(이|좋|!)": "딱 좋음",
    r"밥도둑": "밥도둑", r"신선": "신선함", r"훌륭|굿|good": "훌륭함",
    r"감사|고마": "감사", r"강추|짱|대박|최애": "강추", r"필수템|쟁여|쟁이|비상용": "쟁여둠",
    r"저렴|가성비|착한\s*가격|싸게|할인|세일": "가성비", r"맛집|식당\s*맛|사\s*먹는\s*맛": "맛집 맛",
    r"깔끔|개운|시원": "깔끔함", r"달달|고소": "고소·달달", r"잘\s*먹|잘\s*먹었": "잘 먹음",
    r"믿고": "믿고 삼", r"기대\s*이상": "기대 이상",
}
NEGATIVE = {
    r"짜요|짜네|짜다|짜서|짰|짭니|너무\s*짜|많이\s*짜": "짬", r"달아요|너무\s*달|달았|달긴|좀\s*달": "너무 담",
    r"싱거": "싱거움", r"느끼": "느끼함", r"질기|질겨": "질김", r"비리|비린|잡내|냄새": "잡내",
    r"아쉽|아쉬[워운웠]": "아쉬움", r"실망": "실망", r"비싸|비쌈": "비쌈", r"번거로": "번거로움",
    r"양\s*(이|도)?\s*(좀\s*)?(적[어었네음다은]|작[아았네음다은])|부족": "양 부족",
    r"기름(지|져|짐|기가\s*많)|비계": "기름짐",
    r"최악": "최악", r"후회": "후회", r"녹아서\s*(왔|도착)|터져|파손|새서|샜|찢어": "배송·포장 불량",
    r"이상한\s*맛|맛이\s*이상|상한|쉰\s*맛": "맛 이상", r"그저\s*그|평범": "평범함",
    r"딱딱": "딱딱함", r"퍽퍽": "퍽퍽함", r"ㅠ|ㅜ": "ㅠㅠ",
}
COMPILED = [
    (re.compile(p, re.IGNORECASE), word, sign)
    for table, sign in ((NEGATED_POSITIVE, -1), (NEGATED_NEGATIVE, +1), (POSITIVE, +1), (NEGATIVE, -1))
    for p, word in table.items()
]
SENTIMENTS = ["긍정", "부정", "중립"]

# sp500_analysis.py · birth_analysis.py 와 같은 노랑 톤 UI 팔레트
COLORS = {
    "bg": "#FFF9EE",
    "surface": "#FFFFFF",
    "surface_alt": "#FFFBF1",
    "border": "#F3E3BF",
    "primary": "#FFC233",
    "primary_light": "#FFD84D",
    "primary_dark": "#FFA41B",
    "accent": "#E8890C",
    "selection": "#FFE59A",
    "text": "#3B2A12",
    "muted": "#8A6A3F",
    "disabled": "#C9B99A",
    "positive": "#2E9E5B",
    "negative": "#D6342C",
    "neutral": "#C9B99A",
}
SENTIMENT_COLORS = {"긍정": COLORS["positive"], "부정": COLORS["negative"], "중립": COLORS["neutral"]}

STYLESHEET = """
QMainWindow, QWidget#root {{ background: {bg}; }}
QWidget {{ color: {text}; font-family: "Malgun Gothic"; }}

QFrame#header {{
    border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {primary_light}, stop:0.55 {primary}, stop:1 {primary_dark});
}}
QLabel#logo {{
    background: {surface}; color: {primary_dark};
    border-radius: 24px; font-size: 16px; font-weight: 800;
}}
QLabel#appTitle {{ font-size: 22px; font-weight: 800; background: transparent; }}
QLabel#appSubtitle {{ font-size: 13px; color: #6B4A16; background: transparent; }}

QFrame[class="card"] {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
QLabel[class="fieldLabel"] {{ color: {muted}; font-weight: 600; background: transparent; }}
QLabel[class="statLabel"] {{ color: {muted}; font-size: 12px; background: transparent; }}
QLabel[class="statValue"] {{ font-size: 20px; font-weight: 800; background: transparent; }}
QLabel[class="statSub"] {{ color: {muted}; font-size: 11px; background: transparent; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {surface_alt}; border: 1px solid {border}; border-radius: 10px;
    padding: 8px 12px; font-size: 13px;
    selection-background-color: {selection}; selection-color: {text};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {primary}; background: {surface}; }}

QPushButton {{
    background: {surface}; border: 1px solid #F0D9A8; border-radius: 10px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; color: #5A4220;
}}
QPushButton:hover {{ background: #FFF6DC; border-color: {primary}; }}
QPushButton:pressed {{ background: #FFEDB8; }}
QPushButton:disabled {{ background: #FBF6EA; border-color: #F1E8D4; color: {disabled}; }}
QPushButton#primary {{
    border: none; font-weight: 800; padding: 9px 26px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_light}, stop:1 {primary});
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary}, stop:1 {primary_dark});
}}
QProgressBar {{
    background: {surface_alt}; border: 1px solid {border}; border-radius: 6px;
    height: 12px; text-align: center; font-size: 11px;
}}
QProgressBar::chunk {{ background: {primary}; border-radius: 5px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {muted}; padding: 8px 18px; margin-right: 4px;
    font-size: 14px; font-weight: 700; border: none; border-bottom: 3px solid transparent;
}}
QTabBar::tab:selected {{ color: {text}; border-bottom-color: {primary}; }}
QTabBar::tab:hover:!selected {{ color: {accent}; }}

QTableWidget {{
    background: {surface}; alternate-background-color: {surface_alt}; border: none;
    gridline-color: transparent; font-size: 13px; outline: 0;
    selection-background-color: {selection}; selection-color: {text};
}}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px solid #FBF0D8; }}
QHeaderView::section {{
    background: #FFF4D6; color: {muted}; font-weight: 700;
    padding: 8px 10px; border: none; border-bottom: 2px solid {primary};
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #F5D58A; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: #FFF3D6; color: {muted}; border-top: 1px solid {border}; padding: 4px 12px; }}
""".format(**COLORS)


# ---------------------------------------------------------------- 수집

def parse_goods_no(text):
    """상품 주소(또는 상품번호)에서 상품번호를 꺼낸다."""
    text = text.strip()
    match = re.search(r"/goods/(\d+)", text) or re.fullmatch(r"(\d+)", text)
    if not match:
        raise ValueError("컬리 상품 주소(…/goods/숫자) 또는 상품번호를 입력하세요.")
    return match.group(1)


def fetch_review_count(goods_no):
    resp = requests.get(COUNT_API.format(goods_no), headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]["count"]


def fetch_reviews(goods_no, limit, sort_type, progress=None):
    """후기 API를 커서(after)로 넘겨가며 limit개까지 모은다."""
    reviews, after = [], None
    while len(reviews) < limit:
        params = {"sortType": sort_type, "size": min(PAGE_SIZE, limit - len(reviews)), "onlyImage": "false"}
        if after:
            params["after"] = after
        resp = requests.get(REVIEWS_API.format(goods_no), headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        page = data.get("reviews") or []
        reviews.extend(page)
        if progress:
            progress(min(len(reviews), limit))
        after = (data.get("nextCursor") or {}).get("after")
        if not page or not after:
            break
        time.sleep(REQUEST_DELAY)
    return reviews[:limit]


def reviews_to_frame(reviews):
    rows = [{
        "후기번호": r["no"],
        "작성일": r.get("registeredAt"),
        "작성자": r.get("ownerName", ""),
        "등급": r.get("ownerGrade", ""),
        "구매상품": r.get("dealProductName", ""),
        "후기": (r.get("contents") or "").strip(),
        "사진": len(r.get("images") or []),
        "좋아요": r.get("likeCount", 0),
    } for r in reviews]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["작성일"] = pd.to_datetime(df["작성일"])
    return df


# ---------------------------------------------------------------- 분석

def score_text(text):
    """감성 사전으로 (점수, 긍정 키워드, 부정 키워드)를 구한다."""
    text = re.sub(r"\s+", " ", text)
    pos, neg = [], []
    for pattern, word, sign in COMPILED:
        hits = pattern.findall(text)
        if hits:
            (pos if sign > 0 else neg).extend([word] * len(hits))
            text = pattern.sub(" ", text)
    return len(pos) - len(neg), pos, neg


def analyze(df: pd.DataFrame) -> dict:
    df = df.drop_duplicates("후기번호").copy()
    df = df[df["후기"].str.len() > 0]
    scored = df["후기"].apply(score_text)
    df["점수"] = scored.str[0]
    df["긍정 키워드"] = scored.str[1]
    df["부정 키워드"] = scored.str[2]
    df["감성"] = pd.cut(df["점수"], [-float("inf"), -1, 0, float("inf")], labels=["부정", "중립", "긍정"])
    df["감성"] = df["감성"].astype(str)
    df["글자수"] = df["후기"].str.len()

    counts = df["감성"].value_counts().reindex(SENTIMENTS, fill_value=0)
    ratio = (counts / counts.sum() * 100).round(1)
    by_sentiment = df.groupby("감성").agg(
        후기수=("후기", "size"), 평균글자수=("글자수", "mean"),
        평균점수=("점수", "mean"), 사진후기=("사진", lambda s: (s > 0).sum()),
    ).reindex(SENTIMENTS).fillna(0).round(1)
    by_sentiment["비율(%)"] = ratio

    def top_keywords(col, n=10):
        words = df[col].explode().dropna()
        return words.value_counts().head(n).rename_axis("키워드").rename("등장 횟수")

    daily = (df.assign(날짜=df["작성일"].dt.date)
               .pivot_table(index="날짜", columns="감성", values="후기번호", aggfunc="count", fill_value=0)
               .reindex(columns=SENTIMENTS, fill_value=0))

    polar = counts["긍정"] + counts["부정"]
    return {
        "data": df,
        "counts": counts,
        "by_sentiment": by_sentiment,
        "pos_keywords": top_keywords("긍정 키워드"),
        "neg_keywords": top_keywords("부정 키워드"),
        "daily": daily,
        "summary": {
            "total": len(df),
            "pos_share": counts["긍정"] / polar * 100 if polar else 0,
            "period": (df["작성일"].min(), df["작성일"].max()),
            "avg_len": df["글자수"].mean(),
        },
    }


# ---------------------------------------------------------------- 그래프

def draw_pie(fig, result, include_neutral):
    fig.clear()
    counts = result["counts"]
    if not include_neutral:
        counts = counts.drop("중립")
    counts = counts[counts > 0]
    ax = fig.add_subplot(111)
    if counts.empty:
        ax.text(0.5, 0.5, "분석할 후기가 없습니다", ha="center", va="center")
        ax.axis("off")
        return
    wedges, _, autotexts = ax.pie(
        counts.values, labels=None, colors=[SENTIMENT_COLORS[k] for k in counts.index],
        startangle=90, counterclock=False, explode=[0.03] * len(counts),
        wedgeprops={"edgecolor": COLORS["surface"], "linewidth": 2, "width": 0.55},
        autopct=lambda p: f"{p:.1f}%\n({round(p * counts.sum() / 100):,}개)" if p >= 5 else "",
        pctdistance=0.72, textprops={"fontsize": 11, "color": "white", "weight": "bold"},
    )
    ax.text(0, 0.06, f"{counts.sum():,}", ha="center", va="center", fontsize=22, weight="bold",
            color=COLORS["text"])
    ax.text(0, -0.14, "개 후기", ha="center", va="center", fontsize=11, color=COLORS["muted"])
    ax.legend(wedges, [f"{k}  {v:,}개" for k, v in counts.items()], loc="center left",
              bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=11)
    scope = "긍정 · 부정 · 중립" if include_neutral else "긍정 · 부정 (중립 제외)"
    ax.set_title(f"컬리 후기 감성 분석 — {scope}", fontsize=14, weight="bold", color=COLORS["text"])
    ax.axis("equal")


def draw_keywords(fig, result):
    fig.clear()
    axes = fig.subplots(1, 2)
    for ax, key, title, color in (
        (axes[0], "pos_keywords", "긍정 키워드 TOP 10", COLORS["positive"]),
        (axes[1], "neg_keywords", "부정 키워드 TOP 10", COLORS["negative"]),
    ):
        s = result[key].iloc[::-1]
        ax.set_title(title, fontsize=12, weight="bold", color=COLORS["text"], loc="left")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.tick_params(colors=COLORS["muted"])
        if s.empty:
            ax.text(0.5, 0.5, "해당 키워드 없음", ha="center", va="center", transform=ax.transAxes)
            continue
        bars = ax.barh(s.index, s.values, color=color, height=0.6)
        ax.bar_label(bars, padding=3, fontsize=9, color=COLORS["text"])
        ax.margins(x=0.15)


# ---------------------------------------------------------------- 위젯 도우미

def make_card(shadow=False):
    card = QFrame()
    card.setProperty("class", "card")
    if shadow:
        effect = QGraphicsDropShadowEffect(card)
        effect.setBlurRadius(28)
        effect.setOffset(0, 6)
        effect.setColor(QColor(214, 150, 30, 38))
        card.setGraphicsEffect(effect)
    return card


def make_label(text, css_class):
    label = QLabel(text)
    label.setProperty("class", css_class)
    return label


def make_table():
    table = QTableWidget()
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


def fill_table(table, frame, stretch_col=None):
    """DataFrame을 표에 채운다. '감성' 열은 색으로 구분한다."""
    table.clear()
    table.setRowCount(len(frame))
    table.setColumnCount(len(frame.columns))
    table.setHorizontalHeaderLabels([str(c) for c in frame.columns])
    for r, row in enumerate(frame.itertuples(index=False)):
        for c, (col, value) in enumerate(zip(frame.columns, row)):
            if isinstance(value, float):
                text = f"{value:,.1f}"
            elif isinstance(value, list):
                text = ", ".join(dict.fromkeys(value))   # 같은 키워드는 한 번만
            elif isinstance(value, pd.Timestamp):
                text = value.strftime("%Y-%m-%d %H:%M")
            else:
                text = str(value).replace("\n", " ")
            item = QTableWidgetItem(text)
            if col == "후기":
                item.setToolTip(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            elif isinstance(value, (int, float)):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == "감성" and value in SENTIMENT_COLORS:
                item.setForeground(QColor(SENTIMENT_COLORS[value]))
            table.setItem(r, c, item)
    if stretch_col is not None:
        table.setWordWrap(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(list(frame.columns).index(stretch_col), QHeaderView.ResizeMode.Stretch)
        for c, col in enumerate(frame.columns):
            if col.endswith("키워드"):   # 키워드가 길면 후기 칸이 좁아지므로 폭을 고정 (툴팁으로 전체 확인)
                header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(c, 200)
                for r in range(table.rowCount()):
                    table.item(r, c).setToolTip(table.item(r, c).text())


class ChartPanel(QWidget):
    """matplotlib 캔버스 + 확대/이동 툴바."""

    def __init__(self, figsize):
        super().__init__()
        self.figure = Figure(figsize=figsize, facecolor=COLORS["surface"], layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas, 1)


class CrawlWorker(QThread):
    """후기 수집은 시간이 걸리므로 UI가 멈추지 않게 별도 스레드에서 한다."""
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(object, int)
    failed = pyqtSignal(str)

    def __init__(self, goods_no, limit, sort_type):
        super().__init__()
        self.goods_no, self.limit, self.sort_type = goods_no, limit, sort_type

    def run(self):
        try:
            total = fetch_review_count(self.goods_no)
            reviews = fetch_reviews(self.goods_no, self.limit, self.sort_type, self.progress.emit)
            self.finished_ok.emit(reviews_to_frame(reviews), total)
        except requests.RequestException as e:
            self.failed.emit(f"네트워크 오류: {e}")
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- 메인 창

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("컬리 후기 감성 분석기")
        self.resize(1320, 900)
        self.setMinimumSize(1050, 720)
        self.result = None
        self.worker = None

        root = QVBoxLayout()
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(16)
        root.addWidget(self.build_header())
        root.addWidget(self.build_control_card())
        root.addWidget(self.build_summary_card())
        root.addWidget(self.build_tabs_card(), 1)

        central = QWidget()
        central.setObjectName("root")
        central.setLayout(root)
        self.setCentralWidget(central)
        self.statusBar().showMessage("컬리 상품 주소를 넣고 [후기 수집 · 분석]을 누르세요.")

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(90)

        logo = QLabel("후기")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("컬리 후기 감성 분석기")
        title.setObjectName("appTitle")
        subtitle = QLabel("마켓컬리 상품 후기를 수집하고 Pandas로 긍정 · 부정 의견을 분석해 파이 차트로 보여줍니다")
        subtitle.setObjectName("appSubtitle")
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addStretch()
        titles.addWidget(title)
        titles.addWidget(subtitle)
        titles.addStretch()

        layout = QHBoxLayout(header)
        layout.setContentsMargins(26, 0, 26, 0)
        layout.setSpacing(16)
        layout.addWidget(logo)
        layout.addLayout(titles)
        layout.addStretch()
        return header

    def build_control_card(self):
        self.url_edit = QLineEdit(DEFAULT_URL)
        self.url_edit.setPlaceholderText("https://www.kurly.com/goods/상품번호")
        self.url_edit.returnPressed.connect(self.start_crawl)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(10, 2000)
        self.count_spin.setSingleStep(50)
        self.count_spin.setValue(300)
        self.count_spin.setSuffix(" 개")
        self.count_spin.setFixedWidth(120)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_TYPES)
        self.sort_combo.setFixedWidth(110)
        self.neutral_combo = QComboBox()
        self.neutral_combo.addItems(["중립 포함", "중립 제외"])
        self.neutral_combo.setFixedWidth(120)
        self.neutral_combo.currentIndexChanged.connect(self.redraw_charts)

        self.run_btn = QPushButton("후기 수집 · 분석")
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self.start_crawl)
        self.save_img_btn = QPushButton("그래프 저장")
        self.save_img_btn.setToolTip("지금 보고 있는 탭의 그래프를 PNG로 저장합니다")
        self.save_img_btn.clicked.connect(self.save_image)
        self.save_xlsx_btn = QPushButton("분석 결과 저장")
        self.save_xlsx_btn.setToolTip("후기 원문 · 감성 판정 · 분석 표를 엑셀 파일(시트별)로 저장합니다")
        self.save_xlsx_btn.clicked.connect(self.save_xlsx)
        for btn in (self.run_btn, self.save_img_btn, self.save_xlsx_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_img_btn.setEnabled(False)
        self.save_xlsx_btn.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        card = make_card(shadow=True)
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 14, 20, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(make_label("상품 주소", "fieldLabel"), 0, 0)
        grid.addWidget(self.url_edit, 0, 1, 1, 7)

        grid.addWidget(make_label("수집 개수", "fieldLabel"), 1, 0)
        grid.addWidget(self.count_spin, 1, 1)
        grid.addWidget(make_label("정렬", "fieldLabel"), 1, 2)
        grid.addWidget(self.sort_combo, 1, 3)
        grid.addWidget(make_label("차트", "fieldLabel"), 1, 4)
        grid.addWidget(self.neutral_combo, 1, 5)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.progress, 1)
        buttons.addWidget(self.run_btn)
        buttons.addWidget(self.save_img_btn)
        buttons.addWidget(self.save_xlsx_btn)
        grid.addLayout(buttons, 1, 6, 1, 2)
        grid.setColumnStretch(6, 1)
        return card

    def build_summary_card(self):
        tiles = [
            ("total", "분석한 후기"), ("pos", "긍정"), ("neg", "부정"),
            ("neu", "중립"), ("share", "긍정 비율 (중립 제외)"), ("period", "후기 기간"),
        ]
        self.stat_values, self.stat_subs = {}, {}
        card = make_card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(22, 14, 22, 14)
        for i, (key, title) in enumerate(tiles):
            if i:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setStyleSheet(f"background: {COLORS['border']};")
                layout.addWidget(divider)
            box = QVBoxLayout()
            box.setSpacing(2)
            value, sub = make_label("—", "statValue"), make_label("", "statSub")
            box.addWidget(make_label(title, "statLabel"))
            box.addWidget(value)
            box.addWidget(sub)
            self.stat_values[key], self.stat_subs[key] = value, sub
            layout.addLayout(box, 1)
        return card

    def build_tabs_card(self):
        self.pie_panel = ChartPanel((10, 6))
        self.keyword_panel = ChartPanel((12, 6))
        self.review_table = make_table()
        self.stats_table = make_table()
        self.daily_table = make_table()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.pie_panel, "감성 파이 차트")
        self.tabs.addTab(self.keyword_panel, "키워드 TOP 10")
        self.tabs.addTab(self.review_table, "후기 목록")
        self.tabs.addTab(self.stats_table, "감성별 통계")
        self.tabs.addTab(self.daily_table, "날짜별 후기")
        self.tabs.currentChanged.connect(self.update_buttons)

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.addWidget(self.tabs)
        return card

    # ------------------------------------------------------------ 동작

    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            goods_no = parse_goods_no(self.url_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, "주소 확인", str(e))
            return
        limit = self.count_spin.value()
        self.progress.setRange(0, limit)
        self.progress.setValue(0)
        self.progress.setFormat(f"%v / {limit}개")
        self.progress.setVisible(True)
        self.run_btn.setEnabled(False)
        self.statusBar().showMessage(f"상품 {goods_no}의 후기를 수집하는 중…")

        self.worker = CrawlWorker(goods_no, limit, SORT_TYPES[self.sort_combo.currentText()])
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished_ok.connect(self.on_crawled)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_failed(self, message):
        self.progress.setVisible(False)
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage("수집 실패")
        QMessageBox.critical(self, "수집 실패", message)

    def on_crawled(self, df, total):
        self.progress.setVisible(False)
        self.run_btn.setEnabled(True)
        if df.empty:
            self.statusBar().showMessage("수집된 후기가 없습니다.")
            QMessageBox.information(self, "후기 없음", "이 상품에는 후기가 없습니다.")
            return
        self.result = analyze(df)
        self.show_result()
        self.statusBar().showMessage(f"분석 완료: 전체 후기 {total:,}개 중 {self.result['summary']['total']:,}개 수집 · 분석")
        self.update_buttons()

    def show_result(self):
        res, s, counts = self.result, self.result["summary"], self.result["counts"]

        def set_tile(key, text, color=None, sub=""):
            self.stat_values[key].setText(text)
            self.stat_values[key].setStyleSheet(f"color: {color};" if color else "")
            self.stat_subs[key].setText(sub)

        total = s["total"]
        set_tile("total", f"{total:,}개", sub=f"평균 {s['avg_len']:.0f}자")
        for key, name in (("pos", "긍정"), ("neg", "부정"), ("neu", "중립")):
            set_tile(key, f"{counts[name]:,}개", SENTIMENT_COLORS[name], f"{counts[name] / total:.1%}")
        share = s["pos_share"]
        set_tile("share", f"{share:.1f}%", COLORS["positive"] if share >= 50 else COLORS["negative"],
                 "긍정 / (긍정 + 부정)")
        first, last = s["period"]
        set_tile("period", f"{(last - first).days + 1}일", sub=f"{first:%Y-%m-%d} ~ {last:%Y-%m-%d}")

        self.redraw_charts()

        cols = ["작성일", "작성자", "감성", "점수", "긍정 키워드", "부정 키워드", "후기"]
        fill_table(self.review_table, res["data"][cols], stretch_col="후기")
        fill_table(self.stats_table, res["by_sentiment"].rename_axis("감성").reset_index())
        daily = res["daily"].sort_index(ascending=False).reset_index()
        daily["날짜"] = daily["날짜"].astype(str)
        fill_table(self.daily_table, daily)

    def redraw_charts(self):
        if self.result is None:
            return
        draw_pie(self.pie_panel.figure, self.result, self.neutral_combo.currentIndex() == 0)
        self.pie_panel.canvas.draw_idle()
        draw_keywords(self.keyword_panel.figure, self.result)
        self.keyword_panel.canvas.draw_idle()

    def update_buttons(self):
        has_result = self.result is not None
        self.save_xlsx_btn.setEnabled(has_result)
        self.save_img_btn.setEnabled(has_result and self.tabs.currentWidget() in (self.pie_panel, self.keyword_panel))

    def save_image(self):
        panel = self.tabs.currentWidget()
        default = "kurly_review_pie.png" if panel is self.pie_panel else "kurly_review_keywords.png"
        path, _ = QFileDialog.getSaveFileName(self, "그래프 저장", default, "PNG 이미지 (*.png)")
        if path:
            panel.figure.savefig(path, dpi=150, facecolor=COLORS["surface"])
            self.statusBar().showMessage(f"저장했습니다: {path}")

    def save_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "분석 결과 저장", "kurly_review_analysis.xlsx", "엑셀 파일 (*.xlsx)")
        if not path:
            return
        res = self.result
        data = res["data"].copy()
        for col in ("긍정 키워드", "부정 키워드"):
            data[col] = data[col].str.join(", ")
        try:
            with pd.ExcelWriter(path) as xw:
                data.to_excel(xw, sheet_name="후기", index=False)
                res["by_sentiment"].to_excel(xw, sheet_name="감성별통계")
                res["pos_keywords"].to_excel(xw, sheet_name="긍정키워드")
                res["neg_keywords"].to_excel(xw, sheet_name="부정키워드")
                res["daily"].to_excel(xw, sheet_name="날짜별")
        except PermissionError:
            QMessageBox.warning(self, "저장 실패", "파일이 다른 프로그램(엑셀 등)에서 열려 있는지 확인하세요.")
            return
        self.statusBar().showMessage(f"저장했습니다: {path}")


def resource_path(name):
    """PyInstaller 실행파일에서는 임시 압축해제 폴더(_MEIPASS), 평소에는 프로젝트 루트에서 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, name)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
