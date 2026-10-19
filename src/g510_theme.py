"""Shared visual theme for the control application."""

STYLESHEET = """
QWidget {
    background-color: #101721;
    color: #e2eaf4;
    font-family: sans-serif;
}
QLabel { background: transparent; }
QWidget#Sidebar {
    background-color: #151f2e;
    border-right: 1px solid #2a3c52;
}
QListWidget#Navigation {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#Navigation::item {
    padding: 14px 12px;
    margin: 3px 0;
    border-radius: 6px;
}
QListWidget#Navigation::item:selected {
    background: #244f7b;
    color: white;
}
QListWidget#Navigation::item:hover { background: #20354d; }
QLabel#Brand { font-size: 22px; font-weight: bold; color: #65baff; }
QLabel#PageTitle { font-size: 24px; font-weight: bold; }
QWidget#Card { background: #182435; border: 1px solid #2a3c52; border-radius: 8px; }
QWidget#Card QLabel { background: transparent; }
QLabel#Metric { font-size: 22px; font-weight: bold; color: #65baff; }
QScrollArea, QStackedWidget { border: none; }
QScrollBar:vertical { background: #101721; width: 12px; margin: 0; }
QScrollBar:horizontal { background: #101721; height: 12px; margin: 0; }
QScrollBar::handle { background: #3a5069; border-radius: 5px; min-width: 20px; min-height: 20px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolBar { background: #151f2e; border-top: 1px solid #2a3c52; padding: 8px; spacing: 12px; }
QStatusBar { background: #101721; color: #a8bbd0; }
QPushButton:disabled { color: #7f91a5; border-color: #29394b; background: #182230; }
QPushButton#saveAllBtn { background: #2464a0; color: white; font-weight: bold; }
QListWidget, QTableWidget { background: #162131; alternate-background-color: #1c2a3d; }
QHeaderView::section { background: #20354d; color: #e2eaf4; padding: 6px; border: none; }
QComboBox, QSpinBox { background: #1b293b; border: 1px solid #3a5069; border-radius: 4px; }
QComboBox QAbstractItemView { background: #1b293b; color: #e2eaf4; selection-background-color: #244f7b; }
QPushButton {
    background-color: #26262b;
    border: 1px solid #34343a;
    border-radius: 6px;
    padding: 7px 10px;
    text-align: left;
}
QPushButton:hover {
    background-color: #302f36;
    border-color: #46454e;
}
QPushButton:focus, QComboBox:focus, QLineEdit:focus { border-color: #65baff; }
QPushButton:checked {
    background-color: #3a6cc4;
    border-color: #5a8ce0;
    color: white;
}
QPushButton#Primary {
    background-color: #3a6cc4;
    border-color: #5a8ce0;
    color: white;
    text-align: center;
    font-weight: 600;
    padding: 9px 10px;
}
QPushButton#Primary:hover {
    background-color: #4a7cd4;
    border-color: #6a9cf0;
}
QPushButton#PanelPrimary {
    background-color: #3a6cc4;
    border-color: #5a8ce0;
    color: white;
    text-align: center;
    font-weight: 600;
    font-size: 11px;
    padding: 4px 8px;
    min-height: 28px;
}
QPushButton#PanelPrimary:hover {
    background-color: #4a7cd4;
    border-color: #6a9cf0;
}
QPushButton#PanelButton {
    font-size: 11px;
    padding: 4px 8px;
    text-align: center;
    min-height: 28px;
}
QLabel#Title {
    font-size: 15px;
    font-weight: 600;
    padding: 4px 2px 10px 2px;
}
QLabel#PanelSection {
    color: #c9c9d0;
    font-weight: 600;
    padding-top: 4px;
}
QWidget#Panel {
    background-color: #182435;
    border: 1px solid #2a3c52;
    border-radius: 8px;
}
QFrame#Separator {
    background-color: #2a2a30;
    border: none;
    max-height: 1px;
}
QLabel#Status {
    color: #9a9aa2;
    font-size: 11px;
    padding-top: 4px;
}
QPushButton#Discreet {
    background-color: transparent;
    border: 1px solid #2a2a30;
    color: #8a8a92;
    font-size: 11px;
    padding: 4px 6px;
    text-align: center;
}
QPushButton#Discreet:hover {
    background-color: #26262b;
    color: #c0c0c6;
    border-color: #3a3a42;
}
QLineEdit {
    background-color: #1e1e22;
    border: 1px solid #34343a;
    border-radius: 4px;
    padding: 5px;
    min-height: 24px;
}
QComboBox {
    min-height: 28px;
    padding: 3px 8px;
}
"""
