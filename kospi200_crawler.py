"""
네이버 증권(Npay 증권)에서 코스피200 데이터를 크롤링하는 GUI 앱 (requests + BeautifulSoup4 + PyQt6)

stock.naver.com/market/stock/kr 는 브라우저에서 자바스크립트로 그려지는 페이지라
HTML 안에 지수 값이 없습니다. 그래서 같은 데이터를 서버에서 렌더링하는
모바일 지수 페이지(m.stock.naver.com/domestic/index/KPI200/total)를 BeautifulSoup으로 파싱하고,
페이지가 내부적으로 호출하는 JSON API로 편입종목·일별 시세를 가져옵니다.

설치:
    pip install -r requirements.txt   (requests, beautifulsoup4, PyQt6, openpyxl)

사용:
    python kospi200_crawler.py
"""
import csv
import json
import os
import sys
import time

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

INDEX_CODE = "KPI200"
INDEX_PAGE_URL = f"https://m.stock.naver.com/domestic/index/{INDEX_CODE}/total"
ENROLL_STOCKS_URL = f"https://m.stock.naver.com/api/index/{INDEX_CODE}/enrollStocks"
DAILY_PRICE_URL = f"https://m.stock.naver.com/api/index/{INDEX_CODE}/price"
STOCK_PAGE_URL = "https://stock.naver.com/domestic/stock/{}"

PAGE_SIZE = 50  # enrollStocks API는 pageSize 100부터 빈 응답을 줌
MAX_PAGES = 20  # API가 이상하게 응답해도 무한 반복하지 않도록 상한
INDEX_SIZE = 200

SUMMARY_LABELS = {
    "name": "지수명",
    "currentPrice": "현재가",
    "fluctuations": "전일대비",
    "fluctuationsRatio": "등락률(%)",
    "previousClosingPrice": "전일종가",
    "openPrice": "시가",
    "highPrice": "고가",
    "lowPrice": "저가",
    "accumulatedTradingVolume": "거래량",
    "accumulatedTradingValue": "거래대금",
    "highPriceOf52Weeks": "52주 최고",
    "lowPriceOf52Weeks": "52주 최저",
    "localTradedAt": "기준시각",
}

STOCK_FIELDS = {
    "rank": "순위",
    "itemCode": "종목코드",
    "stockName": "종목명",
    "closePrice": "현재가",
    "compareToPreviousClosePrice": "전일대비",
    "fluctuationsRatio": "등락률(%)",
    "accumulatedTradingVolume": "거래량",
    "accumulatedTradingValue": "거래대금(백만)",
    "marketValue": "시가총액(억)",
}

DAILY_FIELDS = {
    "localTradedAt": "날짜",
    "closePrice": "종가",
    "compareToPreviousClosePrice": "전일대비",
    "fluctuationsRatio": "등락률(%)",
    "openPrice": "시가",
    "highPrice": "고가",
    "lowPrice": "저가",
}

TEXT_FIELDS = {"itemCode", "stockName", "localTradedAt", "name"}  # 숫자로 바꾸지 않는 열
CHANGE_FIELDS = {"compareToPreviousClosePrice", "fluctuationsRatio"}  # 오르면 빨강, 내리면 파랑
EXCEL_COLUMN_WIDTHS = {"stockName": 20, "localTradedAt": 14}

# 노랑을 메인으로 한 따뜻한 색감 팔레트 (naver_news_crawler.py 와 같은 톤)
COLORS = {
    "bg": "#FFF9EE",
    "surface": "#FFFFFF",
    "surface_alt": "#FFFBF1",
    "border": "#F3E3BF",
    "primary": "#FFC233",
    "primary_light": "#FFD84D",
    "primary_dark": "#FFA41B",
    "accent": "#E8890C",
    "coral": "#E2683C",
    "selection": "#FFE59A",
    "chip": "#FFF0C2",
    "text": "#3B2A12",
    "muted": "#8A6A3F",
    "disabled": "#C9B99A",
    "rise": "#D6342C",  # 국내 증시 관례: 상승은 빨강
    "fall": "#2F6FDB",  # 하락은 파랑
}

