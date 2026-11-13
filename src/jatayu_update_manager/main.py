"""Jatayu Update Manager: native Qt dashboard for Debian APT."""
import sys
from PyQt6.QtCore import Qt, QProcess, QSettings
from PyQt6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView, QStackedWidget, QLineEdit)
from .core import available_updates, recent_history
from .i18n import tr

HELPER = '/usr/lib/jatayu-update-manager/privileged-helper'

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('JatayuOS', 'UpdateManager')
        self.lang = self.settings.value('language', 'en')
        self.checked = False
        self.last_error = None
        self.last_success = self.settings.value('last_success', '')
        self.busy = False
        self.process = None
        self.operation = None
        self.build_ui()
        self.load_updates()

    def t(self, key, **kwargs):
        return tr(self.lang, key, **kwargs)

    def card(self, name=None):
        frame = QFrame()
        frame.setObjectName(name or 'card')
        frame.setFrameShape(QFrame.Shape.NoFrame)
        return frame

    def build_ui(self):
        self.setMinimumSize(850, 660)
        self.resize(990, 730)
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(17)

        header = QHBoxLayout()
        brand = QLabel('✦')
        brand.setObjectName('brand')
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(50, 50)
        header.addWidget(brand)
        headings = QVBoxLayout()
        headings.setSpacing(3)
        self.title_label = QLabel()
        self.title_label.setObjectName('heading')
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName('muted')
        headings.addWidget(self.title_label)
        headings.addWidget(self.subtitle_label)
        header.addLayout(headings)
        header.addStretch()
        self.language_box = QComboBox()
        self.language_box.setAccessibleName('Language / भाषा')
        self.language_box.addItem('English', 'en')
        self.language_box.addItem('हिन्दी', 'hi')
        self.language_box.setCurrentIndex(0 if self.lang == 'en' else 1)
        self.language_box.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_box)
        outer.addLayout(header)

        status_card = self.card('hero')
        hero_layout = QVBoxLayout(status_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(11)
        hero_row = QHBoxLayout()
        self.hero_icon = QLabel('◉')
        self.hero_icon.setObjectName('heroIcon')
        hero_row.addWidget(self.hero_icon)
        status_text = QVBoxLayout()
        self.hero_title = QLabel()
        self.hero_title.setObjectName('heroTitle')
        self.status = QLabel()
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        status_text.addWidget(self.hero_title)
        status_text.addWidget(self.status)
        hero_row.addLayout(status_text, 1)
        hero_layout.addLayout(hero_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()
        hero_layout.addWidget(self.progress)
        self.platform = QLabel('Debian 13 Trixie  •  APT  •  KDE Plasma')
        self.platform.setObjectName('muted')
        hero_layout.addWidget(self.platform)
        outer.addWidget(status_card)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_titles = []
        self.metric_values = []
        for icon in ('▣', '◷', '⬡'):
            card = self.card()
            lay = QVBoxLayout(card)
            lay.setContentsMargins(18, 14, 18, 14)
            lay.setSpacing(5)
            small = QLabel(icon)
            small.setObjectName('metricIcon')
            value = QLabel('—')
            value.setObjectName('metricValue')
            title = QLabel()
            title.setObjectName('muted')
            lay.addWidget(small)
            lay.addWidget(value)
            lay.addWidget(title)
            metrics.addWidget(card, 1)
            self.metric_titles.append(title)
            self.metric_values.append(value)
        outer.addLayout(metrics)

        self.tabs = QTabWidget()
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        self.updates_page = QWidget()
        page_layout = QVBoxLayout(self.updates_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self.update_stack = QStackedWidget()
        self.empty_panel = QWidget()
        empty_layout = QVBoxLayout(self.empty_panel)
        empty_layout.addStretch()
        self.empty_icon = QLabel('✓')
        self.empty_icon.setObjectName('emptyIcon')
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName('emptyTitle')
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message = QLabel()
        self.empty_message.setObjectName('muted')
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message.setWordWrap(True)
        empty_layout.addWidget(self.empty_icon)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_message)
        empty_layout.addStretch()
        self.update_stack.addWidget(self.empty_panel)
        self.list_panel = QWidget()
        list_layout = QVBoxLayout(self.list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_updates)
        list_layout.addWidget(self.search)
        list_layout.addWidget(self.table)
        self.update_stack.addWidget(self.list_panel)
        page_layout.addWidget(self.update_stack)
        self.tabs.addTab(self.updates_page, '')
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.tabs.addTab(self.history, '')
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName('log')
        self.tabs.addTab(self.log, '')
        outer.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.check_button = QPushButton()
        self.check_button.setObjectName('primary')
        self.check_button.setMinimumHeight(44)
        self.check_button.clicked.connect(lambda: self.run_operation('refresh'))
        self.install_button = QPushButton()
        self.install_button.setMinimumHeight(44)
        self.install_button.clicked.connect(self.confirm_install)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.install_button)
        buttons.addStretch()
        outer.addLayout(buttons)
        self.note = QLabel()
        self.note.setObjectName('muted')
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.translate_ui()
        self.apply_theme()

    def apply_theme(self):
        palette = QApplication.palette()
        bg = palette.window().color()
        dark = bg.lightness() < 128
        if dark:
            base, card, hero, border, fg, muted, accent, hover = ('#161B24','#222B38','#24354B','#38475A','#F3F6FB','#B4C2D3','#5BA4FA','#397FCF')
        else:
            base, card, hero, border, fg, muted, accent, hover = ('#F4F7FB','#FFFFFF','#E9F2FE','#D5DFEB','#1E293B','#59697C','#176BC2','#0B559F')
        self.setStyleSheet(f"""
            QWidget#root {{ background: {base}; color: {fg}; font-size: 13px; }}
            QLabel {{ color: {fg}; background: transparent; }}
            QLabel#heading {{ font-size: 23px; font-weight: 700; }}
            QLabel#heroTitle {{ font-size: 18px; font-weight: 700; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#brand {{ background: {accent}; color: white; font-size: 27px; font-weight: bold; border-radius: 13px; }}
            QLabel#heroIcon {{ color: {accent}; font-size: 31px; padding-right: 12px; }}
            QLabel#metricIcon {{ color: {accent}; font-size: 17px; }}
            QLabel#metricValue {{ font-size: 27px; font-weight: 700; }}
            QFrame#card, QFrame#hero {{ background: {card}; border: 1px solid {border}; border-radius: 13px; }}
            QFrame#hero {{ background: {hero}; }}
            QPushButton {{ background: {card}; border: 1px solid {border}; border-radius: 8px; padding: 9px 18px; color: {fg}; font-weight: 600; }}
            QPushButton:hover:enabled {{ border-color: {accent}; }}
            QPushButton#primary {{ background: {accent}; color: white; border: none; }}
            QPushButton#primary:hover:enabled {{ background: {hover}; }}
            QPushButton:disabled {{ color: {muted}; opacity: 0.6; }}
            QComboBox {{ background: {card}; border: 1px solid {border}; border-radius: 8px; padding: 8px 12px; color: {fg}; min-width: 92px; }}
            QComboBox QAbstractItemView {{ background: {card}; color: {fg}; selection-background-color: {accent}; }}
            QTabWidget::pane {{ border: 1px solid {border}; border-radius: 9px; background: {card}; }}
            QTabBar::tab {{ background: transparent; color: {muted}; padding: 11px 17px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {fg}; border-bottom: 2px solid {accent}; }}
            QTableWidget, QTextEdit {{ background: {card}; color: {fg}; border: none; selection-background-color: {accent}; selection-color: white; padding: 7px; }}
            QTableWidget::item {{ padding: 6px; }}
            QLineEdit {{ background: {card}; color: {fg}; border: 1px solid {border}; border-radius: 8px; padding: 8px; }}
            QLabel#emptyIcon {{ color: {accent}; font-size: 38px; }}
            QLabel#emptyTitle {{ font-size: 18px; font-weight: 700; }}
            QHeaderView::section {{ background: {card}; color: {muted}; border: none; border-bottom: 1px solid {border}; padding: 10px; font-weight: 600; }}
            QProgressBar {{ background: {border}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
        """)

    def translate_ui(self):
        self.setWindowTitle(self.t('title'))
        self.title_label.setText(self.t('title'))
        self.subtitle_label.setText(self.t('subtitle'))
        self.hero_title.setText(self.t('system_status'))
        self.check_button.setText('↻  ' + self.t('check'))
        self.install_button.setText('↓  ' + self.t('install'))
        for i, key in enumerate(('name', 'current', 'new')):
            self.table.setHorizontalHeaderItem(i, QTableWidgetItem(self.t(key)))
        for i, key in enumerate(('updates', 'history', 'log')):
            self.tabs.setTabText(i, self.t(key))
        for widget, key in zip(self.metric_titles, ('updates_count', 'last_check', 'manager')):
            widget.setText(self.t(key))
        self.metric_values[2].setText('APT')
        self.metric_values[1].setText(self.last_success or '—')
        self.search.setPlaceholderText(self.t('search'))
        self.note.setText(self.t('warning') + ' ' + self.t('restart'))
        if not self.busy:
            self.status.setText(self.t('failed_generic') if self.last_error else (self.t('count', count=self.table.rowCount()) if self.checked else self.t('ready')))
        self.refresh_empty_state()
        self.check_button.setEnabled(not self.busy)
        self.install_button.setEnabled(self.checked and self.table.rowCount() > 0 and not self.busy)

    def change_language(self):
        self.lang = self.language_box.currentData()
        self.settings.setValue('language', self.lang)
        self.translate_ui()

    def load_updates(self):
        try:
            updates = available_updates()
        except Exception as exc:
            self.status.setText(f'{self.t("error")}: {exc}')
            self.checked = False
            self.last_error = str(exc)
            self.refresh_empty_state()
            self.install_button.setEnabled(False)
            return
        self.table.setRowCount(len(updates))
        for row, values in enumerate(updates):
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.metric_values[0].setText(str(len(updates)) if self.checked else '—')
        self.history.setPlainText(recent_history())
        self.refresh_empty_state()
        self.install_button.setEnabled(self.checked and bool(updates) and not self.busy)
        if self.checked:
            self.status.setText(self.t('count', count=len(updates)) if updates else self.t('none'))

    def filter_updates(self, query):
        needle = query.casefold().strip()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            self.table.setRowHidden(row, bool(needle and item and needle not in item.text().casefold()))

    def refresh_empty_state(self):
        if not hasattr(self, 'update_stack'):
            return
        has_rows = self.table.rowCount() > 0
        self.update_stack.setCurrentIndex(1 if has_rows else 0)
        if self.last_error:
            title, message, icon = self.t('failed_generic'), self.last_error, '⚠'
        elif self.busy:
            title, message, icon = self.t('working'), self.t('wait'), '◌'
        elif self.checked:
            title, message, icon = self.t('none'), self.t('none_detail'), '✓'
        else:
            title, message, icon = self.t('not_checked'), self.t('check_prompt'), '↻'
        self.empty_title.setText(title)
        self.empty_message.setText(message)
        self.empty_icon.setText(icon)

    def confirm_install(self):
        if not self.checked:
            QMessageBox.information(self, self.t('info'), self.t('refresh_first'))
            return
        if QMessageBox.question(self, self.t('install'), self.t('confirm')) == QMessageBox.StandardButton.Yes:
            self.run_operation('upgrade')

    def run_operation(self, action):
        if self.busy:
            return
        self.busy = True
        self.last_error = None
        self.operation = action
        if action == 'refresh':
            self.checked = False
            self.metric_values[0].setText('—')
        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.status.setText(self.t('checking' if action == 'refresh' else 'installing'))
        self.progress.setRange(0, 0)
        self.progress.show()
        self.refresh_empty_state()
        self.log.clear()
        self.log.append(self.t('admin') + '\n')
        self.tabs.setCurrentIndex(2)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)
        self.process.start('/usr/bin/pkexec', [HELPER, action])

    def read_output(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(data)

    def process_error(self, error):
        self.log.append(f'Process error: {error}')

    def finished(self, code, status):
        self.read_output()
        success = code == 0 and status == QProcess.ExitStatus.NormalExit
        self.busy = False
        self.progress.hide()
        if success and self.operation == 'refresh':
            self.checked = True
            from datetime import datetime
            self.last_success = datetime.now().strftime('%Y-%m-%d %H:%M')
            self.settings.setValue('last_success', self.last_success)
            self.metric_values[1].setText(self.last_success)
        self.last_error = None if success else self.t('failed', code=code)
        self.load_updates()
        self.refresh_empty_state()
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(self.checked and self.table.rowCount() > 0)
        if not success:
            self.status.setText(self.t('failed', code=code))
        elif self.operation == 'upgrade':
            self.status.setText(self.t('success') + ' ' + self.t('restart'))
        elif self.operation == 'refresh':
            self.tabs.setCurrentIndex(0)
        self.operation = None
        self.process = None
        self.refresh_empty_state()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Jatayu Update Manager')
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
