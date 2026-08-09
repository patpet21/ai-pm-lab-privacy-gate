APP_STYLE = """
QMainWindow, QWidget {
    background: #F4F7FA;
    color: #10263A;
    font-family: "Bitstream Vera Sans";
    font-size: 10pt;
}
QFrame#Sidebar { background: #071F36; border: none; }
QFrame#BrandPanel { background: #FFFFFF; border-radius: 16px; padding: 8px; }
QLabel#SidebarBrand { color: #071F36; font-size: 15pt; font-weight: 800; letter-spacing: 2px; }
QLabel#SidebarProduct { color: #B58A36; font-size: 8pt; font-weight: 800; letter-spacing: 2px; }
QLabel#SidebarNote { color: #9DB4C7; font-size: 8pt; padding: 14px; border-top: 1px solid #24435D; }
QPushButton#NavButton {
    background: transparent; color: #C9D6E1; border: none; border-radius: 9px;
    padding: 12px 14px; text-align: left; font-weight: 650;
}
QPushButton#NavButton:hover { background: #102F4A; color: white; }
QPushButton#NavButton:checked { background: #168492; color: white; border-left: 3px solid #D2A84B; }
QFrame#Content { background: #F4F7FA; }
QFrame#Card, QFrame#ConnectionCard {
    background: white; border: 1px solid #D8E1E8; border-radius: 12px;
}
QFrame#ConnectionCard { min-height: 150px; }
QFrame#ActionBar { background: #EAF0F4; border: 1px solid #D2DDE5; border-radius: 11px; }
QLabel#PageTitle { color: #071F36; font-size: 22pt; font-weight: 800; }
QLabel#SectionTitle { color: #0B2A45; font-size: 12pt; font-weight: 750; }
QLabel#FieldLabel { color: #183E5B; font-weight: 700; }
QLabel#Muted { color: #64788A; }
QLabel#SafeBadge { background: #DFF5F0; color: #136A5D; border-radius: 12px; padding: 7px 12px; font-weight: 700; }
QLabel#ConnectionBadge { background: #E8F1F5; color: #176777; border-radius: 10px; padding: 5px 9px; font-size: 8pt; font-weight: 700; }
QLabel#Metric { background: #E9F2F6; color: #123B56; border: 1px solid #CBDCE6; border-radius: 10px; padding: 8px 13px; font-weight: 700; }
QPushButton, QToolButton {
    background: #168492; color: white; border: none; border-radius: 8px;
    padding: 9px 15px; font-weight: 700;
}
QPushButton:hover, QToolButton:hover { background: #0F6D79; }
QPushButton:disabled, QToolButton:disabled { background: #B8C4CD; color: #EAF0F3; }
QPushButton#Secondary, QToolButton#SecondaryTool { background: white; color: #174E62; border: 1px solid #9EBBC6; }
QPushButton#Secondary:hover, QToolButton#SecondaryTool:hover { background: #EFF7F8; }
QPushButton#Gold { background: #B58A36; }
QPushButton#Gold:hover { background: #987329; }
QPushButton#Danger { background: #FFF2F0; color: #A33A31; border: 1px solid #E9B4AF; }
QPushButton#Tiny { background: #EAF1F5; color: #244B63; padding: 5px 9px; font-size: 8pt; }
QComboBox, QLineEdit, QPlainTextEdit, QListWidget, QTableWidget, QTabWidget::pane {
    background: white; border: 1px solid #C9D6DF; border-radius: 8px;
}
QComboBox, QLineEdit { padding: 7px 9px; min-height: 24px; }
QPlainTextEdit { padding: 9px; selection-background-color: #D2A84B; }
QListWidget { padding: 5px; }
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:hover { background: #EDF5F7; }
QHeaderView::section { background: #123B56; color: white; padding: 8px; border: none; font-weight: 700; }
QTableWidget { gridline-color: #DDE5EA; alternate-background-color: #F4F8FA; }
QTableWidget::item:selected { background: #D9EEF1; color: #10263A; }
QTabBar::tab { background: #E3EBF0; color: #38566B; padding: 8px 18px; margin-right: 3px; border-radius: 6px; }
QTabBar::tab:selected { background: #168492; color: white; }
QSplitter::handle { background: transparent; width: 8px; }
QMenu { background: white; border: 1px solid #C9D6DF; padding: 6px; }
QMenu::item { padding: 8px 24px; border-radius: 5px; }
QMenu::item:selected { background: #D9EEF1; color: #10263A; }
QStatusBar { background: #E8EFF3; color: #536C7E; }
"""
