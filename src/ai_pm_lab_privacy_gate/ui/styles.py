APP_STYLE = """
QMainWindow, QWidget {
    background: #F7FAFC;
    color: #17384E;
    font-family: "Bitstream Vera Sans";
    font-size: 10pt;
}
QFrame#Sidebar { background: #062B4F; border: none; }
QFrame#BrandPanel { background: #FFFFFF; border-radius: 16px; padding: 8px; }
QPushButton#SidebarToggle {
    background: #0D3A5C; color: #DCE7EF; border: 1px solid #1B4B6B; border-radius: 9px;
    padding: 5px; min-width: 28px; max-width: 28px; font-size: 14pt; font-weight: 800;
}
QPushButton#SidebarToggle:hover { background: #0B7180; color: white; }
QLabel#SidebarBrand { color: #062B4F; font-size: 15pt; font-weight: 800; letter-spacing: 2px; }
QLabel#SidebarProduct { color: #D3A13B; font-size: 8pt; font-weight: 800; letter-spacing: 2px; }
QLabel#SidebarNote { color: #AFC3D1; font-size: 8pt; padding: 14px; border-top: 1px solid #1B4B6B; }
QLabel#ProductFooter {
    background: #EAF0F4; color: #5B7182; border-top: 1px solid #D7E2EA;
    padding: 7px 12px; font-size: 8pt;
}
QLabel#ProductFooter a { color: #0B7180; text-decoration: none; }
QPushButton#NavButton {
    background: transparent; color: #DCE7EF; border: none; border-radius: 9px;
    padding: 12px 14px; text-align: left; font-weight: 650; min-height: 24px;
}
QPushButton#NavButton:hover { background: #0D3A5C; color: white; }
QPushButton#NavButton:checked { background: #0B7180; color: white; border-left: 3px solid #D3A13B; }
QFrame#Content { background: #F7FAFC; }
QFrame#Card, QFrame#ConnectionCard {
    background: white; border: 1px solid #D7E2EA; border-radius: 12px;
}
QFrame#ConnectionCard { min-height: 150px; }
QFrame#ActionBar { background: #EEF3F6; border: 1px solid #D7E2EA; border-radius: 11px; }
QLabel#PageTitle { color: #062B4F; font-size: 22pt; font-weight: 800; }
QLabel#SectionTitle { color: #17384E; font-size: 12pt; font-weight: 750; }
QLabel#FieldLabel { color: #17384E; font-weight: 700; }
QLabel#Muted { color: #64788A; }
QLabel#ReviewGuide {
    color: #0B7180;
    background: #E8F6F6;
    border-radius: 6px;
    padding: 5px 8px;
    font-weight: 700;
}
QLabel#ReviewContext {
    color: #294C60;
    background: #F7FAFC;
    border: 1px solid #D7E2EA;
    border-radius: 7px;
    padding: 7px 9px;
}
QLabel#SafeBadge { background: #E8F6F6; color: #0B7180; border-radius: 12px; padding: 7px 12px; font-weight: 700; }
QLabel#ConnectionBadge { background: #EEF4F7; color: #0B7180; border-radius: 10px; padding: 5px 9px; font-size: 8pt; font-weight: 700; }
QLabel#CopyFeedback { color: #0B7180; font-size: 8pt; font-weight: 750; min-width: 58px; }
QLabel#TokenHint { background: #EDF4F7; color: #476578; border-radius: 9px; padding: 5px 9px; font-size: 8pt; font-weight: 700; }
QLabel#Metric { background: #EDF4F8; color: #17384E; border: 1px solid #CEDDE6; border-radius: 10px; padding: 8px 13px; font-weight: 700; }
QLabel#SourceMetric { background: #FBF5E8; color: #775A1F; border: 1px solid #E7D4AA; border-radius: 10px; padding: 8px 13px; font-weight: 700; }
QPushButton#SafetyMetric { background: #E8F6F6; color: #0B7180; border: 1px solid #BFE2E2; border-radius: 10px; padding: 8px 13px; font-weight: 700; }
QPushButton#SafetyMetric:hover { background: #DDF0F0; }
QPushButton#SafetyMetric[warning="true"] { background: #FBF5E8; color: #8A6321; border-color: #E4C47A; }
QPushButton, QToolButton {
    background: #0B7180; color: white; border: none; border-radius: 8px;
    padding: 9px 15px; font-weight: 700;
}
QPushButton:hover, QToolButton:hover { background: #095E6B; }
QPushButton:pressed, QToolButton:pressed { background: #084E59; }
QPushButton:disabled, QToolButton:disabled { background: #D7E0E7; color: #8796A4; }
QPushButton#Secondary, QToolButton#SecondaryTool { background: white; color: #17384E; border: 1px solid #B9CBD5; }
QPushButton#Secondary:hover, QToolButton#SecondaryTool:hover { background: #F1FAFA; color: #0B7180; border-color: #8FB8BF; }
QPushButton#Gold { background: #D3A13B; color: #062B4F; }
QPushButton#Gold:hover { background: #B9862F; color: white; }
QPushButton#Danger { background: #FFF2F0; color: #A33A31; border: 1px solid #E9B4AF; }
QPushButton#Tiny { background: #EAF0F4; color: #17384E; padding: 5px 9px; font-size: 8pt; }
QPushButton#Tiny:hover { background: #E8F6F6; color: #0B7180; }
QToolButton#InfoButton { background: #E8F6F6; color: #0B7180; border: 1px solid #BBDCDD; border-radius: 9px; padding: 0; min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; font-size: 8pt; font-weight: 800; }
QToolButton#InfoButton:hover { background: #0B7180; color: white; }
QRadioButton {
    color: #17384E;
    spacing: 10px;
    padding: 7px 10px;
    border-radius: 8px;
    font-weight: 650;
}
QRadioButton:hover { background: #F1FAFA; }
QRadioButton:checked {
    background: #E8F6F6;
    color: #0B7180;
    font-weight: 800;
}
QRadioButton::indicator {
    width: 19px;
    height: 19px;
    border-radius: 10px;
    border: 2px solid #8AA6B7;
    background: white;
}
QRadioButton::indicator:hover { border: 2px solid #1595A3; }
QRadioButton::indicator:checked {
    border: 6px solid #0B7180;
    background: white;
}
QCheckBox { spacing: 9px; font-weight: 650; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #8AA6B7;
    border-radius: 4px;
    background: white;
}
QCheckBox::indicator:checked {
    background: #0B7180;
    border: 2px solid #0B7180;
}
QComboBox, QLineEdit, QPlainTextEdit, QListWidget, QTableWidget, QTabWidget::pane {
    background: white; border: 1px solid #C9D6DF; border-radius: 8px;
}
QComboBox, QLineEdit { padding: 7px 9px; min-height: 24px; }
QPlainTextEdit { padding: 9px; selection-background-color: #D3A13B; }
QPlainTextEdit[readOnly="true"] { background: #FBFDFE; }
QLabel#ColorLegend { color: #516A7B; background: #F8FBFC; border: 1px solid #E1E9EE; border-radius: 8px; padding: 7px 9px; font-size: 8pt; }
QFrame#PdfPanel { background: #FAFCFD; border: 1px solid #D7E2EA; border-radius: 10px; }
QLabel#PdfTitle { color: #17384E; font-weight: 750; font-size: 10pt; }
QLabel#PdfBadge { background: #E8F6F6; color: #0B7180; border-radius: 7px; padding: 4px 7px; font-size: 7.5pt; font-weight: 700; }
QLabel#PdfPageLabel { color: #17384E; font-weight: 700; padding: 3px 8px; }
QPdfView#PdfView { background: #DDE5EA; border: 1px solid #C5D1DA; border-radius: 6px; }
QTextBrowser#OfficeDocumentView, QTableWidget#OfficeSheetView {
    background: #FFFFFF;
    border: 1px solid #C5D1DA;
    border-radius: 6px;
    color: #17384E;
}
QTableWidget#OfficeSheetView::item { padding: 3px 6px; }
QListWidget { padding: 5px; }
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:hover { background: #F1FAFA; }
QHeaderView::section { background: #062B4F; color: white; padding: 8px; border: none; font-weight: 700; }
QTableWidget { gridline-color: #DDE5EA; alternate-background-color: #F7FAFC; }
QTableWidget::item:selected { background: #DCEFF1; color: #062B4F; }
QTabBar::tab { background: #EAF0F4; color: #38566B; padding: 8px 18px; margin-right: 3px; border-radius: 6px; }
QTabBar::tab:hover { background: #E8F6F6; color: #0B7180; }
QTabBar::tab:selected { background: #0B7180; color: white; }
QSplitter::handle { background: #E3EBF0; width: 5px; margin: 8px 2px; border-radius: 2px; }
QSplitter::handle:hover { background: #1595A3; }
QMenu { background: white; border: 1px solid #C9D6DF; padding: 6px; }
QMenu::item { padding: 8px 24px; border-radius: 5px; }
QMenu::item:selected { background: #E8F6F6; color: #062B4F; }
QStatusBar { background: #EAF0F4; color: #5B7182; }
"""