STYLESHEET = """
QMainWindow, QWidget#root {{ background: {bg}; }}
QWidget {{ color: {text}; }}

QFrame#header {{
    border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {primary_light}, stop:0.55 {primary}, stop:1 {primary_dark});
}}
QLabel#logo {{
    background: {surface}; color: {primary_dark};
    border-radius: 24px; font-size: 22px; font-weight: 800;
}}
QLabel#appTitle {{ font-size: 22px; font-weight: 800; color: {text}; background: transparent; }}
QLabel#appSubtitle {{ font-size: 13px; color: #6B4A16; background: transparent; }}

QFrame[class="card"] {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 16px;
}}
QLabel[class="sectionTitle"] {{ font-size: 15px; font-weight: 700; background: transparent; }}
QLabel[class="fieldLabel"] {{ color: {muted}; font-weight: 600; background: transparent; }}
QLabel[class="statLabel"] {{ color: {muted}; font-size: 12px; background: transparent; }}
QLabel[class="statValue"] {{ font-size: 15px; font-weight: 700; background: transparent; }}
QLabel#indexName {{ font-size: 15px; font-weight: 700; color: {muted}; background: transparent; }}
QLabel#indexPrice {{ font-size: 34px; font-weight: 800; background: transparent; }}
QLabel#indexChange {{ font-size: 16px; font-weight: 700; background: transparent; }}
QLabel#indexTime {{ font-size: 12px; color: {muted}; background: transparent; }}
QFrame#statDivider {{ background: {border}; }}
QLabel#chip {{
    background: {chip}; color: {accent};
    border-radius: 11px; padding: 3px 12px; font-weight: 700;
}}

QLineEdit, QSpinBox {{
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 14px;
    selection-background-color: {selection};
    selection-color: {text};
}}
QSpinBox {{ padding: 9px 6px; }}
QSpinBox QLineEdit {{ padding: 0; border: none; background: transparent; }}  /* 스핀박스 내부 입력칸 */
/* 화살표 버튼은 숨기고 숫자 입력/휠로 조절. setButtonSymbols(NoButtons)는 QSS와 함께 쓰면 입력칸이 0폭이 된다. */
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {primary}; background: {surface}; }}

QPushButton {{
    background: {surface};
    border: 1px solid #F0D9A8;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 14px;
    font-weight: 600;
    color: #5A4220;
}}
QPushButton:hover {{ background: #FFF6DC; border-color: {primary}; }}
QPushButton:pressed {{ background: #FFEDB8; }}
QPushButton:disabled {{ background: #FBF6EA; border-color: #F1E8D4; color: {disabled}; }}
QPushButton#primary {{
    border: none; color: {text}; font-weight: 800; padding: 10px 26px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_light}, stop:1 {primary});
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary}, stop:1 {primary_dark});
}}
QPushButton#primary:disabled {{ background: #FCEBC0; color: {disabled}; }}
QPushButton#danger {{ color: {coral}; border-color: #F6C9A8; }}
QPushButton#danger:hover {{ background: #FFF1E8; border-color: {coral}; }}
QPushButton#danger:disabled {{ color: {disabled}; border-color: #F1E8D4; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {muted};
    padding: 8px 18px; margin-right: 4px;
    font-size: 14px; font-weight: 700;
    border: none; border-bottom: 3px solid transparent;
}}
QTabBar::tab:selected {{ color: {text}; border-bottom-color: {primary}; }}
QTabBar::tab:hover:!selected {{ color: {accent}; }}

QTableWidget {{
    background: {surface};
    alternate-background-color: {surface_alt};
    border: none;
    gridline-color: transparent;
    font-size: 13px;
    selection-background-color: {selection};
    selection-color: {text};
    outline: 0;
}}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px solid #FBF0D8; }}
QTableWidget::item:selected {{ background: {selection}; color: {text}; }}
QHeaderView::section {{
    background: #FFF4D6;
    color: {muted};
    font-weight: 700;
    padding: 9px 10px;
    border: none;
    border-bottom: 2px solid {primary};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #F5D58A; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {primary}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{
    background: #FFF3D6; color: {muted};
    border-top: 1px solid {border}; padding: 4px 12px;
}}
QMessageBox {{ background: {surface}; }}
""".format(**COLORS)


# ---------------------------------------------------------------- 크롤링 로직

