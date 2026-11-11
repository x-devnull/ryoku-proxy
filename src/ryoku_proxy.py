#!/usr/bin/python3
"""Ryoku Proxy ED 1.0 — native bilingual Qt6 Wayland network control."""
from __future__ import annotations

from collections import deque
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal, QPointF, QUrl
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF, QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QStackedWidget, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget, QHeaderView, QSizePolicy,
)

from profile_store import (candidates, delete_password, load_store, new_profile,
                           parse_proxy_url, save_store, validate_profile)
from network_probe import probe
from i18n import tr, LANG, ui_error
from monitoring import (api_snapshot, get_token, save_token, delete_token,
                        pretty_size, tun_counters)

HELPER = '/usr/lib/ryoku-proxy/ryoku-proxy-helper'
CONFIG = '/etc/sing-box/config.json'

# Ryoku: restrained charcoal, precise hairlines, mono annotations, serif headlines.
STYLES = r'''
* {font-family: 'Space Grotesk', 'Noto Sans', 'DejaVu Sans'; font-size: 14px; color: #ced3d7;}
QMainWindow, QWidget#root, QWidget#workspace, QWidget#formRoot, QDialog,
QScrollArea#scroll {background: #0b0d0e; color: #ced3d7;}
QFrame#sidebar, QWidget#sidebarBody {background: #101213; border-right: 1px solid #363a3c;}
QFrame#topbar {background: #0b0d0e; border-bottom: 1px solid #363a3c;}
QFrame#card {background: #101315; border: 1px solid #414546; border-radius: 8px;}
QFrame#panel {background: #151719; border: 1px solid #414546; border-radius: 8px;}
QFrame#note {background: #111416; border: 1px solid #393c3e; border-radius: 2px;}
QLabel#brand {font-family: 'DejaVu Sans Mono'; font-size: 12px; font-weight: bold;
              letter-spacing: 2px; color: #f0f0eb;}
QLabel#micro {font-family: 'DejaVu Sans Mono'; font-size: 11px;
              letter-spacing: 2px; color: #7e898e;}
QLabel#smallcap {font-family: 'DejaVu Sans Mono'; font-size: 12px;
                 letter-spacing: 1px; color: #9da7af;}
QLabel#title {font-family: 'Space Grotesk', 'Noto Sans', sans-serif;
              font-size: 32px; color: #f1f0ec;}
QLabel#heading {font-family: 'Space Grotesk', 'Noto Sans', sans-serif;
                font-size: 23px; color: #f0efec;}
QLabel#section {font-family: 'DejaVu Sans Mono'; font-size: 11px;
                font-weight: bold; letter-spacing: 1px; color: #d7dade;}
QLabel#muted {color: #8b959e; font-size: 12px;}
QLabel#value {font-family: 'DejaVu Sans Mono'; color: #ededeb; font-size: 18px;}
QLabel#statusOk {color: #b8d3bf; font-family: 'DejaVu Sans Mono'; font-size: 11px;}
QLabel#statusBad {color: #dfacac; font-family: 'DejaVu Sans Mono'; font-size: 11px;}
QLabel#statusWarn {color: #cfbd99; font-family: 'DejaVu Sans Mono'; font-size: 11px;}
QLineEdit, QComboBox, QSpinBox, QTextEdit {background: #151719; border: 1px solid #494d4f;
    color: #e4e5e3; border-radius: 8px; padding: 8px; min-height: 22px;
    selection-background-color: #6d7378;}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {border-color: #d5d6d5;}
QComboBox QAbstractItemView {background: #171a1b; color: #f4f4f2; selection-background-color: #414548;}
QPushButton {background: #17191b; color: #cbd0d4; border: 1px solid #444849;
    border-radius: 8px; min-height: 23px; padding: 7px 14px;
    font-family: 'DejaVu Sans Mono'; font-size: 12px; letter-spacing: 1px;}
QPushButton:hover {background: #272a2c; border-color: #858a8d;}
QPushButton:focus {border-color: #dedfdd;}
QPushButton:pressed {background: #36393b;}
QPushButton:disabled {color: #646a6e; border-color: #313536; background: #131516;}
QPushButton#primary {background: #dedfdd; color: #202426; border-color: #ebebe8;}
QPushButton#primary:hover {background: #f7f7f3;}
QPushButton#danger {color: #d8a7a7;}
QPushButton#nav {text-align: left; border-color: transparent; background: transparent;
  font-size: 12px; letter-spacing: 0px; font-family: 'DejaVu Sans Mono'; padding: 8px 12px;}
QPushButton#nav:hover {background: #222526;}
QPushButton#nav[active="true"] {background: #2b2e30; border: 1px solid #62676a; color: #f3f3f2;}
QPushButton#quiet {border: 0; background: transparent; color: #aab1b8;}
QListWidget {background: transparent; border: 0; outline: 0;}
QListWidget::item {background: #151719; border: 1px solid #393d3e; padding: 12px;
                    margin: 2px 0 5px 0; min-height: 27px; color: #c8cdd1;}
QListWidget::item:selected {background: #2c2f31; border: 1px solid #a1a3a4; color: #fff;}
QListWidget::item:hover {background: #252829;}
QCheckBox {spacing: 8px;}
QCheckBox::indicator {width: 15px; height: 15px; background: #202324; border: 1px solid #82878a; border-radius: 2px;}
QCheckBox::indicator:checked {background: #dedfdd; border: 4px solid #555f65;}
QCheckBox:focus {color: #ffffff;}
QTableWidget {background: #101315; color: #d4d8da; border: 1px solid #414546;
  gridline-color: #303536; selection-background-color: #303537; outline: 0;}
QTableWidget::item {padding: 7px;}
QHeaderView::section {background: #171a1c; color: #9ea7ad; border: 0;
                      border-right: 1px solid #303536; border-bottom: 1px solid #484c4e;
                      padding: 9px; font-family: 'DejaVu Sans Mono'; font-size: 12px;}
QMenu {background: #171a1b; border: 1px solid #515657; color: #d5d8d7;}
QMenu::item {padding: 7px 20px;}
QMenu::item:selected {background: #3a3e40;}
QScrollBar:vertical {background: #101213; width: 8px;}
QScrollBar::handle:vertical {background: #3c4245; min-height: 25px;}
QScrollBar::add-line, QScrollBar::sub-line {height: 0;}
'''


def label(message, kind=None, wrap=True):
    item = QLabel(message)
    item.setTextFormat(Qt.TextFormat.PlainText)
    if kind:
        item.setObjectName(kind)
    item.setWordWrap(wrap)
    return item


