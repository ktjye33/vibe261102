"""대한민국 출생아수 분석기 (PyQt6 GUI).

KOSIS 「인구동향조사」 엑셀(통계표 INH_1B8000F_01, 1970~2025)을 불러와
데이터 클랜징 → Pandas 다각도 분석 → 출생아수 라인 그래프를 보여준다.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False

XLSX_NAME = "출생아수__합계출산율__자연증가_등_20260605082440.xlsx"


def find_default_xlsx():
    """기본 엑셀 위치: 실행파일(또는 스크립트) 옆 → exe에 묶인 사본 → 수업 자료 폴더 순으로 찾는다."""
    app_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
    candidates = [
        app_dir / XLSX_NAME,
        Path(getattr(sys, "_MEIPASS", app_dir)) / XLSX_NAME,
        Path(r"C:\이지예\외근\교육자료\생산성본부_바이브코딩수업\DataSet") / XLSX_NAME,
    ]
    return str(next((p for p in candidates if p.exists()), candidates[0]))


DEFAULT_XLSX = find_default_xlsx()

# 원본 항목명 → 분석용 영문 컬럼명
COL_MAP = {
    "출생아수(명)": "births",
    "자연증가건수(명)": "natural_increase",
    "조출생률(천명당)": "crude_birth_rate",
    "자연증가율(천명당)": "natural_increase_rate",
    "합계출산율(명)": "tfr",
    "출생성비(명)": "sex_ratio",
}
KOR = {v: k for k, v in COL_MAP.items()}

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

# sp500_analysis.py 와 같은 노랑 톤 UI 팔레트
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
    "rise": "#D6342C",  # 증가는 빨강
    "fall": "#2F6FDB",  # 감소는 파랑
    "line": "#2A78D6",  # 그래프 선
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
    border-radius: 24px; font-size: 16px; font-weight: 800;
}}
QLabel#appTitle {{ font-size: 22px; font-weight: 800; background: transparent; }}
QLabel#appSubtitle {{ font-size: 13px; color: #6B4A16; background: transparent; }}

QFrame[class="card"] {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
QLabel[class="fieldLabel"] {{ color: {muted}; font-weight: 600; background: transparent; }}
QLabel[class="statLabel"] {{ color: {muted}; font-size: 12px; background: transparent; }}
QLabel[class="statValue"] {{ font-size: 20px; font-weight: 800; background: transparent; }}
QLabel[class="statSub"] {{ color: {muted}; font-size: 11px; background: transparent; }}

QLineEdit, QSpinBox {{
    background: {surface_alt}; border: 1px solid {border}; border-radius: 10px;
    padding: 8px 12px; font-size: 13px;
    selection-background-color: {selection}; selection-color: {text};
}}
QLineEdit:focus, QSpinBox:focus {{ border-color: {primary}; background: {surface}; }}

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


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ---------------------------------------------------------------- 데이터 클랜징

def load_and_clean(src) -> pd.DataFrame:
    section("1. 데이터 클랜징")
    raw = pd.read_excel(src, sheet_name="데이터")
    print(f"원본 형태: {raw.shape} (행=지표, 열=연도 → wide format)")

    # (1) 지표명을 인덱스로, 연도 헤더를 문자열로 통일
    raw = raw.set_index("기본항목별")
    raw.columns = raw.columns.map(lambda c: str(c).strip())

    # (2) 잠정치 표기 처리: '2025 p)' → 2025, 잠정치 여부는 별도 컬럼으로 보존
    provisional = [c for c in raw.columns if "p)" in c]
    years = raw.columns.str.extract(r"(\d{4})")[0].astype(int)
    raw.columns = years
    print(f"잠정치(p) 연도: {provisional} → 연도 정수로 변환, is_provisional 플래그 추가")

    # (3) wide → long(tidy): 연도를 행으로 전치하고 컬럼명 영문화
    df = raw.T.rename(columns=COL_MAP)
    df.columns.name = None
    df.index.name = "year"

    # (4) 숫자형 변환: '-', '…', 공백, 천단위 콤마 등 비정상 값은 NaN 처리
    for c in df.columns:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace(",", "").str.strip()
                 .replace({"-": None, "…": None, "": None, "nan": None}),
            errors="coerce")
    df[["births", "natural_increase"]] = df[["births", "natural_increase"]].astype("Int64")

    # (5) 결측·중복·정렬 점검
    df = df[~df.index.duplicated(keep="last")].sort_index()
    print(f"결측치 수:\n{df.isna().sum().to_string()}")
    missing_years = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    print(f"누락 연도: {missing_years or '없음'}")

    # (6) 값 범위 유효성 검사 (논리적으로 불가능한 값 탐지)
    checks = {
        "출생아수 <= 0": df["births"] <= 0,
        "합계출산율 범위 밖(0~10)": ~df["tfr"].between(0, 10),
        "출생성비 범위 밖(90~130)": ~df["sex_ratio"].between(90, 130),
    }
    for name, mask in checks.items():
        print(f"이상치 검사 [{name}]: {int(mask.sum())}건")

    df["is_provisional"] = df.index.isin([int(p[:4]) for p in provisional])
    print(f"\n클랜징 후 형태: {df.shape}  (연도 {df.index.min()}~{df.index.max()})")
    print(df.head().to_string())
    return df


# ---------------------------------------------------------------- 다각도 분석

def analyze(df: pd.DataFrame) -> dict:
    out = {}

    section("2-1. 기술통계")
    desc = df.drop(columns="is_provisional").astype(float).describe().T
    desc.index = desc.index.map(KOR)
    print(desc.to_string())
    out["기술통계"] = desc

    section("2-2. 최댓값·최솟값 연도")
    b = df["births"].astype(float)
    print(f"출생아수 최대: {b.idxmax()}년 {b.max():,.0f}명")
    print(f"출생아수 최소: {b.idxmin()}년 {b.min():,.0f}명")
    print(f"합계출산율 최대: {df['tfr'].idxmax()}년 {df['tfr'].max():.2f}명")
    print(f"합계출산율 최소: {df['tfr'].idxmin()}년 {df['tfr'].min():.3f}명")
    print(f"{b.index[0]} → {b.index[-1]} 출생아수 변화: {b.iloc[-1] / b.iloc[0] - 1:+.1%} "
          f"({b.iloc[0]:,.0f} → {b.iloc[-1]:,.0f}명)")

    section("2-3. 전년 대비 증감 (출생아수)")
    yoy = pd.DataFrame({
        "출생아수": b,
        "전년대비_증감": b.diff().astype("Int64"),
        "전년대비_증감률(%)": b.pct_change() * 100,
    })
    print("감소폭 TOP 5:\n", yoy.nsmallest(5, "전년대비_증감률(%)").to_string())
    print("\n증가폭 TOP 5:\n", yoy.nlargest(5, "전년대비_증감률(%)").to_string())
    print("\n최근 10년:\n", yoy.tail(10).to_string())
    out["전년대비"] = yoy

    section("2-4. 연대별 평균")
    decade = (df.drop(columns="is_provisional").astype(float)
                .groupby((df.index // 10) * 10).mean())
    decade.index = [f"{d}년대" for d in decade.index]
    decade.columns = decade.columns.map(KOR)
    print(decade.to_string())
    out["연대별평균"] = decade

    section("2-5. 주요 이정표")
    for thr in (800_000, 600_000, 400_000, 300_000):
        below = b[b < thr]
        if not below.empty:
            print(f"출생아수 {thr // 10_000}만명 미만 최초: {below.index[0]}년")
    for thr, name in ((2.1, "2.1(인구대체수준)"), (1.3, "1.3(초저출산)"), (1.0, "1.0")):
        below = df[df["tfr"] < thr]
        if not below.empty:
            print(f"합계출산율 {name} 미만 최초: {below.index[0]}년")
    dead_cross = df[df["natural_increase"] < 0]
    if not dead_cross.empty:
        print(f"자연증가 마이너스(데드크로스) 최초: {dead_cross.index[0]}년, "
              f"이후 {len(dead_cross)}년 연속")
        print(f"자연감소 누적({dead_cross.index[0]}~): {dead_cross['natural_increase'].sum():,}명")

    section("2-6. 기간별 연평균 성장률(CAGR)")
    periods = [(1970, 1983), (1983, 2000), (2000, 2015), (2015, 2023), (2023, 2025)]
    cagr = pd.Series({f"{s}~{e}": (b[e] / b[s]) ** (1 / (e - s)) - 1
                      for s, e in periods if s in b.index and e in b.index},
                     name="출생아수 CAGR")
    print((cagr * 100).map("{:+.2f}%".format).to_string())
    out["CAGR"] = (cagr * 100).rename("연평균 성장률(%)").to_frame()

    section("2-7. 지표 간 상관관계")
    corr = df.drop(columns="is_provisional").astype(float).corr()
    corr.index = corr.columns = corr.columns.map(KOR)
    print(corr.round(3).to_string())
    out["상관관계"] = corr

    section("2-8. 출생성비 정상화 (정상범위 103~107)")
    abnormal = df[df["sex_ratio"] > 107]["sex_ratio"]
    if not abnormal.empty:
        print(f"정상범위 초과 연도 {len(abnormal)}개: "
              f"{abnormal.index.min()}~{abnormal.index.max()}년, 최고 "
              f"{abnormal.idxmax()}년 {abnormal.max():.1f}")
    print(f"2007년 이후 정상범위 유지 여부: {bool((df.loc[2007:, 'sex_ratio'] <= 107).all())}")

    section("2-9. 최근 추이")
    recent = df.index[-4:]
    print(yoy.loc[recent, ["출생아수", "전년대비_증감률(%)"]].to_string())
    print(df.loc[recent, ["tfr"]].rename(columns=KOR).to_string())
    if df["is_provisional"].any():
        print(f"※ {', '.join(map(str, df.index[df['is_provisional']]))}년은 잠정치(p)")

    # 상단 요약 카드용 값
    last = b.index[-1]
    out["summary"] = {
        "max": (b.idxmax(), b.max()),
        "min": (b.idxmin(), b.min()),
        "last": (last, b[last], yoy.loc[last, "전년대비_증감률(%)"], bool(df.loc[last, "is_provisional"])),
        "change": (b.index[0], last, b.iloc[-1] / b.iloc[0] - 1),
        "tfr": (last, df.loc[last, "tfr"], df["tfr"].idxmin(), df["tfr"].min()),
        "natural": (last, df.loc[last, "natural_increase"]),
    }
    return out


def run_pipeline(src):
    """클랜징 + 분석을 실행하고 (정제 데이터, 분석 결과, 텍스트 리포트)를 돌려준다."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        df = load_and_clean(src)
        result = analyze(df)
    return df, result, buf.getvalue().lstrip()