def get(url, **params):
    resp = requests.get(url, params=params or None, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp


def fetch_index_summary():
    """지수 페이지 HTML을 BeautifulSoup으로 파싱해 코스피200 요약 시세를 꺼낸다.

    Next.js 페이지라 화면에 그려진 태그의 class 이름은 빌드마다 바뀌므로,
    서버가 HTML에 심어 두는 <script id="__NEXT_DATA__"> JSON을 읽는다.
    """
    soup = BeautifulSoup(get(INDEX_PAGE_URL).text, "html.parser")
    script = soup.select_one("script#__NEXT_DATA__")
    if script is None:
        raise RuntimeError("페이지에서 __NEXT_DATA__ 를 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있습니다.")

    data = json.loads(script.string)
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
    for query in queries:
        if query["queryKey"][0].get("url") == "/domestic/index/detail":
            return query["state"]["data"]["result"]
    raise RuntimeError("페이지 데이터에 지수 상세 정보가 없습니다.")


def iter_constituent_pages():
    """코스피200 편입종목을 페이지 단위로 넘겨준다.

    빈 페이지나 PAGE_SIZE보다 짧은 페이지가 오면 마지막 페이지로 보고 멈추며,
    페이지 경계에서 같은 종목이 다시 나와도 한 번만 담는다.
    """
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        rows = get(ENROLL_STOCKS_URL, page=page, pageSize=PAGE_SIZE).json()
        new_rows = []
        for row in rows:
            if row["itemCode"] not in seen:
                seen.add(row["itemCode"])
                row["rank"] = len(seen)
                new_rows.append(row)
        yield page, new_rows
        if len(rows) < PAGE_SIZE:
            return
        time.sleep(0.2)


def iter_daily_pages(pages):
    """최근 일별 지수 시세 (페이지당 10거래일)."""
    for page in range(1, pages + 1):
        rows = get(DAILY_PRICE_URL, page=page, pageSize=10).json()
        if not rows:
            return
        yield page, rows
        time.sleep(0.2)


def to_number(value):
    """"1,388,000" 같은 문자열을 숫자로. "N/A" 등 숫자가 아니면 None."""
    if isinstance(value, (int, float)):
        return value
    text = str(value).replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def format_number(value, decimals=2):
    n = to_number(value)
    if n is None:
        return str(value)
    return f"{n:,}" if isinstance(n, int) else f"{n:,.{decimals}f}"


def change_color(value):
    n = to_number(value)
    if not n:
        return COLORS["text"]
    return COLORS["rise"] if n > 0 else COLORS["fall"]


def change_text(key, value):
    """전일대비는 ▲/▼ 화살표, 등락률은 +/- 부호를 붙인다."""
    n = to_number(value)
    if n is None:
        return str(value)
    if key == "fluctuationsRatio":
        return f"{n:+.2f}%"
    arrow = "▲ " if n > 0 else "▼ " if n < 0 else ""
    return arrow + format_number(abs(n))


def save_csv(rows, fields, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀에서 한글 깨짐 방지
        writer = csv.writer(f)
        writer.writerow(fields.values())
        for row in rows:
            writer.writerow([row.get(key, "") for key in fields])


def write_sheet(ws, rows, fields):
    ws.append(list(fields.values()))
    for cell in ws[1]:
        cell.font = Font(bold=True, color=COLORS["text"][1:])
        cell.fill = PatternFill("solid", fgColor=COLORS["primary"][1:])
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row in rows:
        values = []
        for key in fields:
            value = row.get(key, "")
            n = None if key in TEXT_FIELDS else to_number(value)
            values.append(value if n is None else n)
        ws.append(values)

    for col, key in enumerate(fields, 1):
        letter = ws.cell(1, col).column_letter
        ws.column_dimensions[letter].width = EXCEL_COLUMN_WIDTHS.get(key, 14)
        if key not in TEXT_FIELDS:
            fmt = "#,##0.00" if any(isinstance(c.value, float) for c in ws[letter][1:]) else "#,##0"
            for cell in ws[letter][1:]:
                cell.number_format = fmt
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def save_xlsx(summary, stocks, daily, filename):
    """요약 · 편입종목 · 일별 시세를 시트 3개짜리 엑셀 파일 하나로 저장."""
    wb = Workbook()
    ws = wb.active
    ws.title = "지수 요약"
    write_sheet(ws, [{"label": label, "value": summary.get(key, "")}
                     for key, label in SUMMARY_LABELS.items()],
                {"label": "항목", "value": "값"})
    ws.column_dimensions["B"].width = 26
    write_sheet(wb.create_sheet("편입종목"), stocks, STOCK_FIELDS)
    write_sheet(wb.create_sheet("일별 시세"), daily, DAILY_FIELDS)
    wb.save(filename)


# ---------------------------------------------------------------- GUI

class CrawlWorker(QThread):
    """네트워크 작업을 별도 스레드에서 실행해 창이 멈추지 않게 한다."""

    status = pyqtSignal(str)
    summary = pyqtSignal(dict)
    stocks = pyqtSignal(list)
    daily = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, daily_pages):
        super().__init__()
        self.daily_pages = daily_pages

    def run(self):
        try:
            self.status.emit("코스피200 지수 페이지를 읽는 중...")
            self.summary.emit(fetch_index_summary())

            total = 0
            for page, rows in iter_constituent_pages():
                if self.isInterruptionRequested():
                    self.status.emit("중지되었습니다.")
                    return
                total += len(rows)
                self.stocks.emit(rows)
                self.status.emit(f"편입종목 {page}페이지 수집 중... (누적 {total}개)")

            days = 0
            for page, rows in iter_daily_pages(self.daily_pages):
                if self.isInterruptionRequested():
                    self.status.emit("중지되었습니다.")
                    return
                days += len(rows)
                self.daily.emit(rows)
                self.status.emit(f"일별 시세 {page}/{self.daily_pages}페이지 수집 중...")
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as e:
            self.failed.emit(f"수집 실패: {e}")
            return

        note = "" if total == INDEX_SIZE else f"  (네이버가 {INDEX_SIZE}개가 아닌 {total}개를 돌려줌)"
        self.status.emit(f"완료: 편입종목 {total}개, 일별 시세 {days}일{note}")


class SortItem(QTableWidgetItem):
    """숫자 열은 글자가 아니라 값으로 정렬되게 한다 ("9,120" < "11,860")."""

    def __init__(self, text, key=None):
        super().__init__(text)
        self.key = key

    def __lt__(self, other):
        if isinstance(other, SortItem) and self.key is not None and other.key is not None:
            return self.key < other.key
        return super().__lt__(other)


def make_card(shadow=False):
    """흰 카드. 그림자는 스크롤 영역이 없는 카드에만 쓴다(스크롤 시 느려짐 방지)."""
    card = QFrame()
    card.setProperty("class", "card")
    if not shadow:
        return card
    shadow = QGraphicsDropShadowEffect(card)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(214, 150, 30, 38))
    card.setGraphicsEffect(shadow)
    return card