def btn(title, callback, kind=None):
    item = QPushButton(title.replace('&', '&&'))
    item.setProperty('requiresProfile', getattr(callback, '__name__', '') in
                     ('connect_selected', 'test_selected', 'edit_profile', 'remove_profile', 'allow_backup'))
    if kind:
        item.setObjectName(kind)
    item.clicked.connect(callback)
    return item


def card(title=None):
    container = QFrame()
    container.setObjectName('card')
    layout = QVBoxLayout(container)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(11)
    if title:
        layout.addWidget(label(title.upper(), 'section'))
    return container, layout


def icon_image(running=False, guarded=False):
    image = QPixmap(64, 64)
    image.fill(Qt.GlobalColor.transparent)
    paint = QPainter(image)
    paint.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint.setBrush(QColor('#0c0d0e'))
    paint.setPen(QPen(QColor('#b0b6b8'), 2))
    paint.drawRoundedRect(5, 5, 53, 53, 5, 5)
    paint.setPen(QPen(QColor('#f0f0ee'), 3))
    paint.setFont(QFont('DejaVu Serif', 29))
    paint.drawText(16, 44, 'R')
    paint.setPen(Qt.PenStyle.NoPen)
    paint.setBrush(QColor('#a9c9b4' if running and guarded else '#d1b99d' if running else '#b38d8d'))
    paint.drawEllipse(46, 46, 13, 13)
    paint.end()
    return QIcon(image)


class TraceGraph(QWidget):
    """Subtle Ryoku-style line graph for TUN RX/TX rates in bytes/s."""
    def __init__(self):
        super().__init__()
        self.rx = deque([0.0] * 60, maxlen=60)
        self.tx = deque([0.0] * 60, maxlen=60)
        self.setMinimumHeight(185)

    def push(self, rx, tx):
        self.rx.append(float(rx))
        self.tx.append(float(tx))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(r, QColor('#0e1113'))
        painter.setPen(QPen(QColor('#272c2e'), 1))
        for n in range(5):
            y = r.top() + n * r.height() / 4
            painter.drawLine(r.left(), int(y), r.right(), int(y))
        cap = max(1000, max(self.rx), max(self.tx)) * 1.15
        for values, color in [(self.rx, '#d8dad8'), (self.tx, '#8a989f')]:
            points = []
            for i, v in enumerate(values):
                x = r.left() + i * r.width() / max(1, len(values) - 1)
                y = r.bottom() - v / cap * (r.height() - 14)
                points.append(QPointF(x, y))
            painter.setPen(QPen(QColor(color), 1.5))
            painter.drawPolyline(QPolygonF(points))
        painter.end()