# ---------------------------------------------------------------- 차트

def style_axes(ax):
    ax.set_facecolor(COLORS["surface"])
    ax.grid(axis="y", color="#EFE6D2", linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(COLORS["disabled"])
    ax.tick_params(colors=COLORS["muted"], labelsize=9, length=0)


def year_step(start, end, max_ticks):
    """연도 눈금 간격: 1·2·5·10년 중 눈금 수가 max_ticks 이하가 되는 가장 촘촘한 값."""
    return next((st for st in (1, 2, 5, 10) if (end - start) / st <= max_ticks), 20)


def draw_births_chart(fig, df, start, end):
    """출생아수 라인 그래프. 확정치는 실선, 잠정치 구간은 점선."""
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)
    blue = COLORS["line"]

    s = df.loc[start:end, "births"].astype(float)
    is_prov = df.loc[s.index, "is_provisional"]
    final = s[~is_prov]
    ax.plot(final.index, final.values, color=blue, linewidth=2, marker="o", markersize=3.5)
    if is_prov.any():
        seg = s.loc[final.index[-1]:] if len(final) else s[is_prov]
        ax.plot(seg.index, seg.values, color=blue, linewidth=2, linestyle="--")
        ax.plot(s[is_prov].index, s[is_prov].values, "o", markersize=5,
                markerfacecolor=COLORS["surface"], markeredgecolor=blue, markeredgewidth=1.5)

    # 선택적 직접 라벨: 최대, 최소, 최근
    labels = {s.idxmax(): ("최대", 12), s.idxmin(): ("최소", -30), s.index[-1]: ("최근", 12)}
    for yr, (tag, dy) in labels.items():
        v = s[yr]
        suffix = " (잠정)" if df.loc[yr, "is_provisional"] else ""
        ax.annotate(f"{yr}년 {tag}\n{v / 10_000:,.1f}만명{suffix}", (yr, v),
                    xytext=(0, dy), textcoords="offset points",
                    ha="center", fontsize=9, color=COLORS["text"])

    ax.set_title(f"대한민국 연간 출생아수 추이 ({start}~{end})", fontsize=14, weight="bold",
                 color=COLORS["text"], loc="left", pad=12)
    ax.set_xlabel("연도", color=COLORS["muted"])
    ax.set_ylabel("출생아수 (만 명)", color=COLORS["muted"])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}"))
    ax.set_ylim(0, s.max() * 1.15)
    ax.set_xlim(start - 2, end + 2)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(year_step(start, end, 12)))
    fig.text(0.01, 0.005, "자료: KOSIS 「인구동향조사」 · 점선/빈 점은 잠정치",
             fontsize=8, color=COLORS["muted"])


