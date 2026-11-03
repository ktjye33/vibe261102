"""
네이버 검색 결과에서 뉴스 기사를 찾아 본문까지 크롤링하는 GUI 앱 (BeautifulSoup4 + PyQt6)

설치:
    pip install -r requirements.txt   (requests, beautifulsoup4, PyQt6, openpyxl)

사용:
    python naver_news_crawler.py
"""
import csv
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
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
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
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="03C75A")
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1100, 700)
        self.articles = []
        self.worker = None

        # 검색 조건
        self.query_edit = QLineEdit("반도체")
        self.query_edit.setPlaceholderText("검색어")
        self.query_edit.returnPressed.connect(self.start_crawl)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(10)
        self.limit_spin.setSuffix(" 개")

        self.search_btn = QPushButton("검색")
        self.search_btn.clicked.connect(self.start_crawl)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel)

        top = QHBoxLayout()
        top.addWidget(QLabel("검색어"))
        top.addWidget(self.query_edit, 1)
        top.addWidget(QLabel("최대"))
        top.addWidget(self.limit_spin)
        top.addWidget(self.search_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # 기사 목록
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["언론사", "제목", "날짜"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.currentCellChanged.connect(lambda row, *_: self.show_article(row))
        self.table.cellDoubleClicked.connect(self.open_in_browser)

        # 기사 본문
        self.body_view = QTextBrowser()
        self.body_view.setOpenExternalLinks(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.body_view)
        splitter.setSizes([300, 400])

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.statusBar().showMessage("검색어를 입력하고 [검색]을 누르세요. 기사를 더블클릭하면 브라우저로 엽니다.")

    def start_crawl(self):
        query = self.query_edit.text().strip()
        if not query or (self.worker and self.worker.isRunning()):
            return

        self.articles.clear()
        self.table.setRowCount(0)
        self.body_view.clear()
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
            self.table.setItem(row, col, QTableWidgetItem(article[key]))
        if row == 0:
            self.table.selectRow(0)

    def show_article(self, row):
        if not 0 <= row < len(self.articles):
            return
        a = self.articles[row]
        self.body_view.setMarkdown(
            f"## {a['title']}\n\n"
            f"**{a['press']}** · {a['date']} · [원문 보기]({a['url']})\n\n---\n\n"
            + a["body"].replace("\n", "\n\n")
        )

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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
