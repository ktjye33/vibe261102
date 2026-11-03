"""S&P 500 과거 데이터 분석기 (PyQt6 GUI).

CSV를 불러와 데이터 클렌징 → Pandas 다각도 분석 → 종가 라인그래프를 보여준다.
"""
import sys
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDateEdit, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False

CSV_NAME = "S&P 500 과거 데이터.csv"


def find_default_csv():
    """기본 CSV 위치: 실행파일(또는 스크립트) 옆 → exe에 묶인 사본 → 수업 자료 폴더 순으로 찾는다."""
    app_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
    candidates = [
        app_dir / CSV_NAME,
        Path(getattr(sys, "_MEIPASS", app_dir)) / CSV_NAME,
        Path(r"C:\이지예\외근\교육자료\생산성본부_바이브코딩수업\DataSet") / CSV_NAME,
    ]
    return str(next((p for p in candidates if p.exists()), candidates[0]))


DEFAULT_CSV = find_default_csv()
DEFAULT_START = QDate(2000, 1, 1)
DEFAULT_END = QDate(2019, 12, 31)

# kospi200_crawler.py 와 같은 노랑 톤 팔레트
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
    "rise": "#D6342C",  # 상승은 빨강
    "fall": "#2F6FDB",  # 하락은 파랑
    "line": "#1F4E79",
}

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
    border-radius: 24px; font-size: 18px; font-weight: 800;
}}
QLabel#appTitle {{ font-size: 22px; font-weight: 800; background: transparent; }}
QLabel#appSubtitle {{ font-size: 13px; color: #6B4A16; background: transparent; }}

