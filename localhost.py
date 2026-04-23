import sys
import os
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QLineEdit, QMessageBox, QDialog, QRadioButton,
    QButtonGroup, QSpinBox, QFormLayout, QToolButton
)
from PyQt5.QtGui import QIcon, QFont


class HttpServerThread(QThread):
    started_signal = pyqtSignal(str)
    stopped_signal = pyqtSignal()

    def __init__(self, directory, host="127.0.0.1", port=8000, start_file=None, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.host = host
        self.port = port
        self.start_file = start_file
        self._stop_flag = threading.Event()
        self.httpd = None

    def run(self):
        handler_class = self.make_handler(self.directory)
        try:
            with TCPServer((self.host, self.port), handler_class) as httpd:
                self.httpd = httpd
                url = f"http://{self.host}:{self.port}/"
                if self.start_file:
                    url += self.start_file
                self.started_signal.emit(url)
                while not self._stop_flag.is_set():
                    httpd.handle_request()
        except OSError as e:
            self.started_signal.emit(f"ERROR: {e}")
        finally:
            self.stopped_signal.emit()

    def stop(self):
        self._stop_flag.set()
        try:
            import socket
            with socket.create_connection((self.host, self.port), timeout=1):
                pass
        except Exception:
            pass

    @staticmethod
    def make_handler(directory):
        class CustomHandler(SimpleHTTPRequestHandler):
            def translate_path(self, path):
                path = SimpleHTTPRequestHandler.translate_path(self, path)
                relpath = os.path.relpath(path, os.getcwd())
                return os.path.join(directory, os.path.relpath(relpath, directory))

        return CustomHandler


class SettingsDialog(QDialog):
    def __init__(self, parent=None, host_mode="local", port=8000, auto_open=True):
        super().__init__(parent)
        self.setWindowTitle("Server Settings")
        self.setFixedSize(320, 200)

        self.host_mode = host_mode
        self.port = port
        self.auto_open = auto_open

        layout = QVBoxLayout(self)

        title = QLabel("Hosting Mode")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(title)

        self.local_radio = QRadioButton("Local Host (this device only)")
        self.global_radio = QRadioButton("Global Network Host (any device on LAN)")
        group = QButtonGroup(self)
        group.addButton(self.local_radio)
        group.addButton(self.global_radio)

        if host_mode == "global":
            self.global_radio.setChecked(True)
        else:
            self.local_radio.setChecked(True)

        layout.addWidget(self.local_radio)
        layout.addWidget(self.global_radio)

        form = QFormLayout()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(port)
        form.addRow("Port:", self.port_spin)
        layout.addLayout(form)

        self.auto_open_checkbox = QRadioButton("Auto-open in browser")
        self.auto_open_checkbox.setChecked(auto_open)
        layout.addWidget(self.auto_open_checkbox)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def get_values(self):
        host_mode = "global" if self.global_radio.isChecked() else "local"
        port = self.port_spin.value()
        auto_open = self.auto_open_checkbox.isChecked()
        return host_mode, port, auto_open


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Premium Local Web Host")
        self.setMinimumSize(600, 260)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton {
                background-color: #3a3a46;
                border-radius: 6px;
                padding: 8px 14px;
                color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #505064;
            }
            QPushButton:disabled {
                background-color: #2a2a34;
                color: #777777;
            }
            QLineEdit {
                background-color: #2a2a34;
                border-radius: 4px;
                padding: 6px;
                border: 1px solid #444;
                color: #f0f0f0;
            }
            QDialog {
                background-color: #25252c;
            }
            QRadioButton {
                color: #f0f0f0;
            }
            QSpinBox {
                background-color: #2a2a34;
                border-radius: 4px;
                padding: 4px;
                border: 1px solid #444;
                color: #f0f0f0;
            }
        """)

        self.server_thread = None
        self.current_dir = None
        self.current_file = None

        self.host_mode = "local"
        self.port = 8000
        self.auto_open = True

        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        header = QLabel("Local Web File Host")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        main_layout.addWidget(header)

        subtitle = QLabel("Serve a folder or a single web file over HTTP with one click.")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #bbbbbb;")
        main_layout.addWidget(subtitle)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose a folder or a single HTML file...")
        self.path_edit.setReadOnly(True)

        choose_file_btn = QPushButton("Choose File")
        choose_file_btn.clicked.connect(self.choose_file)

        choose_folder_btn = QPushButton("Choose Folder")
        choose_folder_btn.clicked.connect(self.choose_folder)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_selection)

        path_row.addWidget(self.path_edit, stretch=1)
        path_row.addWidget(choose_file_btn)
        path_row.addWidget(choose_folder_btn)
        path_row.addWidget(clear_btn)
        main_layout.addLayout(path_row)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #aaaaaa;")
        status_row.addWidget(self.status_label, stretch=1)

        self.url_label = QLabel("")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.url_label.setStyleSheet("color: #6ab0ff;")
        status_row.addWidget(self.url_label, stretch=1)
        main_layout.addLayout(status_row)

        control_row = QHBoxLayout()
        control_row.addStretch()

        self.start_btn = QPushButton("Start Server")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_server)

        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_server)

        control_row.addWidget(self.start_btn)
        control_row.addWidget(self.stop_btn)
        main_layout.addLayout(control_row)

        bottom_row = QHBoxLayout()

        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(QIcon("gear.svg"))
        self.settings_btn.setIconSize(QSize(22, 22))
        self.settings_btn.setFixedSize(QSize(36, 36))
        self.settings_btn.setStyleSheet("""
            QToolButton {
                background-color: #3a3a46;
                border-radius: 6px;
            }
            QToolButton:hover {
                background-color: #505064;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        bottom_row.addWidget(self.settings_btn, alignment=Qt.AlignLeft)

        bottom_row.addStretch()

        hint = QLabel("Tip: Use Global Network Host to access from phones or other PCs on your LAN.")
        hint.setStyleSheet("color: #888888; font-size: 9pt;")
        bottom_row.addWidget(hint, alignment=Qt.AlignRight)

        main_layout.addLayout(bottom_row)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Web File",
            "",
            "Web Files (*.html *.htm *.php *.js *.css);;All Files (*)"
        )
        if path:
            self.current_file = os.path.basename(path)
            self.current_dir = os.path.dirname(path)
            self.path_edit.setText(path)
            self.update_start_button_state()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Folder", "")
        if path:
            self.current_dir = path
            self.current_file = None
            self.path_edit.setText(path)
            self.update_start_button_state()

    def clear_selection(self):
        self.current_dir = None
        self.current_file = None
        self.path_edit.clear()
        self.url_label.clear()
        self.status_label.setText("Status: Idle")
        self.start_btn.setEnabled(False)

    def update_start_button_state(self):
        self.start_btn.setEnabled(self.current_dir is not None and self.server_thread is None)

    def start_server(self):
        if not self.current_dir:
            QMessageBox.warning(self, "No Path Selected", "Please choose a file or folder first.")
            return

        host = "0.0.0.0" if self.host_mode == "global" else "127.0.0.1"

        self.server_thread = HttpServerThread(
            directory=self.current_dir,
            host=host,
            port=self.port,
            start_file=self.current_file
        )
        self.server_thread.started_signal.connect(self.on_server_started)
        self.server_thread.stopped_signal.connect(self.on_server_stopped)
        self.server_thread.start()

        self.status_label.setText("Status: Starting server...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_server(self):
        if self.server_thread:
            self.status_label.setText("Status: Stopping server...")
            self.server_thread.stop()

    def on_server_started(self, url):
        if url.startswith("ERROR:"):
            QMessageBox.critical(self, "Server Error", url)
            self.status_label.setText("Status: Error")
            self.server_thread = None
            self.update_start_button_state()
            self.stop_btn.setEnabled(False)
            self.url_label.setText("")
            return

        self.status_label.setText("Status: Running")
        self.url_label.setText(url)
        if self.auto_open:
            webbrowser.open(url)

    def on_server_stopped(self):
        self.status_label.setText("Status: Stopped")
        self.stop_btn.setEnabled(False)
        self.server_thread = None
        self.update_start_button_state()

    def open_settings(self):
        dlg = SettingsDialog(
            self,
            host_mode=self.host_mode,
            port=self.port,
            auto_open=self.auto_open
        )
        if dlg.exec_() == QDialog.Accepted:
            host_mode, port, auto_open = dlg.get_values()
            self.host_mode = host_mode
            self.port = port
            self.auto_open = auto_open
            mode_text = "Local Host" if host_mode == "local" else "Global Network Host"
            self.status_label.setText(f"Status: Idle ({mode_text}, port {port})")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
