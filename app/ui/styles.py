QSS_LIGHT = """
QWidget {
    background-color: #f3f5f8;
    color: #2b3440;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 12px;
}
QMainWindow, QDialog { background-color: #eef1f5; }
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e2e7ee;
    border-radius: 10px;
}
QLabel#cardTitle { font-size: 14px; font-weight: 600; color: #1f2937; }
QLabel#muted { color: #6b7280; }
QLabel#statusBadge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 8px; }
QLabel#statusBadge[state="ok"] { background-color: #dcfce7; color: #15803d; }
QLabel#statusBadge[state="warn"] { background-color: #fef3c7; color: #b45309; }
QLabel#statusBadge[state="err"] { background-color: #fee2e2; color: #b91c1c; }
QLabel#statusBadge[state="lock"] { background-color: #e5e7eb; color: #6b7280; }
QFrame#videoOverlay {
    background-color: transparent;
    margin: 8px;
}
QFrame#videoOverlay QLabel {
    background: transparent;
    border: none;
    color: #ffffff;
}
QLabel#ovTitle { font-weight: 700; font-size: 14px; }
QLabel#ovDim { font-size: 11px; font-weight: 600; }
QLabel#ovMeta { font-size: 12px; font-weight: 600; }
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d1d6dd;
    border-radius: 6px;
    padding: 5px 12px;
}
QPushButton:hover { background-color: #f0f4f8; border-color: #9aa5b1; }
QPushButton:pressed { background-color: #e2e8f0; }
QPushButton:disabled { color: #b0b7c0; background-color: #f3f5f8; }
QPushButton#primary { background-color: #2563eb; color: #ffffff; border: none; }
QPushButton#primary:hover { background-color: #1d4ed8; }
QPushButton#danger { color: #b91c1c; }
QToolBar { background-color: #ffffff; border-bottom: 1px solid #e2e7ee; spacing: 6px; padding: 4px; }
QToolButton { border: none; border-radius: 6px; padding: 6px; }
QToolButton:hover { background-color: #eef2f7; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d1d6dd;
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #2563eb;
}
QTableWidget, QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e7ee;
    border-radius: 6px;
    gridline-color: #eef1f5;
}
QHeaderView::section {
    background-color: #f8fafc;
    border: none;
    border-bottom: 1px solid #e2e7ee;
    padding: 5px;
    font-weight: 600;
}
QProgressBar {
    background-color: #e5e9ef;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk { background-color: #2563eb; border-radius: 4px; }
QSplitter::handle { background-color: #e2e7ee; }
QScrollArea { border: none; background: transparent; }
"""
