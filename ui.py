from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableView, QToolBar,
    QLineEdit, QPushButton, QInputDialog, QFileDialog, QMessageBox, QTabWidget,
    QHeaderView, QMenu, QLabel, QColorDialog
)
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QAction, QColor

from sheet_model import SheetModel
from sql_engine import sql_engine
from extension_api import extension_api
from file_io import load_file, save_file

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQLSheet (SQL機能付き表計算ソフト)")
        self.resize(1000, 700)
        
        self.tabs = QTabWidget()
        self.sheets = [] # [{"model": SheetModel, "view": QTableView}, ...]
        
        self._setup_ui()
        self.add_sheet("Sheet1")

    def _setup_ui(self):
        # メインメニュー
        menu = self.menuBar()
        file_menu = menu.addMenu("ファイル")
        
        action_open = QAction("開く", self)
        action_open.triggered.connect(self.open_file)
        file_menu.addAction(action_open)
        
        action_save = QAction("保存", self)
        action_save.triggered.connect(self.save_file)
        file_menu.addAction(action_save)

        edit_menu = menu.addMenu("編集")
        action_undo = QAction("元に戻す (Undo)", self)
        action_undo.setShortcut("Ctrl+Z")
        action_undo.triggered.connect(self.undo_action)
        edit_menu.addAction(action_undo)
        
        action_redo = QAction("やり直し (Redo)", self)
        action_redo.setShortcut("Ctrl+Y")
        action_redo.triggered.connect(self.redo_action)
        edit_menu.addAction(action_redo)

        sheet_menu = menu.addMenu("シート")
        action_add_sheet = QAction("シートの追加", self)
        action_add_sheet.triggered.connect(lambda: self.add_sheet(f"Sheet{len(self.sheets)+1}"))
        sheet_menu.addAction(action_add_sheet)

        # ツールバー（ツール群）
        toolbar_tools = QToolBar("Tools")
        self.addToolBar(toolbar_tools)
        
        action_bold = QAction("太字 (B)", self)
        action_bold.triggered.connect(self.toggle_bold)
        toolbar_tools.addAction(action_bold)
        
        action_color = QAction("背景色設定", self)
        action_color.triggered.connect(self.set_bg_color)
        toolbar_tools.addAction(action_color)

        # メインレイアウト
        central = QWidget()
        layout = QVBoxLayout()
        
        # SQL/数式入力バー
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("fx / SQL:"))
        self.sql_input = QLineEdit()
        self.sql_input.setPlaceholderText('例: =sql("select * from テーブル名") または =A1+B1')
        form_layout.addWidget(self.sql_input)
        
        run_btn = QPushButton("実行 (Enter)")
        run_btn.clicked.connect(self.apply_formula)
        self.sql_input.returnPressed.connect(self.apply_formula)
        form_layout.addWidget(run_btn)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.tabs)
        
        central.setLayout(layout)
        self.setCentralWidget(central)

    def current_model_view(self):
        idx = self.tabs.currentIndex()
        if idx >= 0 and idx < len(self.sheets):
            return self.sheets[idx]["model"], self.sheets[idx]["view"]
        return None, None

    def add_sheet(self, name):
        model = SheetModel()
        view = QTableView()
        view.setModel(model)
        view.horizontalHeader().setDefaultSectionSize(100)
        
        def header_data(section, orientation, role):
            if role != Qt.DisplayRole:
                return None
            if orientation == Qt.Horizontal:
                res = ""
                s = section
                while s >= 0:
                    res = chr(65 + (s % 26)) + res
                    s = s // 26 - 1
                return res
            else:
                return str(section + 1)
        model.headerData = header_data

        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(self.show_context_menu)
        
        # セル選択切り替え時に数式バーを更新
        view.selectionModel().currentChanged.connect(self.on_cell_selected)
        
        self.sheets.append({"model": model, "view": view})
        self.tabs.addTab(view, name)

    def on_cell_selected(self, current, previous):
        if not current.isValid():
            return
        r, c = current.row(), current.column()
        model, _ = self.current_model_view()
        if not model:
            return
        
        formula = model.formulas.get((r, c))
        if formula:
            self.sql_input.setText(formula)
        else:
            val = model.values.get((r, c), "")
            self.sql_input.setText(str(val))

    def apply_formula(self):
        model, view = self.current_model_view()
        if not model: return
        current = view.currentIndex()
        if not current.isValid():
            return
        
        text = self.sql_input.text()
        model.setData(current, text, Qt.EditRole)

    def undo_action(self):
        model, _ = self.current_model_view()
        if model: model.undo()

    def redo_action(self):
        model, _ = self.current_model_view()
        if model: model.redo()

    def toggle_bold(self):
        model, view = self.current_model_view()
        if not model: return
        selection = view.selectionModel().selectedIndexes()
        if selection:
            # 現在の先頭セルが太字か判定して反転させる
            r, c = selection[0].row(), selection[0].column()
            f = model.fonts.get((r, c), {"bold": False})
            new_bold = not f.get("bold", False)
            model.set_cell_style(selection, bold=new_bold)

    def set_bg_color(self):
        model, view = self.current_model_view()
        if not model: return
        selection = view.selectionModel().selectedIndexes()
        if selection:
            color = QColorDialog.getColor(Qt.yellow, self, "背景色の選択")
            if color.isValid():
                model.set_cell_style(selection, bg_color=color)

    def show_context_menu(self, pos):
        model, view = self.current_model_view()
        if not model: return
        
        menu = QMenu(self)
        
        action_name_range = QAction("選択範囲に名前を付ける (SQL連携)", self)
        action_name_range.triggered.connect(self.name_selected_range)
        menu.addAction(action_name_range)
        
        menu.addSeparator()
        
        action_insert_row = QAction("行を挿入", self)
        action_insert_row.triggered.connect(self.insert_row)
        menu.addAction(action_insert_row)
        
        action_insert_col = QAction("列を挿入", self)
        action_insert_col.triggered.connect(self.insert_col)
        menu.addAction(action_insert_col)
        
        menu.exec_(view.viewport().mapToGlobal(pos))

    def insert_row(self):
        model, view = self.current_model_view()
        if not model: return
        idx = view.currentIndex()
        if idx.isValid():
            model.insertRows(idx.row(), 1)

    def insert_col(self):
        model, view = self.current_model_view()
        if not model: return
        idx = view.currentIndex()
        if idx.isValid():
            model.insertColumns(idx.column(), 1)

    def name_selected_range(self):
        model, view = self.current_model_view()
        if not model: return
        
        selection = view.selectionModel().selection()
        if selection.isEmpty():
            QMessageBox.warning(self, "エラー", "範囲を選択してください。")
            return
            
        rect = selection[0]
        start_r = rect.top()
        end_r = rect.bottom()
        start_c = rect.left()
        end_c = rect.right()
        
        name, ok = QInputDialog.getText(self, "範囲に名前を付ける", "範囲名 (SQLのテーブル名として使われます):")
        if ok and name:
            model.set_named_range(name, start_r, start_c, end_r, end_c)
            QMessageBox.information(self, "完了", f"「{name}」として範囲を保存しました。\n SQLiteで参照可能です。")

    def open_file(self):
        model, _ = self.current_model_view()
        if not model: return
        path, _ = QFileDialog.getOpenFileName(self, "ファイルを開く", "", "Supported Files (*.csv *.xlsx *.xls)")
        if path:
            try:
                data = load_file(path)
                model.load_data(data)
                self.tabs.setTabText(self.tabs.currentIndex(), path.split('/')[-1])
                QMessageBox.information(self, "完了", "読み込みました。")
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))

    def save_file(self):
        model, _ = self.current_model_view()
        if not model: return
        path, _ = QFileDialog.getSaveFileName(self, "ファイルを保存", "", "CSV (*.csv);;Excel (*.xlsx)")
        if path:
            try:
                data = model.get_data_list()
                save_file(path, data)
                self.tabs.setTabText(self.tabs.currentIndex(), path.split('/')[-1])
                QMessageBox.information(self, "完了", "保存しました。")
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))