class Worker(QThread):
    done = Signal(str, bool, object, str)

    def __init__(self, action, payload=None, parent=None):
        super().__init__(parent)
        self.action = action
        self.payload = payload

    def run(self):
        action = self.action
        try:
            if action == 'local-networks':
                from routing import local_networks
                self.done.emit(action, True, {'networks': local_networks()}, '')
                return
            if action == 'status':
                def service(name, operation):
                    return subprocess.run(['/usr/bin/systemctl', operation, '--quiet', name],
                                          capture_output=True, timeout=5).returncode == 0
                try:
                    changed = Path(CONFIG).stat().st_mtime_ns
                except OSError:
                    changed = None
                result = {
                    'running': service('sing-box', 'is-active'),
                    'autostart': service('sing-box', 'is-enabled'),
                    'firewall_service': service('ryoku-proxy-killswitch.service', 'is-active'),
                    'firewall_autostart': service('ryoku-proxy-killswitch.service', 'is-enabled'),
                    'firewall_trial': Path('/run/ryoku-proxy-killswitch-trial').exists(),
                    'mtime_ns': changed,
                    'passwordless': subprocess.run(['/usr/bin/pkcheck', '--action-id',
                        'org.ryoku.proxy.manage', '--process', str(os.getpid())],
                        capture_output=True, timeout=5).returncode == 0
                        if Path('/usr/bin/pkcheck').exists() else False,
                }
                self.done.emit(action, True, result, '')
                return
            if action == 'snapshot':
                result = {}
                try:
                    result['tun'] = tun_counters()
                except (ValueError, OSError):
                    result['tun'] = None
                try:
                    token = get_token()
                    result['api'] = api_snapshot(token, timeout=2.5) if token else None
                except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as e:
                    result['api'] = None
                    result['api_error'] = str(e)[:120]
                self.done.emit(action, True, result, '')
                return
            if action == 'diag':
                env = {k: v for k, v in os.environ.items() if k.lower() not in
                       ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
                tls = subprocess.run(['/usr/bin/curl', '-4', '--noproxy', '*', '--silent',
                                      '--output', '/dev/null', '--max-time', '9',
                                      '--write-out', '%{time_total}', 'https://example.com/'],
                                     capture_output=True, text=True, timeout=12, env=env)
                elapsed = None
                if tls.returncode == 0:
                    try:
                        elapsed = round(float(tls.stdout.strip()) * 1000)
                    except ValueError:
                        pass
                dns_label = 'NOT AVAILABLE'
                try:
                    dns = subprocess.run(['/usr/bin/resolvectl', 'dns', 'tun0'],
                                         capture_output=True, text=True, timeout=5)
                    if dns.returncode == 0:
                        dns_label = ' '.join(dns.stdout.strip().split())[:130]
                    else:
                        dns_label = 'NO PER-LINK DNS'
                except OSError:
                    pass
                self.done.emit(action, True, {'https_ms': elapsed, 'dns': dns_label}, '')
                return
            if action == 'ip':
                env = {k: v for k, v in os.environ.items() if k.lower() not in
                       ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
                result = subprocess.run(['/usr/bin/curl', '-4', '--fail', '--silent', '--show-error',
                                         '--noproxy', '*', '--connect-timeout', '5',
                                         '--max-time', '10', 'https://api.ipify.org'],
                                        capture_output=True, text=True, timeout=13, env=env)
                if result.returncode:
                    raise RuntimeError('Public IPv4 check failed: ' + result.stderr[-120:])
                ip = result.stdout.strip()
                ipaddress.IPv4Address(ip)
                self.done.emit(action, True, {'ip': ip}, '')
                return
            if action == 'test':
                ms = probe(self.payload)
                self.done.emit(action, True, {'ms': ms, 'transport': self.payload['protocol']}, '')
                return
            if action == 'logs':
                result = subprocess.run(['/usr/bin/journalctl', '-u', 'sing-box', '-n', '120',
                                         '--no-pager', '--output=short'], capture_output=True,
                                        text=True, timeout=10)
                if result.returncode:
                    raise RuntimeError(result.stderr[-250:] or 'Journal unavailable')
                self.done.emit(action, True, {'log': result.stdout[-22000:]}, '')
                return
            payload = json.dumps(self.payload, ensure_ascii=False) if self.payload is not None else ''
            result = subprocess.run(['/usr/bin/pkexec', HELPER, action], input=payload,
                                    capture_output=True, text=True, timeout=145)
            rows = [x.strip() for x in result.stdout.splitlines() if x.strip()]
            try:
                response = json.loads(rows[-1]) if rows else None
            except json.JSONDecodeError:
                response = None
            if response and response.get('ok'):
                self.done.emit(action, True, response.get('data') or {}, response.get('message', 'Done'))
                return
            if result.returncode in (126, 127):
                raise RuntimeError(tr('authentication_error'))
            raise RuntimeError((response or {}).get('message') or result.stderr.strip() or 'Helper failed')
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            self.done.emit(action, False, None, str(e)[:1000])



class ProfileEditor(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle('RYOKU / ' + tr('editor'))
        self.setMinimumWidth(420)
        self.resize(520, 590)
        self.original = dict(profile)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(13)
        root.addWidget(label('— ' + tr('editor'), 'smallcap'))
        root.addWidget(label(tr('server'), 'heading'))
        form = QFormLayout()
        form.setSpacing(9)
        self.name = QLineEdit(profile['name'])
        self.host = QLineEdit(profile['host'])
        self.username = QLineEdit(profile['username'])
        self.password = QLineEdit(profile['password'])
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.http = QSpinBox(); self.http.setRange(0,65535); self.http.setValue(profile['http_port'])
        self.socks = QSpinBox(); self.socks.setRange(0,65535); self.socks.setValue(profile['socks_port'])
        self.preferred = QComboBox()
        for key, choice in [('auto','auto'), ('http','HTTP / HTTPS'), ('socks5','SOCKS5')]:
            self.preferred.addItem(tr('auto') if key=='auto' else choice, key)
        self.preferred.setCurrentIndex(max(0,self.preferred.findData(profile['preferred'])))
        self.tls = QCheckBox(tr('http_tls')); self.tls.setChecked(profile['http_tls'])
        self.udp = QCheckBox(tr('socks_udp')); self.udp.setChecked(profile['socks_udp'])
        for key, widget in [('name',self.name), ('host',self.host), ('user',self.username),
                            ('password',self.password), ('http_port',self.http), ('socks_port',self.socks),
                            ('priority',self.preferred)]:
            form.addRow(tr(key),widget)
        root.addLayout(form)
        show = QCheckBox(tr('show_password'))
        show.toggled.connect(lambda on: self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        root.addWidget(show)
        root.addWidget(self.tls)
        root.addWidget(self.udp)
        root.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(btn(tr('cancel'),self.reject))
        actions.addWidget(btn(tr('save'),self.accept,'primary'))
        root.addLayout(actions)
        self.profile = None

    def accept(self):
        p = dict(self.original)
        p.update(name=self.name.text(), host=self.host.text(), username=self.username.text(),
                 password=self.password.text(), http_port=self.http.value(),
                 socks_port=self.socks.value(), preferred=self.preferred.currentData(),
                 http_tls=self.tls.isChecked(), socks_udp=self.udp.isChecked())
        if p['password']:
            p['secret_missing'] = False
        try:
            self.profile = validate_profile(p)
        except ValueError as exc:
            QMessageBox.warning(self,tr('invalid'),ui_error(exc))
            return
        super().accept()


class Window(QMainWindow):
    NAV_KEYS = ['overview','profiles','security','routing','monitor','events','about']
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Ryoku Proxy — ' + tr('system'))
        self.setMinimumSize(680, 510)
        self.resize(1230, 810)
        self.data = load_store()
        self.selected_id = self.data.get('active_id') or (self.data['profiles'][0]['id'] if self.data['profiles'] else None)
        self.running = False
        self.autostart = False
        self.passwordless = False
        self.firewall_active = False
        self.firewall_enabled = False
        self.firewall_verified = None
        self.firewall_trial = False
        self.public_ip = '—'
        self.health_ok = None
        self.config_mtime = None
        self.active_transport = '—'
        self.api_data = None
        self.api_error = None
        self.pending_token = None
        self.pending_profile_id = None
        self.routing_loaded = False
        self.jobs = {}
        self._profile_signature = None
        self._tray_signature = None
        self.busy = False
        self.exiting = False
        self.last_counters = None
        self.current_page = 0
        self.last_test_time = 0
        self.tun_rx = 0
        self.tun_tx = 0
        self.tray_supported = QSystemTrayIcon.isSystemTrayAvailable()
        self.setup_ui()
        self.setup_tray()
        self.refresh_profile_lists()
        self.refresh_ui()
        self.run_job('status')
        self.run_job('snapshot')
        self.t_status = QTimer(self); self.t_status.timeout.connect(lambda:self.run_job('status')); self.t_status.start(10000)
        self.t_snapshot = QTimer(self); self.t_snapshot.timeout.connect(self.poll_snapshot); self.t_snapshot.start(3000)
        self.t_health = QTimer(self); self.t_health.timeout.connect(lambda:self.check_ip(True)); self.t_health.start(30000)
        QTimer.singleShot(1800,lambda:self.check_ip(True))
        QTimer.singleShot(2600,lambda:self.run_job('diag'))

    def poll_snapshot(self):
        if self.isVisible():
            self.run_job('snapshot')
        else:
            # Rates need a fresh baseline after returning from the tray.
            self.last_counters = None

    def setup_ui(self):
        base = QWidget(); base.setObjectName('root'); self.setCentralWidget(base)
        outer = QHBoxLayout(base); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        self.sidebar = QScrollArea(); self.sidebar.setObjectName('sidebar'); self.sidebar.setFixedWidth(232)
        self.sidebar.setWidgetResizable(True)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_body = QWidget(); sidebar_body.setObjectName('sidebarBody')
        self.sidebar.setWidget(sidebar_body)
        left = QVBoxLayout(sidebar_body); left.setContentsMargins(15,20,15,15); left.setSpacing(7)
        brand_card, bc = card(); bc.addWidget(label('R    RYOKU', 'brand')); bc.addWidget(label('    '+tr('network_system_control'),'micro'))
        left.addWidget(brand_card)
        left.addSpacing(16)
        self.nav_buttons = {}
        for i,key in enumerate(self.NAV_KEYS):
            if i in (0,2,4,6):
                left.addWidget(label('0'+str((i//2)+1)+'   '+tr(['connection','control','network_traffic','system'][i//2]),'micro'))
            button = btn(tr(key),lambda checked=False,idx=i:self.show_page(idx),'nav')
            self.nav_buttons[i] = button
            left.addWidget(button)
        left.addStretch(1)
        self.side_status = label('SING-BOX  —','smallcap'); left.addWidget(self.side_status)
        self.side_firewall = label(tr('kill_switch')+'  —','smallcap'); left.addWidget(self.side_firewall)
        left.addWidget(label('ED 1.0     //     RYOKU SYSTEMS','micro'))
        outer.addWidget(self.sidebar)
        right = QWidget(); right.setObjectName('workspace')
        right_layout = QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(0)
        top = QFrame(); top.setObjectName('topbar')
        top_l = QHBoxLayout(top); top_l.setContentsMargins(23,12,23,12)
        self.breadcrumb = label(tr('network_overview'),'micro'); top_l.addWidget(self.breadcrumb)
        top_l.addStretch()
        self.top_status = label('◌  '+tr('loading'),'smallcap'); top_l.addWidget(self.top_status)
        top_l.addWidget(btn(tr('refresh'),self.refresh_all))
        right_layout.addWidget(top)
        self.pages = QStackedWidget(); right_layout.addWidget(self.pages,1)
        bottom = QFrame(); bottom.setObjectName('topbar')
        bottom_l = QHBoxLayout(bottom); bottom_l.setContentsMargins(24,11,24,11)
        self.status_line = label('○  '+tr('ready'),'smallcap'); bottom_l.addWidget(self.status_line)
        bottom_l.addStretch()
        bottom_l.addWidget(label('RYOKU / WAYLAND / SING-BOX','micro'))
        right_layout.addWidget(bottom)
        outer.addWidget(right,1)
        self.build_overview()
        self.build_profiles()
        self.build_security()
        self.build_routing()
        self.build_monitor()
        self.build_events()
        self.build_about()
        self.show_page(0)

    def page(self, key, subtitle):
        page = QWidget(); page.setObjectName('workspace')
        scroll = QScrollArea(); scroll.setObjectName('scroll'); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget(); holder.setObjectName('workspace')
        root = QVBoxLayout(holder); root.setContentsMargins(25,24,25,27); root.setSpacing(14)
        root.addWidget(label('— '+tr('network_'+key),'smallcap'))
        root.addWidget(label(tr(key),'title'))
        root.addWidget(label(tr(subtitle),'muted'))
        scroll.setWidget(holder)
        self.pages.addWidget(scroll)
        return root

    def show_page(self,index):
        self.current_page=index
        if index == 4 and hasattr(self, 'graph'):
            self.run_job('snapshot')
        self.pages.setCurrentIndex(index)
        self.breadcrumb.setText(tr('network_'+self.NAV_KEYS[index]))
        for k,item in self.nav_buttons.items():
            item.setProperty('active','true' if k==index else 'false')
            item.style().unpolish(item); item.style().polish(item)
        if index==5:
            self.run_job('logs')
        if index==3:
            self.run_job('routing-read')

    def metric_card(self, title_key, value='—'):
        c,lyt = card(); lyt.addWidget(label(tr(title_key),'micro'))
        number = label(value,'value'); lyt.addWidget(number)
        return c,number

    def build_overview(self):
        root=self.page('overview','overview_hint')
        c,lyt=card(tr('active_session'))
        self.primary_status=label('◌  '+tr('not_checked'),'statusWarn'); lyt.addWidget(self.primary_status)
        self.primary_profile=label(tr('no_profile'),'heading'); lyt.addWidget(self.primary_profile)
        self.primary_details=label(tr('add_or_import'),'muted'); lyt.addWidget(self.primary_details)
        root.addWidget(c)
        self.overview_metrics=QGridLayout(); self.overview_metrics.setSpacing(9)
        self.ov_widgets=[]
        for key in ('public_ip','transport','route_tun','kill_switch'):
            w,val=self.metric_card(key); self.ov_widgets.append((w,val))
        for idx,(w,_) in enumerate(self.ov_widgets):
            self.overview_metrics.addWidget(w,0,idx)
        root.addLayout(self.overview_metrics)
        actions = QHBoxLayout()
        actions.addWidget(btn(tr('connect_profile'),self.connect_selected,'primary'))
        actions.addWidget(btn(tr('test'),self.test_selected))
        actions.addWidget(btn(tr('import_current'),self.import_active))
        root.addLayout(actions)
        root.addWidget(label('— '+tr('available_profiles'),'smallcap'))
        self.profile_list=QListWidget(); self.profile_list.setMinimumHeight(135)
        self.profile_list.setMaximumHeight(230)
        self.profile_list.currentItemChanged.connect(lambda item,_:self.change_selection(item))
        self.profile_list.itemDoubleClicked.connect(lambda _:self.connect_selected())
        root.addWidget(self.profile_list)
        row=QHBoxLayout()
        row.addWidget(btn(tr('add'),self.add_profile))
        row.addWidget(btn(tr('edit'),self.edit_profile))
        row.addWidget(btn(tr('import_url'),self.import_proxy_url))
        root.addLayout(row)
        note, nl=card(tr('network_snapshot'))
        self.overview_snapshot=label('—','smallcap'); nl.addWidget(self.overview_snapshot)
        root.addWidget(note)
        root.addStretch()

    def build_profiles(self):
        root=self.page('profiles','profiles_hint')
        row=QHBoxLayout()
        row.addWidget(btn(tr('add'),self.add_profile,'primary'))
        row.addWidget(btn(tr('import_url'),self.import_proxy_url))
        row.addWidget(btn(tr('import_current'),self.import_active))
        root.addLayout(row)
        self.profile_list_large=QListWidget(); self.profile_list_large.setMinimumHeight(260)
        self.profile_list_large.currentItemChanged.connect(lambda item,_:self.change_selection(item))
        self.profile_list_large.itemDoubleClicked.connect(lambda _:self.edit_profile())
        root.addWidget(self.profile_list_large)
        row=QHBoxLayout()
        row.addWidget(btn(tr('connect'),self.connect_selected,'primary'))
        row.addWidget(btn(tr('edit'),self.edit_profile))
        row.addWidget(btn(tr('test'),self.test_selected))
        row.addWidget(btn(tr('delete'),self.remove_profile,'danger'))
        root.addLayout(row)
        root.addWidget(label(tr('profiles_secret'),'muted'))
        root.addStretch()

    def build_security(self):
        root=self.page('security','firewall_hint')
        c,lyt=card(tr('kill_switch'))
        self.firewall_label=label('◌ '+tr('not_checked'),'statusWarn'); lyt.addWidget(self.firewall_label)
        lyt.addWidget(label(tr('firewall_trial_info'),'muted'))
        lyt.addWidget(label(tr('firewall_permanent'),'muted'))
        lyt.addWidget(label(tr('backup_hint'),'muted'))
        row=QHBoxLayout()
        row.addWidget(btn(tr('firewall_trial'),self.enable_firewall,'primary'))
        row.addWidget(btn(tr('firewall_confirm'),self.confirm_firewall))
        lyt.addLayout(row)
        row2=QHBoxLayout()
        row2.addWidget(btn(tr('firewall_disable'),self.disable_firewall,'danger'))
        row2.addWidget(btn(tr('firewall_verify'),lambda:self.run_job('fw-verify')))
        lyt.addLayout(row2)
        lyt.addWidget(btn(tr('backup_allow'),self.allow_backup))
        root.addWidget(c)
        note,nl=card(tr('emergency'))
        nl.addWidget(label(tr('emergency_hint'),'smallcap'))
        cmd=QLineEdit('sudo systemctl disable --now ryoku-proxy-killswitch.service ; sudo nft delete table inet ryoku_proxy')
        cmd.setReadOnly(True); cmd.setCursorPosition(0); nl.addWidget(cmd)
        nl.addWidget(label(tr('firewall_warning'),'muted'))
        root.addWidget(note)
        svc,sl=card(tr('network_service'))
        self.service_status=label('sing-box: —','smallcap'); sl.addWidget(self.service_status)
        actions=QHBoxLayout()
        actions.addWidget(btn(tr('autostart'),lambda:self.run_job('start')))
        actions.addWidget(btn(tr('stop_singbox'),self.stop_singbox,'danger'))
        sl.addLayout(actions)
        root.addWidget(svc)
        access,aa=card(tr('access_control'))
        self.access_label=label(tr('passwordless_disabled'),'statusWarn')
        aa.addWidget(self.access_label)
        aa.addWidget(label(tr('passwordless_info'),'muted'))
        root.addWidget(access)
        root.addStretch()

    def build_routing(self):
        root=self.page('routing','routing_hint')
        c,lyt=card(tr('routing_entries'))
        lyt.addWidget(label(tr('routing_examples'),'muted'))
        self.routing_edit=QTextEdit(); self.routing_edit.setPlaceholderText(tr('routing_examples'))
        self.routing_edit.setMinimumHeight(235)
        self.routing_edit.setFontFamily('DejaVu Sans Mono')
        lyt.addWidget(self.routing_edit)
        row=QHBoxLayout()
        row.addWidget(btn(tr('routing_local'),lambda:self.run_job('local-networks')))
        row.addWidget(btn(tr('routing_save'),self.save_routing,'primary'))
        row.addWidget(btn(tr('routing_refresh'),lambda:self.run_job('routing-read')))
        lyt.addLayout(row)
        lyt.addWidget(label(tr('routing_note'),'muted'))
        root.addWidget(c)
        info,nl=card(tr('diagnostics'))
        nl.addWidget(label(tr('routing_mark'),'muted'))
        nl.addWidget(label(tr('firewall_warning'),'muted'))
        root.addWidget(info)
        root.addStretch()

    def build_monitor(self):
        root=self.page('monitor','monitor_hint')
        c,lyt=card(tr('network_traffic'))
        self.metrics_grid=QGridLayout(); self.metrics_grid.setSpacing(9)
        self.metric_widgets=[]
        for key in ('rx','tx','active_flows','session_total'):
            w,v=self.metric_card(key); self.metric_widgets.append((w,v))
        for idx,(w,_) in enumerate(self.metric_widgets): self.metrics_grid.addWidget(w,0,idx)
        lyt.addLayout(self.metrics_grid)
        self.graph=TraceGraph(); self.graph.setMinimumHeight(140)
        lyt.addWidget(self.graph)
        lyt.addWidget(label(tr('graph_hint'),'muted'))
        self.monitor_diag=label('—','smallcap'); lyt.addWidget(self.monitor_diag)
        root.addWidget(c)
        api,al=card()
        self.api_label=label(tr('api_off'),'statusWarn'); al.addWidget(self.api_label)
        # Vertical actions fit narrow windows, unlike the old single long row.
        row=QHBoxLayout()
        row.addWidget(btn(tr('api_enable'),self.enable_monitor))
        row.addWidget(btn(tr('api_disable'),lambda:self.run_job('monitor-disable')))
        al.addLayout(row)
        root.addWidget(api)
        cc,cl=card(tr('active_flows'))
        self.connections=QTableWidget(0,5)
        self.connections.setHorizontalHeaderLabels([tr(k) for k in ('destination','protocol','process','down','up')])
        for i,width in enumerate((245,95,230,100,100)):
            self.connections.setColumnWidth(i,width)
        self.connections.horizontalHeader().setStretchLastSection(False)
        self.connections.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.connections.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.connections.setHorizontalHeaderLabels([tr(k) for k in ('destination','protocol','process','down','up')])
        self.connections.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.connections.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.connections.verticalHeader().hide()
        self.connections.setMinimumHeight(270)
        self.connections.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        cl.addWidget(self.connections)
        root.addWidget(cc)
        root.addStretch()
        self._metric_columns=4

    def build_events(self):
        root=self.page('events','events_hint')
        row=QHBoxLayout()
        row.addWidget(btn(tr('log_refresh'),lambda:self.run_job('logs'),'primary'))
        row.addWidget(btn(tr('check_ip'),lambda:self.check_ip(False)))
        row.addStretch()
        root.addLayout(row)
        self.events_text=QTextEdit(); self.events_text.setReadOnly(True)
        self.events_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.events_text.setMinimumHeight(390); self.events_text.setPlainText(tr('loading'))
        self.events_text.setFontFamily('DejaVu Sans Mono')
        root.addWidget(self.events_text)
        root.addStretch()

    def build_about(self):
        root=self.page('about','about_hint')
        c,lyt=card(tr('project'))
        lyt.addWidget(label('RYOKU PROXY / ED 1.0','heading'))
        for key,value in [('author','x_devnull'),('release','1.0.0'),('license','MIT'),
                          ('source_url','https://github.com/x-devnull/ryoku-proxy')]:
            lyt.addWidget(label(tr(key),'micro'))
            lyt.addWidget(label(value,'value'))
        lyt.addWidget(btn(tr('url_open'),lambda:QDesktopServices.openUrl(QUrl('https://github.com/x-devnull/ryoku-proxy'))))
        lyt.addWidget(label('ED 1.0 · Qt 6 / Wayland','muted'))
        root.addWidget(c)
        root.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sidebar.setFixedWidth(175 if self.width()<920 else 232)
        # Reflow metric cards at 1, 2 or 4 columns; monitor remains vertically scrollable.
        columns=1 if self.width()<740 else 2 if self.width()<1150 else 4
        if hasattr(self,'metrics_grid') and columns!=self._metric_columns:
            for idx,(w,_) in enumerate(self.metric_widgets):
                self.metrics_grid.addWidget(w,idx//columns,idx%columns)
            self._metric_columns=columns
        if hasattr(self,'overview_metrics'):
            for idx,(w,_) in enumerate(self.ov_widgets):
                self.overview_metrics.addWidget(w,idx//columns,idx%columns)

    def selected(self):
        return next((x for x in self.data['profiles'] if x['id']==self.selected_id),None)

    def active_confirmed(self):
        return bool(self.running and self.data.get('active_id') and
                    self.config_mtime is not None and self.data.get('active_mtime_ns')==self.config_mtime)

    def refresh_profile_lists(self):
        signature = (self.selected_id, self.active_confirmed(), self.data.get('active_id'),
                     tuple((p['id'], p['name'], p['host'], p['preferred'])
                           for p in self.data['profiles']))
        if signature == self._profile_signature:
            return
        self._profile_signature = signature
        for widget in (self.profile_list,self.profile_list_large):
            widget.blockSignals(True); widget.clear()
            for profile in self.data['profiles']:
                active='●  ' if self.active_confirmed() and profile['id']==self.data['active_id'] else '○  '
                transport='SOCKS5' if profile['preferred']=='socks5' else 'HTTP' if profile['preferred']=='http' else 'AUTO'
                item=QListWidgetItem(active+profile['name']+'     /     '+transport+' · '+profile['host'])
                item.setData(Qt.ItemDataRole.UserRole,profile['id']); widget.addItem(item)
                if profile['id']==self.selected_id:
                    widget.setCurrentItem(item)
            widget.blockSignals(False)
        self.populate_tray()

    def change_selection(self,item):
        if item is not None:
            self.selected_id=item.data(Qt.ItemDataRole.UserRole)
            self.refresh_ui()

    def persist(self):
        save_store(self.data)
        self.refresh_profile_lists(); self.refresh_ui()

    def add_profile(self):
        editor=ProfileEditor(new_profile('New proxy' if LANG=='en' else 'Новый прокси'),self)
        if editor.exec()==QDialog.DialogCode.Accepted:
            self.data['profiles'].append(editor.profile); self.selected_id=editor.profile['id']; self.persist()

    def edit_profile(self):
        p=self.selected()
        if not p:return
        editor=ProfileEditor(p,self)
        if editor.exec()==QDialog.DialogCode.Accepted:
            self.data['profiles']=[editor.profile if x['id']==p['id'] else x for x in self.data['profiles']]
            self.persist()

    def remove_profile(self):
        p=self.selected()
        if not p:return
        if p['id']==self.data.get('active_id'):
            QMessageBox.warning(self,tr('error'),tr('active_remove'));return
        if QMessageBox.question(self,tr('confirm'),tr('remove_confirm'))!=QMessageBox.StandardButton.Yes:return
        delete_password(p)
        self.data['profiles']=[x for x in self.data['profiles'] if x['id']!=p['id']]
        self.selected_id=self.data['profiles'][0]['id'] if self.data['profiles'] else None
        self.persist()

    def import_proxy_url(self):
        text,ok=QInputDialog.getText(self,tr('import_url'),tr('url_prompt'))
        if not ok or not text:return
        try:
            p=parse_proxy_url(text)
        except ValueError as exc:
            QMessageBox.warning(self,tr('error'),ui_error(exc));return
        self.data['profiles'].append(p); self.selected_id=p['id'];self.persist()

    def import_active(self):self.run_job('import')

    def connect_selected(self):
        p=self.selected()
        if not p:return
        try:
            option=candidates(p)
        except ValueError as exc:
            QMessageBox.warning(self,tr('error'),ui_error(exc));return
        self.pending_profile_id=p['id']
        self.run_job('apply',{'candidates':option})

    def test_selected(self):
        p=self.selected()
        if not p:return
        try:
            transport=candidates(p)[0]
        except ValueError as exc:
            QMessageBox.warning(self,tr('error'),ui_error(exc));return
        self.run_job('test',transport)

    def check_ip(self,quiet=False):
        if 'ip' not in self.jobs:
            self.run_job('ip')

    def enable_firewall(self):
        if QMessageBox.question(self,tr('confirm'),tr('firewall_ask'))==QMessageBox.StandardButton.Yes:
            self.run_job('fw-trial')

    def confirm_firewall(self):self.run_job('fw-confirm')
    def disable_firewall(self):
        if QMessageBox.question(self,tr('confirm'),tr('firewall_dis_ask'))==QMessageBox.StandardButton.Yes:
            self.run_job('fw-disable')

    def save_routing(self):
        if not self.routing_loaded:
            QMessageBox.warning(self,tr('error'),tr('routing_load_first'))
            return
        lines=[x.strip() for x in self.routing_edit.toPlainText().splitlines() if x.strip()]
        from routing import validated_rules
        try:
            values=validated_rules(lines)
        except ValueError as exc:
            QMessageBox.warning(self,tr('invalid'),ui_error(exc));return
        self.run_job('routing-update',{'exclusions':values})

    def allow_backup(self):
        profile=self.selected()
        if profile is None:return
        try:
            options=candidates(profile)
        except ValueError as exc:
            QMessageBox.warning(self,tr('error'),ui_error(exc));return
        self.run_job('fw-backup-update',{'candidates':options})

    def enable_monitor(self):
        if QMessageBox.question(self,tr('confirm'),tr('api_ask'))!=QMessageBox.StandardButton.Yes:return
        self.pending_token=secrets.token_urlsafe(40)
        self.run_job('monitor-enable',{'token':self.pending_token})

    def stop_singbox(self):
        if QMessageBox.question(self,tr('confirm'),tr('stop_ask'))==QMessageBox.StandardButton.Yes:
            self.run_job('stop')

    def refresh_all(self):
        self.run_job('status');self.run_job('snapshot');self.run_job('fw-verify');self.run_job('diag')

    def run_job(self,name,payload=None):
        if self.exiting or name in self.jobs:return
        if name not in ('status','snapshot','diag','ip','logs','fw-verify','routing-read','local-networks'):
            if self.busy:return
            self.busy=True
        job=Worker(name,payload,self)
        self.jobs[name]=job
        job.done.connect(self.job_finished)
        job.finished.connect(lambda name=name: self.worker_stopped(name))
        job.finished.connect(job.deleteLater)
        job.start()
        self.refresh_ui()
        if self.busy:
            self.status_line.setText('◌  '+tr('working'))

    def worker_stopped(self, name):
        self.jobs.pop(name, None)
        if self.exiting and not self.jobs:
            QApplication.instance().quit()

    def job_finished(self,name,success,data,message):
        if name not in ('status','snapshot','diag','ip','logs','fw-verify','routing-read','local-networks'):
            self.busy=False
        if not success:
            if name=='ip':
                self.health_ok=False; self.public_ip='—'
                self.status_line.setText('⚠  '+tr('net_failure'))
            elif name=='snapshot':
                self.api_data=None
            else:
                self.status_line.setText('×  '+tr('error')+': '+ui_error(message)[:150])
                if name not in ('diag','status','routing-read','fw-verify'):
                    QMessageBox.warning(self,tr('error'),ui_error(message)[:1000])
            self.refresh_ui();return
        data=data or {}
        if name=='status':
            self.running=data.get('running',False)
            self.autostart=data.get('autostart',False)
            self.firewall_active=data.get('firewall_service',False)
            self.firewall_enabled=data.get('firewall_autostart',False)
            self.firewall_trial=data.get('firewall_trial',False)
            self.config_mtime=data.get('mtime_ns')
            self.passwordless=data.get('passwordless',False)
        elif name=='snapshot':
            tun=data.get('tun')
            if tun:
                if self.last_counters:
                    delta=max(.001,tun['timestamp']-self.last_counters['timestamp'])
                    self.tun_rx=max(0,(tun['rx_bytes']-self.last_counters['rx_bytes'])/delta)
                    self.tun_tx=max(0,(tun['tx_bytes']-self.last_counters['tx_bytes'])/delta)
                self.last_counters=tun
            else:
                self.last_counters = None
                self.tun_rx = self.tun_tx = 0
            self.graph.push(self.tun_rx,self.tun_tx)
            self.api_data=data.get('api')
            self.api_error=data.get('api_error')
            if self.api_data:
                self.populate_connections(self.api_data['connections'])
            else:
                self.connections.setRowCount(0)
        elif name=='ip':
            self.health_ok=True;self.public_ip=data['ip'];self.last_test_time=time.time()
        elif name=='diag':
            self.monitor_diag.setText(tr('dns_status')+': '+str(data.get('dns','—'))[:80]
                +'  /  '+tr('https_latency')+': '+str(data.get('https_ms') or '—')+' ms')
        elif name=='logs':
            self.events_text.setPlainText(data.get('log',''))
        elif name=='test':
            self.status_line.setText('✓  TLS/CONNECT: '+str(data.get('ms'))+' ms')
        elif name=='import':
            self.imported_profile(data)
        elif name=='apply':
            self.data['active_id']=self.pending_profile_id
            self.data['active_mtime_ns']=data.get('mtime_ns')
            self.config_mtime=data.get('mtime_ns')
            self.active_transport=data.get('protocol','').upper()+':'+str(data.get('port'))
            self.public_ip=data.get('ip','—');self.running=True;self.health_ok=True
            self.persist()
        elif name=='monitor-enable':
            save_token(self.pending_token);self.pending_token=None
            self.data['active_mtime_ns']=data.get('mtime_ns');self.persist()
        elif name=='monitor-disable':
            delete_token()
            if data.get('changed'):
                self.data['active_mtime_ns']=data.get('mtime_ns');self.persist()
        elif name=='fw-verify':
            self.firewall_verified=data.get('enabled')
            self.firewall_trial=data.get('trial',self.firewall_trial)
        elif name in ('fw-trial','fw-confirm','fw-disable'):
            self.firewall_trial=data.get('trial',False)
            self.firewall_verified=data.get('enabled',False)
            if name=='fw-disable':self.firewall_enabled=False
        elif name=='routing-read':
            self.routing_loaded = True
            # Do not overwrite unsaved user edits while in another page.
            if not self.routing_edit.document().isModified():
                self.routing_edit.setPlainText('\n'.join(data.get('exclusions',[])))
                self.routing_edit.document().setModified(False)
        elif name=='routing-update':
            self.routing_edit.setPlainText('\n'.join(data.get('exclusions',[])))
            self.routing_edit.document().setModified(False)
            self.data['active_mtime_ns']=data.get('mtime_ns')
            self.persist()
        elif name=='local-networks':
            if not self.routing_loaded:
                QMessageBox.warning(self,tr('error'),tr('routing_load_first'))
                return
            existing=[x for x in self.routing_edit.toPlainText().splitlines() if x.strip()]
            nets=data.get('networks',[])
            if nets:
                self.routing_edit.setPlainText('\n'.join(dict.fromkeys(existing+nets)))
                self.status_line.setText(tr('local_added'))
            else:
                self.status_line.setText(tr('no_local'))
        if name not in ('local-networks', 'status', 'snapshot', 'test', 'diag'):
            self.status_line.setText('✓  '+tr('updated'))
        self.refresh_ui()
        if name in ('fw-trial','fw-confirm','fw-disable','apply','routing-update'):
            self.run_job('status')

    def imported_profile(self,raw):
        current=next((p for p in self.data['profiles'] if p['host']==raw['host']
                     and p['username']==raw['username'] and p['password']==raw['password']),None)
        if current is None:
            current=new_profile('Current sing-box' if LANG=='en' else 'Текущий sing-box')
            current.update(host=raw['host'],username=raw['username'],password=raw['password'],
                           http_port=0,socks_port=0)
            self.data['profiles'].append(current)
        if raw['protocol']=='http':
            current['http_port']=raw['port'];current['http_tls']=raw['tls']
        else:
            current['socks_port']=raw['port'];current['socks_udp']=raw['udp']
        current['preferred']=raw['protocol']
        self.data['active_id']=current['id']
        self.data['active_mtime_ns']=raw['mtime_ns']
        self.config_mtime=raw['mtime_ns']
        self.selected_id=current['id']
        self.persist()

    def populate_connections(self,rows):
        self.connections.setRowCount(min(100,len(rows)))
        for idx,item in enumerate(rows[:100]):
            values=[item['destination'],item['type'],item['process'],
                    pretty_size(item['download']),pretty_size(item['upload'])]
            for i,value in enumerate(values):
                cell=QTableWidgetItem(str(value));cell.setToolTip(str(value))
                self.connections.setItem(idx,i,cell)

    def refresh_ui(self):
        for button in self.findChildren(QPushButton):
            if button.property('requiresProfile'):
                button.setEnabled(self.selected() is not None and not self.busy)
        profile = next((p for p in self.data['profiles']
                        if self.active_confirmed() and p['id'] == self.data.get('active_id')),
                       self.selected())
        self.primary_profile.setText(profile['name'] if profile else tr('no_profile'))
        self.primary_details.setText((profile['host']+' · '+profile['preferred'].upper()) if profile else tr('add_or_import'))
        self.primary_status.setText(('●  '+tr('checked')) if self.health_ok and self.active_confirmed() else
                                    ('⚠  '+tr('proxy_unreachable')) if self.running and self.health_ok is False else
                                    ('○  '+tr('running')) if self.running else '○  '+tr('stopped'))
        self.ov_widgets[0][1].setText(self.public_ip)
        self.ov_widgets[1][1].setText(self.active_transport)
        self.ov_widgets[2][1].setText('TUN0' if self.running else '—')
        fw_status=(tr('not_checked') if self.firewall_verified is None else
                   tr('firewall_trial_status') if self.firewall_trial else
                   tr('firewall_enabled') if self.firewall_verified else tr('firewall_lost'))
        self.ov_widgets[3][1].setText(fw_status)
        self.firewall_label.setText(fw_status)
        self.side_status.setText('SING-BOX  '+(tr('running') if self.running else tr('stopped')))
        self.side_firewall.setText(tr('kill_switch')+'  '+(tr('checked') if self.firewall_verified else tr('not_checked')))
        self.service_status.setText('sing-box: '+(tr('running') if self.running else tr('stopped')))
        if hasattr(self,'access_label'):
            self.access_label.setText(tr('passwordless_enabled') if self.passwordless else tr('passwordless_disabled'))
            self.access_label.setObjectName('statusOk' if self.passwordless else 'statusWarn')
            self.access_label.style().unpolish(self.access_label)
            self.access_label.style().polish(self.access_label)
        self.top_status.setText(('●  '+tr('running')) if self.running else '○  '+tr('stopped'))
        self.metric_widgets[0][1].setText(pretty_size(self.tun_rx)+'/s')
        self.metric_widgets[1][1].setText(pretty_size(self.tun_tx)+'/s')
        self.metric_widgets[2][1].setText(str(self.api_data['active']) if self.api_data else '—')
        total=self.api_data['download_total']+self.api_data['upload_total'] if self.api_data else 0
        self.metric_widgets[3][1].setText(pretty_size(total) if self.api_data else '—')
        self.api_label.setText(tr('api_on') if self.api_data else tr('api_off'))
        self.overview_snapshot.setText('TUN RX '+pretty_size(self.tun_rx)+'/s  /  TX '+pretty_size(self.tun_tx)+'/s')
        self.refresh_profile_lists()
        self.populate_tray()

    def setup_tray(self):
        self.tray=QSystemTrayIcon(self)
        self.tray.setIcon(icon_image())
        self.tray.setToolTip('Ryoku Proxy')
        self.tray.activated.connect(lambda reason:self.show_and_raise() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray_menu=QMenu(self);self.tray.setContextMenu(self.tray_menu)
        if self.tray_supported:self.tray.show()
        self.populate_tray()

    def populate_tray(self):
        if not hasattr(self,'tray_menu'):return
        signature = (self.active_confirmed(), self.data.get('active_id'),
                     self.running, self.firewall_verified,
                     tuple((p['id'], p['name']) for p in self.data['profiles']))
        if signature == self._tray_signature:
            return
        self._tray_signature = signature
        self.tray.setIcon(icon_image(self.running, bool(self.firewall_verified)))
        self.tray_menu.clear()
        heading=self.tray_menu.addAction('RYOKU PROXY');heading.setEnabled(False)
        self.tray_menu.addSeparator()
        for p in self.data['profiles']:
            action=self.tray_menu.addAction(p['name'])
            action.setCheckable(True);action.setChecked(self.active_confirmed() and p['id']==self.data.get('active_id'))
            action.triggered.connect(lambda checked=False,pid=p['id']:self.connect_named(pid))
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(tr('open_app'),self.show_and_raise)
        self.tray_menu.addAction(tr('monitor'),lambda:(self.show_and_raise(),self.show_page(4)))
        self.tray_menu.addAction(tr('check_ip'),lambda:self.check_ip(False))
        self.tray_menu.addAction(tr('quit'),self.quit_gui)

    def connect_named(self,pid):
        self.selected_id=pid;self.connect_selected()

    def show_and_raise(self):
        self.showNormal();self.raise_();self.activateWindow()
        self.run_job('snapshot')

    def quit_gui(self):
        if self.busy:
            QMessageBox.information(self,'Ryoku Proxy',tr('busy'));return
        self.exiting = True
        for timer in (self.t_status, self.t_snapshot, self.t_health):
            timer.stop()
        self.hide()
        self.tray.hide()
        if not self.jobs:
            QApplication.instance().quit()

    def closeEvent(self,event):
        if not self.exiting and self.tray_supported:
            self.hide();event.ignore();return
        event.ignore()
        self.quit_gui()


def main():
    if '--version' in sys.argv[1:]:
        print('Ryoku Proxy 1.0.0 (ED 1.0)')
        return 0
    app=QApplication(sys.argv)
    app.setApplicationName('Ryoku Proxy')
    app.setApplicationVersion('1.0.0')
    app.setDesktopFileName('ryoku-proxy')
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    app.setStyle('Fusion')
    app.setStyleSheet(STYLES)
    try:
        window=Window()
    except (OSError,RuntimeError,ValueError) as error:
        QMessageBox.critical(None,'Ryoku Proxy',str(error));return 1
    window.show()
    return app.exec()

if __name__=='__main__':
    sys.exit(main())
