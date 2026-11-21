"""Interface da ilha: cápsula compacta e painel preso ao topo da tela."""

import math

from PySide6.QtCore import Qt, QTimer, QRect, Signal, QEasingCurve, QPropertyAnimation, QPointF, QSettings
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPainterPath, QPixmap, QPen, QLinearGradient, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMenu,
    QProgressBar, QPushButton, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)


THEMES = {
    'midnight': {
        'name': 'Meia-Noite (Azul)',
        'bg_top': '#05080e',
        'bg_bottom': '#0b1423',
        'border': '#20314b',
        'text': '#f7f9ff',
        'muted': '#8290a8',
        'accent': '#6bbcff',
        'surface': '#17253a',
        'surface_hover': '#202c42',
        'bar_bg': '#1d293b',
    },
    'obsidian': {
        'name': 'Obsidiana (OLED)',
        'bg_top': '#000000',
        'bg_bottom': '#0d0d10',
        'border': '#27272a',
        'text': '#fafafa',
        'muted': '#8e8e93',
        'accent': '#e4e4e7',
        'surface': '#1c1c1f',
        'surface_hover': '#2c2c30',
        'bar_bg': '#222226',
    },
    'emerald': {
        'name': 'Esmeralda',
        'bg_top': '#05100b',
        'bg_bottom': '#0b1f16',
        'border': '#1b3d2d',
        'text': '#f3fbf7',
        'muted': '#7fa391',
        'accent': '#1ed760',
        'surface': '#132e22',
        'surface_hover': '#1c4231',
        'bar_bg': '#173326',
    },
    'amber': {
        'name': 'Âmbar Quente',
        'bg_top': '#110b07',
        'bg_bottom': '#1f140c',
        'border': '#3d2818',
        'text': '#fff8f2',
        'muted': '#a88e79',
        'accent': '#ff9f43',
        'surface': '#2b1c11',
        'surface_hover': '#3d2819',
        'bar_bg': '#2e1f14',
    },
    'amethyst': {
        'name': 'Ametista',
        'bg_top': '#0c0714',
        'bg_bottom': '#180f29',
        'border': '#322152',
        'text': '#f8f5ff',
        'muted': '#9687b3',
        'accent': '#b388ff',
        'surface': '#23163b',
        'surface_hover': '#312052',
        'bar_bg': '#25183d',
    },
}

STYLES = {
    'notch': 'Notch Clássico (Topo)',
    'floating': 'Pílula Flutuante',
    'glass': 'Vidro Translúcido',
    'neon': 'Borda Neon',
}