def make_label(text, css_class):
    label = QLabel(text)
    label.setProperty("class", css_class)
    return label


def make_table(fields):
    table = QTableWidget(0, len(fields))
    table.setHorizontalHeaderLabels(fields.values())
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(40)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


def fill_rows(table, rows, fields):
    """표 끝에 행을 덧붙인다. 숫자는 오른쪽 정렬, 등락은 빨강/파랑."""
    sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)  # 정렬 중에 행을 넣으면 칸이 엇갈린다
    for data in rows:
        row = table.rowCount()
        table.insertRow(row)
        for col, key in enumerate(fields):
            value = data.get(key, "")
            if key in TEXT_FIELDS:
                item = SortItem(str(value))
            else:
                n = to_number(value)
                text = change_text(key, value) if key in CHANGE_FIELDS else format_number(value)
                item = SortItem(text, n if n is not None else float("-inf"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if key in CHANGE_FIELDS:
                item.setForeground(QColor(change_color(value)))
            elif key == "stockName":
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key == "itemCode":
                item.setForeground(QColor(COLORS["muted"]))
            table.setItem(row, col, item)
    table.setSortingEnabled(sorting)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 크롤러")
        self.resize(1280, 860)
        self.setMinimumSize(1000, 680)
        self.summary = {}
        self.stocks = []
        self.daily = []
        self.worker = None

        root = QVBoxLayout()
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(18)
        root.addWidget(self.build_header())
        root.addWidget(self.build_control_card())
        root.addWidget(self.build_summary_card())
        root.addWidget(self.build_tables_card(), 1)

        central = QWidget()
        central.setObjectName("root")
        central.setLayout(root)
        self.setCentralWidget(central)

        self.statusBar().showMessage("[수집]을 누르면 코스피200 지수와 편입종목을 가져옵니다. 종목을 더블클릭하면 네이버 증권으로 엽니다.")

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(96)

        logo = QLabel("K")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("코스피200 크롤러")
        title.setObjectName("appTitle")
        subtitle = QLabel("네이버 증권에서 지수 시세 · 편입종목 · 일별 시세를 모아 CSV · 엑셀로 저장하세요")
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
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 50)
        self.days_spin.setValue(3)
        self.days_spin.setSuffix(" 페이지")
        self.days_spin.setFixedWidth(100)
        self.days_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.days_spin.setToolTip("1페이지 = 10거래일")

        self.crawl_btn = QPushButton("수집")
        self.crawl_btn.setObjectName("primary")
        self.crawl_btn.clicked.connect(self.start_crawl)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.setToolTip("지금 보고 있는 탭의 표를 저장합니다")
        self.save_btn.clicked.connect(self.save)
        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.setToolTip("요약 · 편입종목 · 일별 시세를 시트 3개로 저장합니다")
        self.excel_btn.clicked.connect(self.save_excel)
        for btn in (self.crawl_btn, self.stop_btn, self.save_btn, self.excel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        divider = QFrame()
        divider.setFixedSize(1, 28)
        divider.setStyleSheet(f"background: {COLORS['border']};")

        card = make_card(shadow=True)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_label("일별 시세", "fieldLabel"))
        layout.addWidget(self.days_spin)
        layout.addWidget(make_label("(1페이지 = 10거래일)", "statLabel"))
        layout.addStretch()
        layout.addWidget(self.crawl_btn)
        layout.addWidget(self.stop_btn)
        layout.addSpacing(6)
        layout.addWidget(divider)
        layout.addSpacing(6)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.excel_btn)
        return card

    def build_summary_card(self):
        self.index_name = QLabel("코스피 200")
        self.index_name.setObjectName("indexName")
        self.index_price = QLabel("—")
        self.index_price.setObjectName("indexPrice")
        self.index_change = QLabel("")
        self.index_change.setObjectName("indexChange")
        self.index_time = QLabel("아직 수집하지 않았습니다")
        self.index_time.setObjectName("indexTime")

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(self.index_name)
        left.addWidget(self.index_price)
        left.addWidget(self.index_change)
        left.addSpacing(4)
        left.addWidget(self.index_time)

        stat_keys = [
            "previousClosingPrice", "openPrice", "highPrice", "lowPrice",
            "accumulatedTradingVolume", "accumulatedTradingValue",
            "highPriceOf52Weeks", "lowPriceOf52Weeks",
        ]
        self.stat_values = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        for i, key in enumerate(stat_keys):
            value = make_label("—", "statValue")
            self.stat_values[key] = value
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(make_label(SUMMARY_LABELS[key], "statLabel"))
            cell.addWidget(value)
            grid.addLayout(cell, i // 4, i % 4)

        divider = QFrame()
        divider.setObjectName("statDivider")
        divider.setFixedWidth(1)

        card = make_card(shadow=True)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(26, 18, 26, 18)
        layout.setSpacing(28)
        layout.addLayout(left)
        layout.addWidget(divider)
        layout.addLayout(grid, 1)
        return card

    def build_tables_card(self):
        self.count_chip = QLabel("0종목")
        self.count_chip.setObjectName("chip")

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("종목명 · 코드 검색")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setFixedWidth(220)
        self.filter_edit.textChanged.connect(self.apply_filter)

        self.stock_table = make_table(STOCK_FIELDS)
        self.stock_table.setSortingEnabled(True)
        self.stock_table.cellDoubleClicked.connect(self.open_stock)
        stock_header = self.stock_table.horizontalHeader()
        for col, key in enumerate(STOCK_FIELDS):
            if key in ("rank", "itemCode"):
                stock_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self.daily_table = make_table(DAILY_FIELDS)
        self.daily_table.setSortingEnabled(True)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.stock_table, "편입종목")
        self.tabs.addTab(self.daily_table, "일별 시세")
        self.tabs.currentChanged.connect(lambda i: self.filter_edit.setVisible(i == 0))

        title_row = QHBoxLayout()
        title_row.addWidget(make_label("수집 결과", "sectionTitle"))
        title_row.addWidget(self.count_chip)
        title_row.addStretch()
        title_row.addWidget(self.filter_edit)

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addLayout(title_row)
        layout.addWidget(self.tabs)
        return card

    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return

        self.summary = {}
        self.stocks.clear()
        self.daily.clear()
        for table in (self.stock_table, self.daily_table):
            table.setRowCount(0)
        self.stock_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.daily_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.count_chip.setText("0종목")
        self.set_running(True)

        self.worker = CrawlWorker(self.days_spin.value())
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.summary.connect(self.show_summary)
        self.worker.stocks.connect(self.add_stocks)
        self.worker.daily.connect(self.add_daily)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.requestInterruption()

    def set_running(self, running):
        self.crawl_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        can_save = not running and bool(self.stocks)
        self.save_btn.setEnabled(can_save)
        self.excel_btn.setEnabled(can_save)

    def show_summary(self, summary):
        self.summary = summary
        color = change_color(summary.get("fluctuations"))
        self.index_name.setText(summary.get("name", "코스피 200"))
        self.index_price.setText(format_number(summary.get("currentPrice", "—")))
        self.index_price.setStyleSheet(f"color: {color};")
        self.index_change.setText(
            f"{change_text('fluctuations', summary.get('fluctuations', ''))}   "
            f"{change_text('fluctuationsRatio', summary.get('fluctuationsRatio', ''))}"
        )
        self.index_change.setStyleSheet(f"color: {color};")
        self.index_time.setText(f"기준 {summary.get('localTradedAt', '')[:16].replace('T', ' ')}")

        for key, label in self.stat_values.items():
            value = summary.get(key, "")
            if key == "accumulatedTradingValue":
                n = to_number(value)
                text = f"{n / 1e8:,.0f}억" if n is not None else str(value)  # 원 → 억원
            elif key == "accumulatedTradingVolume":
                text = f"{format_number(value)}주"
            else:
                text = format_number(value)
            label.setText(text)

    def add_stocks(self, rows):
        self.stocks.extend(rows)
        fill_rows(self.stock_table, rows, STOCK_FIELDS)
        self.count_chip.setText(f"{len(self.stocks)}종목")
        self.apply_filter(self.filter_edit.text())

    def add_daily(self, rows):
        self.daily.extend(rows)
        fill_rows(self.daily_table, rows, DAILY_FIELDS)

    def apply_filter(self, text):
        text = text.strip().lower()
        code_col = list(STOCK_FIELDS).index("itemCode")
        name_col = list(STOCK_FIELDS).index("stockName")
        for row in range(self.stock_table.rowCount()):
            code = self.stock_table.item(row, code_col).text()
            name = self.stock_table.item(row, name_col).text().lower()
            self.stock_table.setRowHidden(row, bool(text) and text not in code and text not in name)

    def open_stock(self, row, _col):
        code = self.stock_table.item(row, list(STOCK_FIELDS).index("itemCode")).text()
        QDesktopServices.openUrl(QUrl(STOCK_PAGE_URL.format(code)))

    def show_error(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "오류", message)

    def save(self):
        if self.tabs.currentIndex() == 0:
            rows, fields, name = self.stocks, STOCK_FIELDS, "kospi200_stocks"
        else:
            rows, fields, name = self.daily, DAILY_FIELDS, "kospi200_daily"
        self.save_as("CSV 저장", "csv", "CSV 파일 (*.csv)", name,
                     lambda filename: save_csv(rows, fields, filename))

    def save_excel(self):
        self.save_as("엑셀 저장", "xlsx", "Excel 파일 (*.xlsx)", "kospi200",
                     lambda filename: save_xlsx(self.summary, self.stocks, self.daily, filename))

    def save_as(self, caption, ext, file_filter, name, writer):
        default = f"{name}_{time.strftime('%Y%m%d_%H%M')}.{ext}"
        filename, _ = QFileDialog.getSaveFileName(self, caption, default, file_filter)
        if not filename:
            return
        if not filename.lower().endswith(f".{ext}"):
            filename += f".{ext}"
        try:
            writer(filename)
        except OSError as e:  # 엑셀에서 같은 파일을 열어둔 경우 PermissionError
            self.show_error(f"저장 실패: {e}")
            return
        self.statusBar().showMessage(f"{filename} 에 저장했습니다.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        event.accept()


def resource_path(name):
    """PyInstaller 실행파일에서는 임시 압축해제 폴더(_MEIPASS), 평소에는 이 파일 옆에서 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 10))
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
