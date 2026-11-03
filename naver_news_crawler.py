"""
네이버 검색 결과에서 뉴스 기사를 찾아 본문까지 크롤링하는 GUI 앱 (BeautifulSoup4 + PyQt6)

설치:
    pip install -r requirements.txt   (requests, beautifulsoup4, PyQt6, openpyxl)

사용:
    python naver_news_crawler.py
"""
import csv
import html
import os
import re
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
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

# 네이버 뉴스(본문을 네이버가 직접 호스팅하는 기사) 주소 패턴
NAVER_ARTICLE_RE = re.compile(r"https://n\.news\.naver\.com/(?:mnews/)?article/\d+/\d+")

FIELDS = ["title", "press", "date", "url", "body"]
FIELD_LABELS = {"title": "제목", "press": "언론사", "date": "날짜", "url": "URL", "body": "본문"}
EXCEL_COLUMN_WIDTHS = {"title": 50, "press": 14, "date": 20, "url": 45, "body": 100}
EXCEL_CELL_MAX = 32767  # 엑셀 셀 하나에 들어가는 최대 글자 수

# 노랑을 메인으로 한 따뜻한 색감 팔레트
COLORS = {
    "bg": "#FFF9EE",          # 크림색 창 배경
    "surface": "#FFFFFF",     # 카드
    "surface_alt": "#FFFBF1", # 표 줄무늬
    "border": "#F3E3BF",
    "primary": "#FFC233",
    "primary_light": "#FFD84D",
    "primary_dark": "#FFA41B",
    "accent": "#E8890C",      # 링크, 강조 글자
    "coral": "#E2683C",       # 중지 버튼
    "selection": "#FFE59A",
    "chip": "#FFF0C2",
    "text": "#3B2A12",        # 따뜻한 짙은 갈색
    "muted": "#8A6A3F",
    "disabled": "#C9B99A",
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

QTextBrowser {{ background: transparent; border: none; }}

QSplitter::handle {{ background: transparent; }}

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

def build_search_urls(query):
    """통합검색(nexearch) URL과, 기사가 더 많이 나오는 뉴스탭 URL."""
    q = quote(query)
    return [
        f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={q}",
        f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={q}",
    ]


def get_soup(url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def collect_article_links(query, limit):
    """검색 결과 페이지에서 네이버 뉴스 기사 링크를 중복 없이 수집."""
    links = []
    for url in build_search_urls(query):
        soup = get_soup(url)
        # 네이버 검색 결과의 class 이름은 자주 바뀌므로, href 패턴으로 찾는 것이 안정적이다.
        for a in soup.find_all("a", href=True):
            m = NAVER_ARTICLE_RE.match(a["href"])
            if m and m.group(0) not in links:
                links.append(m.group(0))
                if len(links) >= limit:
                    return links
    return links


def text_of(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else ""


def parse_article(url):
    """n.news.naver.com 기사 페이지에서 제목/언론사/날짜/본문 추출."""
    soup = get_soup(url)

    title = text_of(soup, "#title_area") or text_of(soup, "h2.media_end_head_headline")

    press_img = soup.select_one("a.media_end_head_top_logo img")
    press = press_img.get("alt", "") if press_img else ""

    date_tag = soup.select_one("span.media_end_head_info_datestamp_time")
    date = date_tag.get("data-date-time", date_tag.get_text(strip=True)) if date_tag else ""

    body_tag = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    body = ""
    if body_tag:
        # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
        for junk in body_tag.select("script, style, .img_desc, .end_photo_org em, .media_end_summary"):
            junk.decompose()
        body = body_tag.get_text("\n", strip=True)

    return {"title": title, "press": press, "date": date, "url": url, "body": body}


def save_csv(articles, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(articles)


def save_xlsx(articles, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    ws.append([FIELD_LABELS[f] for f in FIELDS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color=COLORS["text"][1:])
        cell.fill = PatternFill("solid", fgColor=COLORS["primary"][1:])
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for article in articles:
        # 엑셀이 허용하지 않는 제어 문자를 지우고, 셀 최대 길이에 맞춰 자른다.
        ws.append([ILLEGAL_CHARACTERS_RE.sub("", article[f])[:EXCEL_CELL_MAX] for f in FIELDS])
        row = ws.max_row
        url_cell = ws.cell(row, FIELDS.index("url") + 1)
        url_cell.hyperlink = article["url"]
        url_cell.style = "Hyperlink"
        for cell in ws[row]:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter != url_cell.column_letter)
        ws.row_dimensions[row].height = 90

    for col, field in enumerate(FIELDS, 1):
        ws.column_dimensions[ws.cell(1, col).column_letter].width = EXCEL_COLUMN_WIDTHS[field]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(filename)


# ---------------------------------------------------------------- GUI

class CrawlWorker(QThread):
    """네트워크 작업을 별도 스레드에서 실행해 창이 멈추지 않게 한다."""

    status = pyqtSignal(str)
    article = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, query, limit):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            self.status.emit(f"'{self.query}' 검색 결과에서 기사 링크를 찾는 중...")
            links = collect_article_links(self.query, self.limit)
        except requests.RequestException as e:
            self.failed.emit(f"검색 실패: {e}")
            return

        if not links:
            self.status.emit("기사 링크를 찾지 못했습니다.")
            return

        for i, link in enumerate(links, 1):
            if self.isInterruptionRequested():
                self.status.emit("중지되었습니다.")
                return
            self.status.emit(f"기사 수집 중... ({i}/{len(links)})")
            try:
                self.article.emit(parse_article(link))
            except requests.RequestException as e:
                self.status.emit(f"실패: {link} ({e})")
            time.sleep(0.5)  # 서버 부담을 줄이기 위한 요청 간격

        self.status.emit(f"완료: 기사 {len(links)}개")


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1280, 800)
        self.setMinimumSize(980, 620)
        self.articles = []
        self.worker = None

        root = QVBoxLayout()
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(18)
        root.addWidget(self.build_header())
        root.addWidget(self.build_search_card())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(18)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.build_list_card())
        splitter.addWidget(self.build_body_card())
        splitter.setSizes([560, 680])
        root.addWidget(splitter, 1)

        central = QWidget()
        central.setObjectName("root")
        central.setLayout(root)
        self.setCentralWidget(central)

        self.show_empty_body()
        self.statusBar().showMessage("검색어를 입력하고 [검색]을 누르세요. 기사를 더블클릭하면 브라우저로 엽니다.")

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(96)

        logo = QLabel("N")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("네이버 뉴스 크롤러")
        title.setObjectName("appTitle")
        subtitle = QLabel("키워드로 최신 기사를 모아 읽고, CSV · 엑셀로 저장하세요")
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

    def build_search_card(self):
        self.query_edit = QLineEdit("반도체")
        self.query_edit.setPlaceholderText("검색어를 입력하세요")
        self.query_edit.setClearButtonEnabled(True)
        self.query_edit.returnPressed.connect(self.start_crawl)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(10)
        self.limit_spin.setSuffix(" 개")
        self.limit_spin.setFixedWidth(84)
        self.limit_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.search_btn = QPushButton("검색")
        self.search_btn.setObjectName("primary")
        self.search_btn.clicked.connect(self.start_crawl)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel)
        for btn in (self.search_btn, self.stop_btn, self.save_btn, self.excel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        divider = QFrame()
        divider.setFixedSize(1, 28)
        divider.setStyleSheet(f"background: {COLORS['border']};")

        card = make_card(shadow=True)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_label("검색어", "fieldLabel"))
        layout.addWidget(self.query_edit, 1)
        layout.addSpacing(8)
        layout.addWidget(make_label("최대", "fieldLabel"))
        layout.addWidget(self.limit_spin)
        layout.addSpacing(8)
        layout.addWidget(self.search_btn)
        layout.addWidget(self.stop_btn)
        layout.addSpacing(6)
        layout.addWidget(divider)
        layout.addSpacing(6)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.excel_btn)
        return card

    def build_list_card(self):
        self.count_chip = QLabel("0건")
        self.count_chip.setObjectName("chip")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["언론사", "제목", "날짜"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.currentCellChanged.connect(lambda row, *_: self.show_article(row))
        self.table.cellDoubleClicked.connect(self.open_in_browser)

        title_row = QHBoxLayout()
        title_row.addWidget(make_label("기사 목록", "sectionTitle"))
        title_row.addWidget(self.count_chip)
        title_row.addStretch()

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        layout.addLayout(title_row)
        layout.addWidget(self.table)
        return card

    def build_body_card(self):
        self.body_view = QTextBrowser()
        self.body_view.setOpenExternalLinks(True)

        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 10, 18)
        layout.setSpacing(12)
        layout.addWidget(make_label("기사 본문", "sectionTitle"))
        layout.addWidget(self.body_view)
        return card

    def start_crawl(self):
        query = self.query_edit.text().strip()
        if not query or (self.worker and self.worker.isRunning()):
            return

        self.articles.clear()
        self.table.setRowCount(0)
        self.count_chip.setText("0건")
        self.show_empty_body("기사를 모으는 중입니다...")
        self.set_running(True)

        self.worker = CrawlWorker(query, self.limit_spin.value())
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.article.connect(self.add_article)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.requestInterruption()

    def set_running(self, running):
        self.search_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        can_save = not running and bool(self.articles)
        self.save_btn.setEnabled(can_save)
        self.excel_btn.setEnabled(can_save)

    def add_article(self, article):
        self.articles.append(article)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, key in enumerate(["press", "title", "date"]):
            item = QTableWidgetItem(article[key])
            item.setToolTip(article[key])
            if key == "press":
                item.setForeground(QColor(COLORS["accent"]))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key == "date":
                item.setForeground(QColor(COLORS["muted"]))
            self.table.setItem(row, col, item)
        self.count_chip.setText(f"{len(self.articles)}건")
        if row == 0:
            self.table.selectRow(0)

    def show_empty_body(self, message="왼쪽 목록에서 기사를 선택하면 본문이 여기에 표시됩니다."):
        self.body_view.setHtml(
            f"<table width='100%' height='420'><tr><td align='center' valign='middle' "
            f"style='color:{COLORS['disabled']}; font-size:14px;'>"
            f"<span style='font-size:34px; color:{COLORS['primary']};'>&#9679;</span><br><br>"
            f"{html.escape(message)}</td></tr></table>"
        )

    def show_article(self, row):
        if not 0 <= row < len(self.articles):
            return
        a = {k: html.escape(v) for k, v in self.articles[row].items()}
        paragraphs = "".join(
            f"<p style='margin:0 0 14px 0; line-height:170%;'>{p}</p>"
            for p in a["body"].split("\n") if p.strip()
        )
        self.body_view.setHtml(f"""
            <div style="color:{COLORS['text']}; font-size:14px;">
              <p style="margin:0 0 12px 0;">
                <span style="background:{COLORS['chip']}; color:{COLORS['accent']}; font-weight:700;">
                  &nbsp;{a['press']}&nbsp;</span>
                <span style="color:{COLORS['muted']};">&nbsp;&nbsp;{a['date']}</span>
              </p>
              <p style="margin:0 0 10px 0; font-size:21px; font-weight:800; line-height:140%;">{a['title']}</p>
              <p style="margin:0 0 18px 0;">
                <a href="{a['url']}" style="color:{COLORS['accent']}; text-decoration:none; font-weight:600;">
                  원문 보기 →</a></p>
              <hr style="background:{COLORS['border']};">
              <div style="margin-top:16px;">{paragraphs or '<p>본문을 가져오지 못했습니다.</p>'}</div>
            </div>""")

    def open_in_browser(self, row, _col):
        QDesktopServices.openUrl(QUrl(self.articles[row]["url"]))

    def show_error(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "오류", message)

    def save(self):
        self.save_as("CSV 저장", "csv", "CSV 파일 (*.csv)", save_csv)

    def save_excel(self):
        self.save_as("엑셀 저장", "xlsx", "Excel 파일 (*.xlsx)", save_xlsx)

    def save_as(self, caption, ext, file_filter, writer):
        default = f"naver_news_{self.query_edit.text().strip()}.{ext}"
        filename, _ = QFileDialog.getSaveFileName(self, caption, default, file_filter)
        if not filename:
            return
        if not filename.lower().endswith(f".{ext}"):
            filename += f".{ext}"
        try:
            writer(self.articles, filename)
        except OSError as e:  # 엑셀에서 같은 파일을 열어둔 경우 PermissionError
            self.show_error(f"저장 실패: {e}")
            return
        self.statusBar().showMessage(f"{len(self.articles)}개 기사를 {filename} 에 저장했습니다.")

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