def draw_dashboard(fig, df, start, end):
    """다른 지표를 2x2 소형 차트로 비교 (지표마다 단위가 달라 축을 분리)."""
    fig.clear()
    d = df.loc[start:end]
    axes = fig.subplots(2, 2)

    ax = axes[0, 0]
    ax.plot(d.index, d["tfr"], color=COLORS["line"], linewidth=2)
    ax.axhline(2.1, color=COLORS["disabled"], linestyle="--", linewidth=1)
    ax.text(d.index[-1], 2.15, "인구대체수준 2.1", ha="right", va="bottom", fontsize=8,
            color=COLORS["muted"])
    ax.set_title("합계출산율 (명)")

    ax = axes[0, 1]
    ni = d["natural_increase"].astype(float) / 10_000
    ax.bar(d.index, ni, width=0.8,
           color=[COLORS["rise"] if v >= 0 else COLORS["fall"] for v in ni])
    ax.axhline(0, color=COLORS["disabled"], linewidth=0.8)
    ax.set_title("자연증가건수 (만 명, 출생-사망)")

    ax = axes[1, 0]
    ax.plot(d.index, d["crude_birth_rate"], color=COLORS["line"], linewidth=2)
    ax.set_title("조출생률 (인구 천 명당)")

    ax = axes[1, 1]
    ax.axhspan(103, 107, color="#F3F7EC", zorder=0)
    ax.plot(d.index, d["sex_ratio"], color=COLORS["line"], linewidth=2)
    ax.text(d.index[0], 103.3, "정상범위 103~107", fontsize=8, color=COLORS["muted"])
    ax.set_title("출생성비 (여아 100명당 남아)")

    for a in axes.flat:
        style_axes(a)
        a.title.set_fontsize(11)
        a.title.set_color(COLORS["text"])
        a.title.set_horizontalalignment("left")
        a.title.set_position((0, 1))
        a.xaxis.set_major_locator(mticker.MultipleLocator(year_step(start, end, 6)))


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