class ClickFrame(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class LensPair(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(46, 20)
        self.ring_color = '#1b2944'
        self.dot_color = '#b8d9fb'

    def set_colors(self, ring_color, dot_color):
        self.ring_color = ring_color
        self.dot_color = dot_color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (3, 25):
            painter.setBrush(QColor(self.ring_color))
            painter.drawEllipse(x, 1, 18, 18)
            painter.setBrush(QColor(self.dot_color))
            painter.drawEllipse(x + 7, 8, 4, 4)


class Waveform(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(27, 22)
        self.playing = False
        self.phase = 0
        self.active_color = '#6bbcff'
        self.idle_color = '#536d8f'
        self.timer = QTimer(self)
        self.timer.setInterval(125)
        self.timer.timeout.connect(self.advance)

    def set_colors(self, accent, muted):
        self.active_color = accent
        self.idle_color = muted
        self.update()

    def set_playing(self, playing):
        self.playing = bool(playing)
        if self.playing:
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def advance(self):
        self.phase += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.active_color if self.playing else self.idle_color))
        for index, x in enumerate((2, 8, 14, 20)):
            height = 6 + int(10 * abs(math.sin(self.phase * .62 + index * 1.5))) if self.playing else (7, 13, 9, 5)[index]
            painter.drawRoundedRect(x, (22 - height) // 2, 3, height, 1.5, 1.5)


class MediaButton(QPushButton):
    def __init__(self, kind, callback):
        super().__init__('')
        self.kind = kind
        self.playing = False
        self.icon_color = '#f3f7ff'
        self.disabled_color = '#4d5a6e'
        self.setObjectName('play' if kind == 'play' else 'control')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(callback)
        self.setAccessibleName({'previous': 'Faixa anterior', 'play': 'Reproduzir ou pausar', 'next': 'Próxima faixa'}[kind])

    def set_colors(self, text_color, muted_color):
        self.icon_color = text_color
        self.disabled_color = muted_color
        self.update()

    def set_playing(self, playing):
        self.playing = bool(playing)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.kind == 'play':
            color = '#091422' if self.isEnabled() else self.disabled_color
        else:
            color = self.icon_color if self.isEnabled() else self.disabled_color
        painter.setBrush(QColor(color))
        center_x, center_y = self.width() / 2, self.height() / 2
        if self.kind == 'play':
            if self.playing:
                painter.drawRoundedRect(int(center_x - 5), int(center_y - 7), 3, 14, 1, 1)
                painter.drawRoundedRect(int(center_x + 2), int(center_y - 7), 3, 14, 1, 1)
            else:
                painter.drawPolygon(QPolygonF([
                    QPointF(center_x - 4, center_y - 8),
                    QPointF(center_x + 7, center_y),
                    QPointF(center_x - 4, center_y + 8),
                ]))
        else:
            direction = -1 if self.kind == 'previous' else 1
            for offset in (-3, 5):
                x = center_x + offset
                painter.drawPolygon(QPolygonF([
                    QPointF(x - direction * 4, center_y - 6),
                    QPointF(x + direction * 4, center_y),
                    QPointF(x - direction * 4, center_y + 6),
                ]))
            edge = center_x - 11 if direction < 0 else center_x + 10
            painter.drawRoundedRect(int(edge), int(center_y - 7), 2, 14, 1, 1)


class Island(QWidget):
    IDLE_WIDTH = 132
    IDLE_HEIGHT = 32
    COMPACT_WIDTH = 318
    COMPACT_HEIGHT = 44
    EXPANDED_WIDTH = 480
    EXPANDED_HEIGHT = 248
    SETTINGS_HEIGHT = 335

    def __init__(self, media_worker_type, metrics_worker_type, album_art_type):
        super().__init__()
        self.expanded = False
        self.hidden_by_user = False
        self.media = None
        self.last_art = None
        self.latest_metrics = {}
        self.metric_checks = {}
        self.metric_labels = {}
        self.unattended = 0
        self._quit = False
        self.animation = None

        self.settings = QSettings('IlhaDinamica', 'WindowsIsland')
        self.current_theme_key = self.settings.value('theme', 'midnight')
        self.current_style_key = self.settings.value('style', 'notch')
        if self.current_theme_key not in THEMES:
            self.current_theme_key = 'midnight'
        if self.current_style_key not in STYLES:
            self.current_style_key = 'notch'

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('Ilha Dinâmica')

        self.compact_panel = ClickFrame(self)
        self.compact_panel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compact_panel.clicked.connect(self.expand)
        compact = QHBoxLayout(self.compact_panel)
        compact.setContentsMargins(15, 0, 17, 0)
        compact.setSpacing(10)
        self.lenses = LensPair()
        self.small_art = album_art_type(29)
        self.compact_title = QLabel('')
        self.compact_title.setObjectName('compactTitle')
        self.compact_title.setMinimumWidth(0)
        self.compact_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waveform = Waveform()
        for widget in (self.lenses, self.small_art, self.compact_title, self.waveform):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        compact.addWidget(self.lenses)
        compact.addWidget(self.small_art)
        compact.addWidget(self.compact_title, 1)
        compact.addWidget(self.waveform)

        self.expanded_panel = QWidget(self)
        panel = QVBoxLayout(self.expanded_panel)
        panel.setContentsMargins(22, 16, 22, 20)
        panel.setSpacing(15)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        self.nav_buttons = []
        for index, name in enumerate(('Música', 'Sistema', 'Ajustes')):
            button = QPushButton(name)
            button.setObjectName('navButton')
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, i=index: self.select_page(i))
            self.nav_buttons.append(button)
            nav.addWidget(button)
        nav.addStretch(1)
        self.summary_label = QLabel('CPU —   RAM —')
        self.summary_label.setObjectName('summary')
        nav.addWidget(self.summary_label)
        self.collapse_button = self._button('−', self.collapse, 'collapseButton')
        self.collapse_button.setToolTip('Recolher ilha')
        nav.addSpacing(10)
        nav.addWidget(self.collapse_button)
        panel.addLayout(nav)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._create_media_page(album_art_type))
        self.pages.addWidget(self._create_system_page())
        self.pages.addWidget(self._create_settings_page())
        panel.addWidget(self.pages, 1)
        self.select_page(0)

        self.media_worker = media_worker_type()
        self.media_worker.changed.connect(self.on_media)
        self.media_worker.error.connect(self.on_media_error)
        self.metrics_worker = metrics_worker_type()
        self.metrics_worker.changed.connect(self.on_metrics)
        self.media_worker.start()
        self.metrics_worker.start()

        t = THEMES[self.current_theme_key]
        self.tray = QSystemTrayIcon(self._tray_icon(t['bg_top'], t['accent']), self)
        menu = QMenu()
        menu.addAction('Mostrar / ocultar', self.toggle_visibility)
        menu.addAction('Expandir', self.expand)
        menu.addSeparator()
        menu.addAction('Sair', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.auto_collapse = QTimer(self)
        self.auto_collapse.timeout.connect(self.auto_collapse_tick)
        self.auto_collapse.start(1000)

        self.apply_theme()
        self.refresh_metric_visibility()
        self.collapse(initial=True)

    def _create_media_page(self, album_art_type):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        row = QHBoxLayout()
        row.setSpacing(22)
        self.album_art = album_art_type(100)
        row.addWidget(self.album_art)
        details = QVBoxLayout()
        details.setSpacing(4)
        self.title_label = QLabel('Nenhuma reprodução detectada')
        self.title_label.setObjectName('mediaTitle')
        self.title_label.setMinimumWidth(0)
        self.artist_label = QLabel('Abra Spotify ou YouTube')
        self.artist_label.setObjectName('artist')
        self.status_label = QLabel('Aguardando mídia do Windows')
        self.status_label.setObjectName('status')
        details.addWidget(self.title_label)
        details.addWidget(self.artist_label)
        details.addWidget(self.status_label)
        details.addStretch()
        self.generic_hint = QLabel('Sem controles de faixa para este aplicativo')
        self.generic_hint.setObjectName('secondary')
        self.generic_hint.hide()
        details.addWidget(self.generic_hint)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.btn_prev = MediaButton('previous', lambda: self.media_worker.control('previous'))
        self.btn_play = MediaButton('play', lambda: self.media_worker.control('toggle'))
        self.btn_next = MediaButton('next', lambda: self.media_worker.control('next'))
        for button in (self.btn_prev, self.btn_play, self.btn_next):
            controls.addWidget(button)
        controls.addStretch()
        details.addLayout(controls)
        row.addLayout(details, 1)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        time_row = QHBoxLayout()
        self.elapsed_label = QLabel('0:00')
        self.remaining_label = QLabel('—')
        for label in (self.elapsed_label, self.remaining_label):
            label.setObjectName('secondary')
        time_row.addWidget(self.elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self.remaining_label)
        layout.addLayout(time_row)
        layout.addStretch()
        return page

    def _create_system_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        heading = QLabel('Visão geral do sistema')
        heading.setObjectName('sectionHeading')
        layout.addWidget(heading)
        for name, caption in (
            ('CPU', 'Processador'), ('RAM', 'Memória'), ('GPU', 'Placa de vídeo'),
            ('CPU Temp', 'Temperatura CPU'), ('GPU Temp', 'Temperatura GPU'),
        ):
            wrapper = QWidget()
            row = QHBoxLayout(wrapper)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            title = QLabel(caption)
            title.setFixedWidth(126)
            bar = QProgressBar()
            bar.setObjectName('metricBar')
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(0)
            value = QLabel('—')
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setFixedWidth(45)
            row.addWidget(title)
            row.addWidget(bar, 1)
            row.addWidget(value)
            layout.addWidget(wrapper)
            self.metric_labels[name] = (wrapper, value, bar)
        layout.addStretch()
        return page

    def _create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        appearance_heading = QLabel('Aparência')
        appearance_heading.setObjectName('sectionHeading')
        layout.addWidget(appearance_heading)

        appearance_row = QHBoxLayout()
        appearance_row.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, data in THEMES.items():
            self.theme_combo.addItem(data['name'], key)
        self.theme_combo.setCurrentIndex(list(THEMES.keys()).index(self.current_theme_key))
        self.theme_combo.currentIndexChanged.connect(self._on_appearance_changed)

        self.style_combo = QComboBox()
        self.style_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, label in STYLES.items():
            self.style_combo.addItem(label, key)
        self.style_combo.setCurrentIndex(list(STYLES.keys()).index(self.current_style_key))
        self.style_combo.currentIndexChanged.connect(self._on_appearance_changed)

        appearance_row.addWidget(self.theme_combo, 1)
        appearance_row.addWidget(self.style_combo, 1)
        layout.addLayout(appearance_row)

        heading = QLabel('Métricas exibidas')
        heading.setObjectName('sectionHeading')
        layout.addWidget(heading)

        for metric in ('CPU', 'RAM', 'GPU', 'CPU Temp', 'GPU Temp'):
            check = QCheckBox(metric)
            saved = self.settings.value(f'metric_{metric}', metric in ('CPU', 'RAM', 'GPU'), type=bool)
            check.setChecked(saved)
            check.toggled.connect(self.refresh_metric_visibility)
            self.metric_checks[metric] = check
            layout.addWidget(check)

        layout.addStretch()
        layout.addWidget(
            self._button('Ocultar na bandeja', self.hide_to_tray, 'hideButton'),
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        return page

    def _on_appearance_changed(self):
        self.current_theme_key = self.theme_combo.currentData()
        self.current_style_key = self.style_combo.currentData()
        self.settings.setValue('theme', self.current_theme_key)
        self.settings.setValue('style', self.current_style_key)
        self.apply_theme()
        self._move_to_target()
        self.update()

    def apply_theme(self):
        t = THEMES[self.current_theme_key]
        self.lenses.set_colors(t['surface_hover'], t['accent'])
        self.waveform.set_colors(t['accent'], t['muted'])
        for btn in (self.btn_prev, self.btn_play, self.btn_next):
            btn.set_colors(t['text'], t['muted'])
        for art in (self.album_art, self.small_art):
            if hasattr(art, 'set_theme_colors'):
                art.set_theme_colors(t['accent'], t['bg_bottom'])
        if hasattr(self, 'tray'):
            self.tray.setIcon(self._tray_icon(t['bg_top'], t['accent']))

        self.setStyleSheet(f'''
            QWidget {{ color: {t['text']}; font-family: 'Segoe UI'; font-size: 12px; }}
            QFrame {{ background: transparent; border: none; }}
            QLabel#compactTitle {{ font-size: 12px; font-weight: 600; }}
            QLabel#mediaTitle {{ font-size: 21px; font-weight: 700; }}
            QLabel#artist {{ color: {t['muted']}; font-size: 13px; }}
            QLabel#status, QLabel#summary, QLabel#secondary {{ color: {t['muted']}; font-size: 11px; }}
            QLabel#sectionHeading {{ color: {t['text']}; font-size: 14px; font-weight: 650; margin-top: 2px; }}
            QPushButton {{ border: none; color: {t['text']}; background: transparent; }}
            QPushButton#navButton {{ color: {t['muted']}; padding: 7px 13px; border-radius: 16px; font-weight: 600; }}
            QPushButton#navButton:checked {{ color: {t['text']}; background: {t['surface_hover']}; }}
            QPushButton#navButton:hover:!checked {{ color: {t['text']}; background: {t['surface']}; }}
            QPushButton#collapseButton {{ color: {t['muted']}; font-size: 17px; border-radius: 15px; min-width: 28px; min-height: 28px; }}
            QPushButton#collapseButton:hover {{ background: {t['surface_hover']}; }}
            QPushButton#control {{ font-size: 19px; min-width: 36px; min-height: 36px; border-radius: 18px; }}
            QPushButton#control:hover {{ background: {t['surface']}; }}
            QPushButton#control:disabled {{ color: {t['muted']}; }}
            QPushButton#play {{ font-size: 17px; min-width: 42px; min-height: 42px; border-radius: 21px; background: {t['accent']}; color: #091422; }}
            QPushButton#play:hover {{ background: {t['text']}; }}
            QPushButton#play:disabled {{ background: {t['surface']}; color: {t['muted']}; }}
            QPushButton#hideButton {{ text-align: center; background: {t['surface']}; border-radius: 12px; padding: 9px 15px; font-weight: 600; }}
            QPushButton#hideButton:hover {{ background: {t['surface_hover']}; }}
            QComboBox {{
                background: {t['surface']}; border: 1px solid {t['border']};
                border-radius: 10px; padding: 6px 10px; color: {t['text']};
            }}
            QComboBox:hover {{ background: {t['surface_hover']}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background: {t['bg_bottom']}; border: 1px solid {t['border']};
                selection-background-color: {t['surface_hover']}; color: {t['text']};
                outline: 0;
            }}
            QCheckBox {{ color: {t['text']}; spacing: 8px; padding: 1px; }}
            QCheckBox::indicator {{ width: 15px; height: 15px; }}
            QProgressBar {{ border: none; background: {t['bar_bg']}; border-radius: 3px; height: 6px; text-align: center; }}
            QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
            QProgressBar#metricBar {{ background: {t['bar_bg']}; height: 5px; }}
        ''')

    @staticmethod
    def _button(text, callback, name):
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _tray_icon(bg_color='#070b13', accent_color='#6bbcff'):
        pix = QPixmap(48, 48)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg_color))
        painter.drawEllipse(1, 1, 46, 46)
        painter.setBrush(QColor(accent_color))
        painter.drawEllipse(18, 18, 12, 12)
        painter.end()
        return QIcon(pix)

    def select_page(self, index):
        self.pages.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        if self.expanded:
            self._move_to_target()

    def target_geometry(self, expanded):
        screen = QApplication.primaryScreen().availableGeometry()
        if expanded:
            width = min(self.EXPANDED_WIDTH, screen.width() - 20)
            height = self.SETTINGS_HEIGHT if self.pages.currentIndex() == 2 else self.EXPANDED_HEIGHT
        elif self.media:
            width, height = min(self.COMPACT_WIDTH, screen.width() - 20), self.COMPACT_HEIGHT
        else:
            width, height = self.IDLE_WIDTH, self.IDLE_HEIGHT

        top_offset = 10 if self.current_style_key == 'floating' else 0
        x = screen.x() + (screen.width() - width) // 2
        return QRect(x, screen.y() + top_offset, width, height)

    def _move_to_target(self, initial=False):
        target = self.target_geometry(self.expanded)
        if self.animation:
            self.animation.stop()
        if initial or not self.isVisible():
            self.setGeometry(target)
            return
        self.animation = QPropertyAnimation(self, b'geometry', self)
        self.animation.setDuration(310)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(target)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()

    def expand(self):
        self.expanded = True
        self.compact_panel.hide()
        self.expanded_panel.show()
        self._move_to_target()
        self.unattended = 0
        self.hidden_by_user = False
        self.show()
        self.raise_()

    def collapse(self, initial=False):
        self.expanded = False
        self.expanded_panel.hide()
        self.compact_panel.show()
        self.lenses.setVisible(not bool(self.media))
        self.small_art.setVisible(bool(self.media))
        self._move_to_target(initial)
        self.unattended = 0

    def resizeEvent(self, event):
        self.compact_panel.setGeometry(self.rect())
        self.expanded_panel.setGeometry(self.rect())
        super().resizeEvent(event)

    def auto_collapse_tick(self):
        if not self.expanded:
            return
        if self.theme_combo.view().isVisible() or self.style_combo.view().isVisible():
            self.unattended = 0
            return
        if self.frameGeometry().contains(QCursor.pos()):
            self.unattended = 0
        else:
            self.unattended += 1
            if self.unattended >= 10:
                self.collapse()

    @staticmethod
    def _time(seconds):
        seconds = max(0, int(seconds))
        return f'{seconds // 60}:{seconds % 60:02d}'

    def on_media(self, data):
        if self.media == data:
            return
        had_media = bool(self.media)
        self.media = data
        if data:
            title = data['title']
            artist = data['artist'] or 'Sem artista informado'
            generic = bool(data.get('generic'))
            self.compact_title.setText(self.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, 190))
            self.title_label.setText(self.title_label.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, 285))
            self.title_label.setToolTip(title)
            self.artist_label.setText(self.artist_label.fontMetrics().elidedText(artist, Qt.TextElideMode.ElideRight, 285))
            self.artist_label.setToolTip(artist)
            source = data['source'].lower()
            if 'spotify' in source:
                provider = 'Spotify'
            elif any(browser in source for browser in ('chrome', 'edge', 'firefox')):
                provider = 'Navegador'
            else:
                provider = 'Mídia do Windows'
            if generic:
                device = data.get('device', 'Saída do Windows')
                self.status_label.setText(self.status_label.fontMetrics().elidedText(device, Qt.TextElideMode.ElideRight, 285))
            else:
                self.status_label.setText(provider + ('  ·  Tocando' if data['playing'] else '  ·  Pausado'))
            self.btn_play.set_playing(data['playing'])
            self.btn_prev.setEnabled(not generic and data['can_previous'])
            self.btn_next.setEnabled(not generic and data['can_next'])
            for button in (self.btn_prev, self.btn_play, self.btn_next):
                button.setVisible(not generic)
            self.generic_hint.setVisible(generic)
            duration = data.get('duration', 0)
            position = data.get('position', 0)
            if generic:
                self.progress.setValue(min(1000, int(data.get('level', 0) * 1000)))
                self.elapsed_label.setText('Nível de áudio')
                self.remaining_label.setText('')
            else:
                self.progress.setValue(min(1000, int(position * 1000 / duration)) if duration else 0)
                self.elapsed_label.setText(self._time(position) if duration else '0:00')
                self.remaining_label.setText(f'-{self._time(duration - position)}' if duration else '—')
        else:
            self.compact_title.setText('')
            self.title_label.setText('Nenhuma reprodução detectada')
            self.artist_label.setText('Abra Spotify ou YouTube')
            self.status_label.setText('Aguardando mídia do Windows')
            self.btn_play.set_playing(False)
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            for button in (self.btn_prev, self.btn_play, self.btn_next):
                button.show()
            self.generic_hint.hide()
            self.progress.setValue(0)
            self.elapsed_label.setText('0:00')
            self.remaining_label.setText('—')
        self.btn_play.setEnabled(bool(data and not data.get('generic')))
        self.waveform.set_playing(bool(data and data['playing']))
        art = data['cover'] if data else None
        if art != self.last_art:
            self.last_art = art
            self.album_art.set_data(art)
            self.small_art.set_data(art)
        if had_media != bool(data):
            self.lenses.setVisible(not bool(data))
            self.small_art.setVisible(bool(data))
            if not self.expanded:
                self._move_to_target()

    def on_media_error(self, message):
        print('[mídia]', message)
        if self.media is None:
            self.status_label.setText('Integração de mídia indisponível')

    def on_metrics(self, metrics):
        self.latest_metrics = metrics
        self.summary_label.setText(f"CPU {metrics.get('CPU', '—')}   RAM {metrics.get('RAM', '—')}")
        for name, (_row, value, bar) in self.metric_labels.items():
            raw = metrics.get(name, '—')
            value.setText(raw)
            try:
                bar.setValue(max(0, min(100, int(float(raw.rstrip('%°C'))))))
            except ValueError:
                bar.setValue(0)

    def refresh_metric_visibility(self, *_):
        for name, (row, _value, _bar) in self.metric_labels.items():
            checked = self.metric_checks[name].isChecked()
            row.setVisible(checked)
            self.settings.setValue(f'metric_{name}', checked)

    def hide_to_tray(self):
        self.hidden_by_user = True
        self.hide()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.hidden_by_user = False
            self.show()
            self.raise_()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = THEMES[self.current_theme_key]
        style = self.current_style_key
        width, height = self.width(), self.height()
        radius = 28 if self.expanded else (19 if self.media else 15)

        path = QPainterPath()
        if style == 'floating':
            path.addRoundedRect(1, 1, width - 2, height - 2, radius, radius)
        else:
            path.moveTo(1, 0)
            path.lineTo(width - 1, 0)
            path.lineTo(width - 1, height - radius)
            path.quadTo(width - 1, height - 1, width - radius, height - 1)
            path.lineTo(radius, height - 1)
            path.quadTo(1, height - 1, 1, height - radius)
            path.closeSubpath()

        c_top = QColor(t['bg_top'])
        c_bottom = QColor(t['bg_bottom'])
        if style == 'glass':
            c_top.setAlpha(215)
            c_bottom.setAlpha(225)

        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, c_top)
        gradient.setColorAt(1, c_bottom)
        painter.fillPath(path, gradient)

        if style == 'neon':
            pen = QPen(QColor(t['accent']), 1.5)
        elif style == 'glass':
            pen = QPen(QColor(255, 255, 255, 42), 1)
        else:
            pen = QPen(QColor(t['border']), 1)

        painter.setPen(pen)
        painter.drawPath(path)

    def quit_app(self):
        self._quit = True
        self.tray.hide()
        self.media_worker.stop()
        self.metrics_worker.stop()
        self.media_worker.wait(3500)
        self.metrics_worker.wait(3500)
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._quit:
            event.accept()
        elif self.tray.isVisible():
            self.hide_to_tray()
            event.ignore()
        else:
            self.quit_app()
            event.accept()