QFrame[class="card"] {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
QLabel[class="fieldLabel"] {{ color: {muted}; font-weight: 600; background: transparent; }}
QLabel[class="statLabel"] {{ color: {muted}; font-size: 12px; background: transparent; }}
QLabel[class="statValue"] {{ font-size: 20px; font-weight: 800; background: transparent; }}
QLabel[class="statSub"] {{ color: {muted}; font-size: 11px; background: transparent; }}

QLineEdit, QDateEdit {{
    background: {surface_alt}; border: 1px solid {border}; border-radius: 10px;
    padding: 8px 12px; font-size: 13px;
    selection-background-color: {selection}; selection-color: {text};
}}
QLineEdit:focus, QDateEdit:focus {{ border-color: {primary}; background: {surface}; }}
QDateEdit::drop-down {{ border: none; width: 22px; }}

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
QPlainTextEdit {{
    background: {surface_alt}; border: none; border-radius: 10px; padding: 12px;
    font-family: Consolas, "Malgun Gothic"; font-size: 13px;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #F5D58A; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: #FFF3D6; color: {muted}; border-top: 1px solid {border}; padding: 4px 12px; }}
""".format(**COLORS)


# ---------------------------------------------------------------- 데이터 클렌징

def load_and_clean(path):
    """CSV를 읽어 정제한 DataFrame과 클렌징 로그(문자열 리스트)를 돌려준다."""
    log = []
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    log.append(f"원본: {raw.shape[0]:,}행 x {raw.shape[1]}열")

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "Change",
    })
    missing = {"Date", "Close", "Open", "High", "Low"} - set(df.columns)
    if missing:
        raise ValueError(f"필요한 컬럼이 없습니다: {', '.join(sorted(missing))}")

    # 날짜: "2019- 11- 14" 처럼 공백이 섞인 문자열 → datetime
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", ""), format="%Y-%m-%d", errors="coerce")
    log.append("날짜: 공백 제거 후 날짜형으로 변환")

    # 가격: "3,096.60" → 3096.6
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
    log.append("가격(종가·시가·고가·저가): 천 단위 쉼표 제거 후 숫자로 변환")

    # 변동률: "-0.20%" → -0.20
    if "Change" in df.columns:
        df["Change"] = pd.to_numeric(df["Change"].str.replace("%", ""), errors="coerce")
        log.append("변동 %: % 기호 제거 후 숫자로 변환")

    # 거래량: 전부 비어 있으면 분석에 쓸 수 없으므로 제거
    if "Volume" in df.columns and df["Volume"].isna().all():
        df = df.drop(columns="Volume")
        log.append("거래량: 전부 비어 있어 컬럼 제거")

    # 결측 / 중복 / 0 이하 값 제거
    before = len(df)
    df = df.dropna(subset=["Date", "Close", "Open", "High", "Low"])
    df = df.drop_duplicates(subset="Date")
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    log.append(f"결측·중복·비정상 행 {before - len(df)}개 제거")

    # 고가/저가 논리 오류 보정 (예: 시가 > 고가) → 종가는 살리고 고가·저가를 OHLC 범위로 맞춤
    ohlc = df[["Open", "High", "Low", "Close"]]
    bad = (df["High"] < ohlc.max(axis=1)) | (df["Low"] > ohlc.min(axis=1))
    for d in df.loc[bad, "Date"]:
        log.append(f"{d:%Y-%m-%d}: 고가/저가 논리 오류 보정")
    df["High"], df["Low"] = ohlc.max(axis=1), ohlc.min(axis=1)

    # 최신순 → 과거순 정렬, 날짜 인덱스
    df = df.sort_values("Date").set_index("Date")
    log.append(f"정제 후: {len(df):,}행, 기간 {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}")
    return df, log


# ---------------------------------------------------------------- 다각도 분석

def analyze(df):
    """선택 기간의 데이터로 지표와 집계표를 계산한다."""
    df = df.copy()
    df["Return"] = df["Close"].pct_change() * 100                       # 일간 수익률(%)
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df["Vol20"] = df["Return"].rolling(20).std() * np.sqrt(252)         # 20일 연환산 변동성(%)
    df["Drawdown"] = (df["Close"] / df["Close"].cummax() - 1) * 100     # 고점 대비 낙폭(%)

    yearly = df.groupby(df.index.year).agg(
        시작=("Close", "first"), 종료=("Close", "last"),
        최고=("High", "max"), 최저=("Low", "min"),
        변동성=("Return", lambda r: r.std() * np.sqrt(252)),
    )
    yearly["연수익률%"] = (yearly["종료"] / yearly["시작"] - 1) * 100
    yearly.index.name = "연도"

    monthly_ret = df["Close"].resample("ME").last().pct_change() * 100
    season = monthly_ret.groupby(monthly_ret.index.month).agg(["mean", "median", lambda s: (s > 0).mean() * 100])
    season.columns = ["평균%", "중앙값%", "상승확률%"]
    season.index = [f"{m}월" for m in season.index]
    season.index.name = "월"

    dow_names = ["월", "화", "수", "목", "금"]
    dow = df.groupby(df.index.dayofweek)["Return"].agg(["mean", "std", "count"])
    dow.columns = ["평균%", "표준편차", "거래일수"]
    dow.index = [dow_names[i] + "요일" for i in dow.index]
    dow.index.name = "요일"

    extremes = pd.concat([
        df["Return"].nlargest(10).rename("수익률%").to_frame().assign(구분="상승"),
        df["Return"].nsmallest(10).rename("수익률%").to_frame().assign(구분="하락"),
    ])
    extremes.index = extremes.index.strftime("%Y-%m-%d")
    extremes.index.name = "날짜"
    extremes = extremes[["구분", "수익률%"]]

    mdd_date = df["Drawdown"].idxmin()
    peak_date = df.loc[:mdd_date, "Close"].idxmax()
    years = max((df.index[-1] - df.index[0]).days / 365.25, 1 / 365.25)
    total = df["Close"].iloc[-1] / df["Close"].iloc[0] - 1
    summary = {
        "total": total * 100,
        "cagr": ((1 + total) ** (1 / years) - 1) * 100,
        "vol": df["Return"].std() * np.sqrt(252),
        "mdd": df["Drawdown"].min(),
        "mdd_range": f"{peak_date:%Y-%m-%d} → {mdd_date:%Y-%m-%d}",
        "up_ratio": (df["Return"] > 0).mean() * 100,
        "days": len(df),
        "period": f"{df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}",
    }
    stats = df[["Close", "Return"]].describe().rename(columns={"Close": "종가", "Return": "일간수익률%"})
    stats.index.name = "통계"
    return {"df": df, "yearly": yearly, "season": season, "dow": dow,
            "extremes": extremes, "summary": summary, "stats": stats}


# ---------------------------------------------------------------- 차트

def style_axes(ax):
    ax.set_facecolor(COLORS["surface"])
    ax.grid(alpha=0.35, color=COLORS["border"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLORS["disabled"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9)


def draw_close_chart(fig, df):
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)
    ax.plot(df.index, df["Close"], color=COLORS["line"], linewidth=1.2, label="종가")
    ax.plot(df.index, df["MA200"], color=COLORS["accent"], linewidth=1, alpha=0.85, label="200일 이동평균")

    # 최고점 / 최저점 표시
    for idx, txt, offset, ha, va in [(df["Close"].idxmax(), "최고", (0, 8), "center", "bottom"),
                                     (df["Close"].idxmin(), "최저", (8, -6), "left", "top")]:
        val = df.loc[idx, "Close"]
        ax.scatter(idx, val, color=COLORS["rise"], zorder=3, s=25)
        ax.annotate(f"{txt} {val:,.1f}\n({idx:%Y-%m-%d})", (idx, val), textcoords="offset points",
                    xytext=offset, ha=ha, va=va, fontsize=9)

    ax.set_title(f"S&P 500 종가 추이 ({df.index.min():%Y.%m} ~ {df.index.max():%Y.%m})",
                 fontsize=14, weight="bold", color=COLORS["text"])
    ax.set_ylabel("종가 (포인트)", color=COLORS["muted"])
    ax.set_ylim(0, df["Close"].max() * 1.08)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=24))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.legend(loc="upper left", frameon=False)


def draw_dashboard(fig, res):
    df, yearly = res["df"], res["yearly"]
    fig.clear()
    axes = fig.subplots(2, 2)

    ax = axes[0, 0]
    colors = [COLORS["rise"] if v >= 0 else COLORS["fall"] for v in yearly["연수익률%"]]
    ax.bar(yearly.index, yearly["연수익률%"], color=colors)
    ax.axhline(0, color=COLORS["disabled"], lw=0.8)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title("연도별 수익률 (%)")

    ax = axes[0, 1]
    ax.fill_between(df.index, df["Drawdown"], 0, color=COLORS["fall"], alpha=0.35)
    ax.set_title("고점 대비 낙폭 (Drawdown, %)")

    ax = axes[1, 0]
    ax.plot(df.index, df["Vol20"], color=COLORS["accent"], lw=0.8)
    ax.set_title("20일 연환산 변동성 (%)")

    ax = axes[1, 1]
    ax.hist(df["Return"].dropna(), bins=100, color=COLORS["line"], alpha=0.85)
    ax.set_title("일간 수익률 분포 (%)")

    for a in axes.flat:
        style_axes(a)
        a.title.set_fontsize(11)
        a.title.set_color(COLORS["text"])


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


def fill_table(table, frame, signed=()):
    """DataFrame을 표에 채운다. 인덱스는 첫 열, signed 컬럼은 +빨강 / -파랑."""
    frame = frame.reset_index()
    table.clear()
    table.setRowCount(len(frame))
    table.setColumnCount(len(frame.columns))
    table.setHorizontalHeaderLabels([str(c) for c in frame.columns])
    for r, row in enumerate(frame.itertuples(index=False)):
        for c, (col, value) in enumerate(zip(frame.columns, row)):
            if isinstance(value, (int, np.integer)):
                text = f"{value:,}" if col != "연도" else str(value)
            elif isinstance(value, (float, np.floating)):
                text = f"{value:+,.2f}" if col in signed else f"{value:,.2f}"
            else:
                text = str(value)
            item = QTableWidgetItem(text)
            if isinstance(value, (int, float, np.number)) and c > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col in signed and isinstance(value, (float, np.floating)):
                item.setForeground(QColor(COLORS["rise"] if value >= 0 else COLORS["fall"]))
            table.setItem(r, c, item)


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


# ---------------------------------------------------------------- 메인 창

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S&P 500 분석기")
        self.resize(1320, 900)
        self.setMinimumSize(1050, 720)
        self.clean_df = None
        self.loaded_path = None
        self.result = None

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
        self.statusBar().showMessage("CSV 파일을 고르고 [분석 실행]을 누르세요.")

        if Path(DEFAULT_CSV).exists():
            self.run_analysis()

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(90)

        logo = QLabel("S&P")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("S&P 500 분석기")
        title.setObjectName("appTitle")
        subtitle = QLabel("과거 데이터를 정제하고 Pandas로 수익률 · 변동성 · 낙폭 · 계절성을 분석합니다")
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
        self.path_edit = QLineEdit(DEFAULT_CSV)
        self.path_edit.setPlaceholderText("S&P 500 과거 데이터 CSV 경로")
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self.browse)

        self.start_edit = QDateEdit(DEFAULT_START)
        self.end_edit = QDateEdit(DEFAULT_END)
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setFixedWidth(150)

        run_btn = QPushButton("분석 실행")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self.run_analysis)
        self.save_img_btn = QPushButton("그래프 저장")
        self.save_img_btn.setToolTip("지금 보고 있는 탭의 그래프를 PNG로 저장합니다")
        self.save_img_btn.clicked.connect(self.save_image)
        self.save_csv_btn = QPushButton("정제 데이터 저장")
        self.save_csv_btn.setToolTip("선택 기간의 정제된 데이터를 CSV로 저장합니다")
        self.save_csv_btn.clicked.connect(self.save_csv)
        for btn in (browse_btn, run_btn, self.save_img_btn, self.save_csv_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_img_btn.setEnabled(False)
        self.save_csv_btn.setEnabled(False)

        card = make_card(shadow=True)
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 14, 20, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(make_label("데이터 파일", "fieldLabel"), 0, 0)
        grid.addWidget(self.path_edit, 0, 1, 1, 5)
        grid.addWidget(browse_btn, 0, 6)

        grid.addWidget(make_label("분석 기간", "fieldLabel"), 1, 0)
        grid.addWidget(self.start_edit, 1, 1)
        grid.addWidget(make_label("~", "fieldLabel"), 1, 2)
        grid.addWidget(self.end_edit, 1, 3)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        buttons.addWidget(run_btn)
        buttons.addWidget(self.save_img_btn)
        buttons.addWidget(self.save_csv_btn)
        grid.addLayout(buttons, 1, 4, 1, 3)
        grid.setColumnStretch(4, 1)
        return card

    def build_summary_card(self):
        tiles = [
            ("total", "누적 수익률"), ("cagr", "연평균 수익률 (CAGR)"), ("vol", "연환산 변동성"),
            ("mdd", "최대 낙폭 (MDD)"), ("up_ratio", "상승일 비율"), ("days", "거래일 수"),
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
        self.close_panel = ChartPanel((12, 5))
        self.dash_panel = ChartPanel((12, 7))
        self.yearly_table = make_table()
        self.season_table = make_table()
        self.dow_table = make_table()
        self.extreme_table = make_table()
        self.stats_table = make_table()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.close_panel, "종가 추이")
        self.tabs.addTab(self.dash_panel, "다각도 분석")
        self.tabs.addTab(self.yearly_table, "연도별 성과")
        self.tabs.addTab(self.season_table, "월별 계절성")
        self.tabs.addTab(self.dow_table, "요일별")
        self.tabs.addTab(self.extreme_table, "급등락일")
        self.tabs.addTab(self.stats_table, "기술 통계")
        self.tabs.addTab(self.log_view, "클렌징 로그")
        self.tabs.currentChanged.connect(self.update_buttons)

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.addWidget(self.tabs)
        return card

    # ------------------------------------------------------------ 동작

    def browse(self):
        start_dir = Path(self.path_edit.text()).parent
        if getattr(sys, "frozen", False) and start_dir == Path(sys._MEIPASS):   # exe 내장 데이터면 exe 폴더에서 시작
            start_dir = Path(sys.executable).parent
        path, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", str(start_dir), "CSV 파일 (*.csv)")
        if path:
            self.path_edit.setText(path)
            self.clean_df = None   # 새 파일이면 다시 읽는다
            self.run_analysis()

    def run_analysis(self):
        start = pd.Timestamp(self.start_edit.date().toPyDate())
        end = pd.Timestamp(self.end_edit.date().toPyDate())
        if start > end:
            QMessageBox.warning(self, "기간 오류", "시작일이 종료일보다 늦습니다.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            path = self.path_edit.text().strip()
            if self.clean_df is None or self.loaded_path != path:
                self.clean_df, log = load_and_clean(path)
                self.loaded_path = path
                self.log_view.setPlainText("\n".join(f"• {line}" for line in log))
            data = self.clean_df.loc[start:end]
            if len(data) < 2:
                raise ValueError("선택한 기간에 데이터가 거의 없습니다. 기간을 넓혀 주세요.")
            self.result = analyze(data)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "분석 실패", f"{type(e).__name__}: {e}")
            return

        self.show_result()
        QApplication.restoreOverrideCursor()

        s = self.result["summary"]
        msg = f"분석 완료: {s['period']} ({s['days']:,}거래일)"
        if self.clean_df.index.max() < end:
            msg += f"  ·  데이터가 {self.clean_df.index.max():%Y-%m-%d}까지만 있어 그 이후는 표시되지 않습니다"
        self.statusBar().showMessage(msg)
        self.update_buttons()

    def show_result(self):
        res, s = self.result, self.result["summary"]

        def set_tile(key, text, color=None, sub=""):
            self.stat_values[key].setText(text)
            self.stat_values[key].setStyleSheet(f"color: {color};" if color else "")
            self.stat_subs[key].setText(sub)

        sign_color = lambda v: COLORS["rise"] if v >= 0 else COLORS["fall"]
        set_tile("total", f"{s['total']:+,.2f}%", sign_color(s["total"]))
        set_tile("cagr", f"{s['cagr']:+.2f}%", sign_color(s["cagr"]))
        set_tile("vol", f"{s['vol']:.2f}%")
        set_tile("mdd", f"{s['mdd']:.2f}%", COLORS["fall"], s["mdd_range"])
        set_tile("up_ratio", f"{s['up_ratio']:.1f}%")
        set_tile("days", f"{s['days']:,}일", sub=s["period"])

        draw_close_chart(self.close_panel.figure, res["df"])
        self.close_panel.canvas.draw_idle()
        draw_dashboard(self.dash_panel.figure, res)
        self.dash_panel.canvas.draw_idle()

        fill_table(self.yearly_table, res["yearly"], signed={"연수익률%"})
        fill_table(self.season_table, res["season"], signed={"평균%", "중앙값%"})
        fill_table(self.dow_table, res["dow"], signed={"평균%"})
        fill_table(self.extreme_table, res["extremes"], signed={"수익률%"})
        fill_table(self.stats_table, res["stats"])

    def update_buttons(self):
        has_result = self.result is not None
        self.save_csv_btn.setEnabled(has_result)
        self.save_img_btn.setEnabled(has_result and self.tabs.currentWidget() in (self.close_panel, self.dash_panel))

    def save_image(self):
        panel = self.tabs.currentWidget()
        default = "sp500_close.png" if panel is self.close_panel else "sp500_dashboard.png"
        path, _ = QFileDialog.getSaveFileName(self, "그래프 저장", default, "PNG 이미지 (*.png)")
        if path:
            panel.figure.savefig(path, dpi=150, facecolor=COLORS["surface"])
            self.statusBar().showMessage(f"저장했습니다: {path}")

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "정제 데이터 저장", "sp500_clean.csv", "CSV 파일 (*.csv)")
        if path:
            self.result["df"].to_csv(path, encoding="utf-8-sig", float_format="%.4f")
            self.statusBar().showMessage(f"저장했습니다: {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