def fill_table(table, frame, index_name="구분", signed=()):
    """DataFrame을 표에 채운다. 인덱스는 첫 열, signed 컬럼은 +빨강 / -파랑."""
    frame = frame.rename_axis(index_name).reset_index()
    table.clear()
    table.setRowCount(len(frame))
    table.setColumnCount(len(frame.columns))
    table.setHorizontalHeaderLabels([str(c) for c in frame.columns])
    for r, row in enumerate(frame.itertuples(index=False)):
        for c, (col, value) in enumerate(zip(frame.columns, row)):
            if value is pd.NA or (isinstance(value, float) and np.isnan(value)):
                text = "—"
            elif isinstance(value, (bool, np.bool_)):
                text = "잠정" if value else ""
            elif isinstance(value, (int, np.integer)):
                text = str(value) if col == "연도" else (f"{value:+,}" if col in signed else f"{value:,}")
            elif isinstance(value, (float, np.floating)):
                text = f"{value:+,.2f}" if col in signed else f"{value:,.3f}".rstrip("0").rstrip(".")
            else:
                text = str(value)
            item = QTableWidgetItem(text)
            numeric = isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_))
            if numeric and c > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col in signed and numeric and value is not pd.NA and not pd.isna(value):
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
        self.setWindowTitle("대한민국 출생아수 분석기")
        self.resize(1320, 900)
        self.setMinimumSize(1050, 720)
        self.clean_df = None
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
        self.statusBar().showMessage("엑셀 파일을 고르고 [분석 실행]을 누르세요.")

        if Path(DEFAULT_XLSX).exists():
            self.run_analysis()

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(90)

        logo = QLabel("출생")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("대한민국 출생아수 분석기")
        title.setObjectName("appTitle")
        subtitle = QLabel("KOSIS 인구동향조사 데이터를 정제하고 Pandas로 출생아수 · 합계출산율 · 자연증가 · 출생성비를 분석합니다")
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
        self.path_edit = QLineEdit(DEFAULT_XLSX)
        self.path_edit.setPlaceholderText("KOSIS 출생아수 엑셀(.xlsx) 경로")
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self.browse)

        self.start_spin, self.end_spin = QSpinBox(), QSpinBox()
        for spin, value in ((self.start_spin, 1970), (self.end_spin, 2025)):
            spin.setRange(1900, 2100)
            spin.setValue(value)
            spin.setSuffix(" 년")
            spin.setFixedWidth(120)
            spin.valueChanged.connect(self.redraw_charts)

        run_btn = QPushButton("분석 실행")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self.run_analysis)
        self.save_img_btn = QPushButton("그래프 저장")
        self.save_img_btn.setToolTip("지금 보고 있는 탭의 그래프를 PNG로 저장합니다")
        self.save_img_btn.clicked.connect(self.save_image)
        self.save_xlsx_btn = QPushButton("분석 결과 저장")
        self.save_xlsx_btn.setToolTip("정제 데이터와 분석 표를 엑셀 파일(시트별)로 저장합니다")
        self.save_xlsx_btn.clicked.connect(self.save_xlsx)
        for btn in (browse_btn, run_btn, self.save_img_btn, self.save_xlsx_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_img_btn.setEnabled(False)
        self.save_xlsx_btn.setEnabled(False)

        card = make_card(shadow=True)
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 14, 20, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(make_label("데이터 파일", "fieldLabel"), 0, 0)
        grid.addWidget(self.path_edit, 0, 1, 1, 5)
        grid.addWidget(browse_btn, 0, 6)

        grid.addWidget(make_label("그래프 기간", "fieldLabel"), 1, 0)
        grid.addWidget(self.start_spin, 1, 1)
        grid.addWidget(make_label("~", "fieldLabel"), 1, 2)
        grid.addWidget(self.end_spin, 1, 3)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        buttons.addWidget(run_btn)
        buttons.addWidget(self.save_img_btn)
        buttons.addWidget(self.save_xlsx_btn)
        grid.addLayout(buttons, 1, 4, 1, 3)
        grid.setColumnStretch(4, 1)
        return card

    def build_summary_card(self):
        tiles = [
            ("max", "최대 출생아수"), ("min", "최소 출생아수"), ("last", "최근 출생아수"),
            ("change", "전체 기간 변화"), ("tfr", "최근 합계출산율"), ("natural", "최근 자연증가"),
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
        self.births_panel = ChartPanel((12, 5))
        self.dash_panel = ChartPanel((12, 7))
        self.clean_table = make_table()
        self.yoy_table = make_table()
        self.decade_table = make_table()
        self.cagr_table = make_table()
        self.corr_table = make_table()
        self.stats_table = make_table()
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.births_panel, "출생아수 추이")
        self.tabs.addTab(self.dash_panel, "지표 대시보드")
        self.tabs.addTab(self.clean_table, "정제 데이터")
        self.tabs.addTab(self.yoy_table, "전년 대비")
        self.tabs.addTab(self.decade_table, "연대별 평균")
        self.tabs.addTab(self.cagr_table, "연평균 성장률")
        self.tabs.addTab(self.corr_table, "상관관계")
        self.tabs.addTab(self.stats_table, "기술 통계")
        self.tabs.addTab(self.report_view, "분석 리포트")
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
        path, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", str(start_dir), "엑셀 파일 (*.xlsx)")
        if path:
            self.path_edit.setText(path)
            self.run_analysis()

    def run_analysis(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.clean_df, self.result, report = run_pipeline(self.path_edit.text().strip())
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "분석 실패", f"{type(e).__name__}: {e}")
            return

        # 그래프 기간 입력 범위를 데이터 연도에 맞춘다
        first, last = int(self.clean_df.index.min()), int(self.clean_df.index.max())
        for spin in (self.start_spin, self.end_spin):
            spin.blockSignals(True)
            spin.setRange(first, last)
        self.start_spin.setValue(max(first, min(self.start_spin.value(), last)))
        self.end_spin.setValue(last)
        for spin in (self.start_spin, self.end_spin):
            spin.blockSignals(False)

        self.report_view.setPlainText(report)
        self.show_result()
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"분석 완료: {first}~{last}년 ({len(self.clean_df)}개 연도)")
        self.update_buttons()

    def show_result(self):
        res, s = self.result, self.result["summary"]

        def set_tile(key, text, color=None, sub=""):
            self.stat_values[key].setText(text)
            self.stat_values[key].setStyleSheet(f"color: {color};" if color else "")
            self.stat_subs[key].setText(sub)

        sign_color = lambda v: COLORS["rise"] if v >= 0 else COLORS["fall"]
        yr, v = s["max"]
        set_tile("max", f"{v / 10_000:,.1f}만명", sub=f"{yr}년")
        yr, v = s["min"]
        set_tile("min", f"{v / 10_000:,.1f}만명", sub=f"{yr}년")
        yr, v, pct, prov = s["last"]
        set_tile("last", f"{v / 10_000:,.1f}만명",
                 sub=f"{yr}년{' 잠정' if prov else ''} · 전년 대비 {pct:+.1f}%")
        y0, y1, ch = s["change"]
        set_tile("change", f"{ch:+.1%}", sign_color(ch), f"{y0} → {y1}년")
        yr, tfr, min_yr, min_tfr = s["tfr"]
        set_tile("tfr", f"{tfr:.2f}명", sub=f"{yr}년 · 최저 {min_yr}년 {min_tfr:.3f}")
        yr, ni = s["natural"]
        set_tile("natural", f"{ni / 10_000:+,.1f}만명", sign_color(ni), f"{yr}년 (출생-사망)")

        self.redraw_charts()

        clean = self.clean_df.rename(columns={**KOR, "is_provisional": "잠정치"})
        fill_table(self.clean_table, clean, "연도")
        fill_table(self.yoy_table, res["전년대비"], "연도", signed={"전년대비_증감", "전년대비_증감률(%)"})
        fill_table(self.decade_table, res["연대별평균"], "연대")
        fill_table(self.cagr_table, res["CAGR"], "기간", signed={"연평균 성장률(%)"})
        fill_table(self.corr_table, res["상관관계"], "지표")
        fill_table(self.stats_table, res["기술통계"], "지표")

    def redraw_charts(self):
        if self.clean_df is None:
            return
        start, end = self.start_spin.value(), self.end_spin.value()
        if end - start < 1:
            self.statusBar().showMessage("그래프 기간은 2개 연도 이상이어야 합니다.")
            return
        draw_births_chart(self.births_panel.figure, self.clean_df, start, end)
        self.births_panel.canvas.draw_idle()
        draw_dashboard(self.dash_panel.figure, self.clean_df, start, end)
        self.dash_panel.canvas.draw_idle()

    def update_buttons(self):
        has_result = self.result is not None
        self.save_xlsx_btn.setEnabled(has_result)
        self.save_img_btn.setEnabled(has_result and self.tabs.currentWidget() in (self.births_panel, self.dash_panel))

    def save_image(self):
        panel = self.tabs.currentWidget()
        default = "births_trend.png" if panel is self.births_panel else "birth_dashboard.png"
        path, _ = QFileDialog.getSaveFileName(self, "그래프 저장", default, "PNG 이미지 (*.png)")
        if path:
            panel.figure.savefig(path, dpi=150, facecolor=COLORS["surface"])
            self.statusBar().showMessage(f"저장했습니다: {path}")

    def save_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "분석 결과 저장", "birth_analysis.xlsx", "엑셀 파일 (*.xlsx)")
        if not path:
            return
        try:
            with pd.ExcelWriter(path) as xw:
                self.clean_df.rename(columns={**KOR, "is_provisional": "잠정치"}).to_excel(xw, sheet_name="정제데이터")
                for name, table in self.result.items():
                    if name != "summary":
                        table.to_excel(xw, sheet_name=name)
        except PermissionError:
            QMessageBox.warning(self, "저장 실패", "파일이 다른 프로그램(엑셀 등)에서 열려 있는지 확인하세요.")
            return
        self.statusBar().showMessage(f"저장했습니다: {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
