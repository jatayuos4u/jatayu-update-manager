"""Jatayu Update Manager: native Qt dashboard for Debian APT."""
import sys
from PyQt6.QtCore import Qt, QProcess, QSettings, QSize, QUrl
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from .transaction import parse_simulation, SimulationError
from PyQt6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView, QStackedWidget, QLineEdit, QStyle, QSizePolicy, QToolButton, QMenu, QDialog, QDialogButtonBox, QFormLayout)
from .core import available_updates, recent_history
from .i18n import tr
from . import __version__

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
        self.preview_output = bytearray()
        self.list_expanded = False
        self.build_ui()
        self.load_updates()

    def t(self, key, **kwargs):
        return tr(self.lang, key, **kwargs)

    def card(self, name=None):
        frame = QFrame()
        frame.setObjectName(name or 'card')
        frame.setFrameShape(QFrame.Shape.NoFrame)
        return frame

    def resolve_app_icon(self):
        # Match Icon=system-software-update in the desktop launcher.
        for name in ('system-software-update', 'software-update-available',
                     'update-none', 'preferences-system'):
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
        return self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)

    def set_brand_icon(self):
        icon = self.resolve_app_icon()
        self.setWindowIcon(icon)
        self.brand_label.setPixmap(icon.pixmap(QSize(42, 42)))
        self.brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def build_ui(self):
        self.setMinimumSize(800, 620)
        self.resize(1120, 820)
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 14, 22, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        self.brand_label = QLabel()
        self.brand_label.setObjectName('brand')
        self.brand_label.setFixedSize(50, 50)
        header.addWidget(self.brand_label)
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
        self.menu_button = QToolButton()
        self.menu_button.setText('⋮')
        self.menu_button.setToolTip(self.t('menu'))
        self.menu_button.setAccessibleName(self.t('menu'))
        self.menu_button.setFixedSize(36, 36)
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.app_menu = QMenu(self.menu_button)
        self.menu_button.setMenu(self.app_menu)
        self.about_action = QAction(self)
        self.help_action = QAction(self)
        self.issue_action = QAction(self)
        self.license_action = QAction(self)
        self.about_action.triggered.connect(self.show_about)
        self.help_action.triggered.connect(self.show_help)
        self.issue_action.triggered.connect(self.open_issues)
        self.license_action.triggered.connect(self.show_license)
        for action in (self.about_action, self.help_action, self.issue_action, self.license_action):
            self.app_menu.addAction(action)
        header.addWidget(self.menu_button)
        outer.addLayout(header)

        # Keep status and summary cards together so the user can expand the
        # update list without losing the toolbar or package controls.
        self.summary_panel = QWidget()
        self.summary_panel.setObjectName('summaryPanel')
        summary_layout = QVBoxLayout(self.summary_panel)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(9)

        status_card = self.card('hero')
        hero_layout = QVBoxLayout(status_card)
        hero_layout.setContentsMargins(18, 10, 18, 10)
        hero_layout.setSpacing(4)
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
        summary_layout.addWidget(status_card)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.metric_titles = []
        self.metric_values = []
        for icon in ('▣', '◷', '⬡'):
            card = self.card()
            lay = QVBoxLayout(card)
            lay.setContentsMargins(15, 8, 15, 8)
            lay.setSpacing(2)
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
        summary_layout.addLayout(metrics)
        outer.addWidget(self.summary_panel, 0)

        self.tabs = QTabWidget()
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
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
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        list_layout.addWidget(self.table, 1)
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
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tabs.setMinimumHeight(240)
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
        self.list_focus_button = QPushButton()
        self.list_focus_button.setObjectName('focusButton')
        self.list_focus_button.setMinimumHeight(40)
        self.list_focus_button.setCheckable(True)
        self.list_focus_button.toggled.connect(self.toggle_list_focus)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.install_button)
        buttons.addStretch()
        buttons.addWidget(self.list_focus_button)
        outer.addLayout(buttons)
        self.note = QLabel()
        self.note.setObjectName('muted')
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.translate_ui()
        self.apply_theme()
        self.set_brand_icon()

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
            QLabel#heroTitle {{ font-size: 17px; font-weight: 700; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#brand {{ background: transparent; border: none; }}
            QLabel#heroIcon {{ color: {accent}; font-size: 31px; padding-right: 12px; }}
            QLabel#metricIcon {{ color: {accent}; font-size: 17px; }}
            QLabel#metricValue {{ font-size: 23px; font-weight: 700; }}
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
            QToolButton {{ background: {card}; border: 1px solid {border}; border-radius: 8px; color: {fg}; font-size: 20px; }}
            QToolButton:hover {{ border-color: {accent}; }}
            QMenu {{ background: {card}; color: {fg}; border: 1px solid {border}; padding: 5px; }}
            QMenu::item {{ padding: 7px 20px; }}
            QMenu::item:selected {{ background: {accent}; color: white; }}
            QProgressBar {{ background: {border}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
        """)

    def translate_ui(self):
        self.setWindowTitle(self.t('title'))
        self.menu_button.setToolTip(self.t('menu'))
        self.menu_button.setAccessibleName(self.t('menu'))
        for action, key in ((self.about_action, 'about'), (self.help_action, 'help'),
                            (self.issue_action, 'report_issue'), (self.license_action, 'license_credits')):
            action.setText(self.t(key))
        self.title_label.setText(self.t('title'))
        self.subtitle_label.setText(self.t('subtitle'))
        self.hero_title.setText(self.t('system_status'))
        self.check_button.setText('↻  ' + self.t('check'))
        self.install_button.setText('↓  ' + self.t('install'))
        self.list_focus_button.setText(self.t('show_dashboard') if self.list_expanded else self.t('expand_updates'))
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

    def build_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('about'))
        dialog.setWindowIcon(self.resolve_app_icon())
        dialog.setMinimumWidth(430)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(self.resolve_app_icon().pixmap(QSize(52, 52)))
        top.addWidget(icon_label)
        heading = QLabel(self.t('title'))
        heading.setObjectName('heading')
        heading.setStyleSheet('font-size: 20px; font-weight: bold;')
        top.addWidget(heading, 1)
        layout.addLayout(top)
        description = QLabel(self.t('about_description'))
        description.setWordWrap(True)
        layout.addWidget(description)
        fields = QFormLayout()
        fields.addRow(self.t('version') + ':', QLabel(__version__.replace('rc', ' RC')))
        fields.addRow(self.t('creator') + ':', QLabel('Anup Kumar Yadav'))
        fields.addRow(self.t('developer') + ':', QLabel('JatayuOS Team'))
        fields.addRow(self.t('license') + ':', QLabel('MIT'))
        for key, address in (
            ('website', 'https://jatayuos.in'),
            ('source_code', 'https://github.com/jatayuos4u/jatayu-update-manager'),
        ):
            link = QLabel('<a href="' + address + '">' + address + '</a>')
            link.setOpenExternalLinks(True)
            fields.addRow(self.t(key) + ':', link)
        layout.addLayout(fields)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog

    def show_about(self):
        self.build_about_dialog().exec()

    def show_help(self):
        QMessageBox.information(self, self.t('help'), self.t('help_text'))

    def show_license(self):
        QMessageBox.information(
            self, self.t('license_credits'),
            self.t('license_info') + '\n\n' +
            self.t('creator') + ': Anup Kumar Yadav\n' +
            self.t('developer') + ': JatayuOS Team\n' +
            self.t('license') + ': MIT\n' +
            'https://github.com/jatayuos4u/jatayu-update-manager/blob/main/LICENSE'
        )

    def open_issues(self):
        QDesktopServices.openUrl(QUrl('https://github.com/jatayuos4u/jatayu-update-manager/issues'))

    def toggle_list_focus(self, expanded):
        self.list_expanded = expanded
        self.summary_panel.setVisible(not expanded)
        if expanded:
            self.tabs.setCurrentIndex(0)
        self.list_focus_button.setText(self.t('show_dashboard') if expanded else self.t('expand_updates'))

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
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, col, item)
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
        if self.busy or self.table.rowCount() == 0:
            return
        # Run an unprivileged APT simulation before asking for authorization.
        self.busy = True
        self.operation = 'preview'
        self.preview_output = bytearray()
        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.status.setText(self.t('previewing'))
        self.progress.setRange(0, 0)
        self.progress.show()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.preview_finished)
        self.process.start('/usr/bin/apt-get', ['-s', '--no-remove', 'upgrade'])

    def preview_finished(self, code, status):
        if self.operation != 'preview':
            return
        self.read_output()
        output = self.preview_output.decode('utf-8', errors='replace')
        self.process = None
        self.operation = None
        self.busy = False
        self.progress.hide()
        if code != 0 or status != QProcess.ExitStatus.NormalExit:
            self.checked = False
            self.last_error = self.t('preview_failed')
            self.log.setPlainText(output)
            self.tabs.setCurrentIndex(2)
            self.translate_ui()
            return
        try:
            preview = parse_simulation(output)
        except SimulationError as exc:
            self.checked = False
            self.last_error = str(exc)
            self.log.setPlainText(output)
            self.tabs.setCurrentIndex(2)
            self.translate_ui()
            return
        self.last_error = None
        self.translate_ui()
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.t('install'))
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(self.t('preview_question', count=len(preview.installs)))
        dialog.setInformativeText(self.t('preview_warning') + '\n\n' +
                                  '\n'.join(preview.installs[:8]))
        dialog.setDetailedText('\n'.join(preview.installs))
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            self.run_operation('upgrade', preview.digest)

    def closeEvent(self, event):
        # This protects against ordinary window closure, not abrupt crashes.
        if self.busy:
            QMessageBox.warning(self, self.t('working'), self.t('do_not_close'))
            event.ignore()
            return
        event.accept()

    def run_operation(self, action, digest=None):
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
        args = [HELPER, action] + ([digest] if action == 'upgrade' else [])
        self.process.start('/usr/bin/pkexec', args)

    def read_output(self):
        if self.process is None:
            return
        raw = bytes(self.process.readAllStandardOutput())
        if self.operation == 'preview':
            self.preview_output.extend(raw)
            return
        data = raw.decode('utf-8', errors='replace')
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(data)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.busy:
            self.last_error = self.t('failed_generic')
            self.busy = False
            self.operation = None
            self.progress.hide()
            self.process = None
            self.translate_ui()
            QMessageBox.warning(self, self.t('error'), self.last_error)
        else:
            self.log.append(f'Process error: {error}')

    def finished(self, code, status):
        if self.operation not in ('refresh', 'upgrade'):
            return
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
        if self.last_error:
            self.checked = False
            self.status.setText(self.last_error)
        elif self.operation == 'upgrade':
            # Require another successful refresh before offering another install.
            self.checked = False
            self.status.setText(self.t('success') + ' ' + self.t('restart'))
        elif self.operation == 'refresh':
            self.tabs.setCurrentIndex(0)
        self.refresh_empty_state()
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(self.checked and self.table.rowCount() > 0 and not self.last_error)
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
