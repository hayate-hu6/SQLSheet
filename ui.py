from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableView, QToolBar,
    QLineEdit, QPushButton, QInputDialog, QFileDialog, QMessageBox,
    QHeaderView, QMenu, QLabel
)
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QAction

from sheet_model import SheetModel
from sql_engine import sql_engine
from extension_api import extension_api
from file_io import load_file, save_file

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQLSheet (SQL機能付き表計算ソフト)")
        self.resize(1000, 700)
        
        self.model = SheetModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        
        # 列行のヘッダー幅をよしなに設定
        self.table_view.horizontalHeader().setDefaultSectionSize(100)
        
        # セクションをA, B, C...にする
        def header_data(section, orientation, role):
            if role != Qt.DisplayRole:
                return None
            if orientation == Qt.Horizontal:
                # 0->A, 1->B...
                res = ""
                s = section
                while s >= 0:
                    res = chr(65 + (s % 26)) + res
                    s = s // 26 - 1
                return res
            else:
                return str(section + 1)
        self.model.headerData = header_data

        # テーブルの右クリックメニュー
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)

        self._setup_ui()

    def _setup_ui(self):
        # ツールバー（ファイルIO）
        toolbar_file = QToolBar("File")
        self.addToolBar(toolbar_file)
        
        action_open = QAction("開く", self)
        action_open.triggered.connect(self.open_file)
        toolbar_file.addAction(action_open)
        
        action_save = QAction("保存", self)
        action_save.triggered.connect(self.save_file)
        toolbar_file.addAction(action_save)

        # ツールバー（ツール群）
        toolbar_tools = QToolBar("Tools")
        self.addToolBar(toolbar_tools)
        
        action_compare = QAction("差分比較テスト", self)
        action_compare.triggered.connect(self.test_compare)
        toolbar_tools.addAction(action_compare)

        # メインウィジェットとレイアウト
        central = QWidget()
        layout = QVBoxLayout()
        
        # SQL/数式入力バー
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("fx / SQL:"))
        self.sql_input = QLineEdit()
        self.sql_input.setPlaceholderText('例: =sql("select * from テーブル名") または数式')
        form_layout.addWidget(self.sql_input)
        
        run_btn = QPushButton("実行 (Enter)")
        run_btn.clicked.connect(self.apply_formula)
        self.sql_input.returnPressed.connect(self.apply_formula)
        form_layout.addWidget(run_btn)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.table_view)
        
        central.setLayout(layout)
        self.setCentralWidget(central)

        # 選択セルが変わった時のイベント（数式バーの更新）
        self.table_view.selectionModel().currentChanged.connect(self.on_cell_selected)

    def on_cell_selected(self, current, previous):
        if not current.isValid():
            return
        r, c = current.row(), current.column()
        # 数式があれば数式を、なければ値を表示
        formula = self.model.formulas.get((r, c))
        if formula:
            self.sql_input.setText(formula)
        else:
            val = self.model.values.get((r, c), "")
            self.sql_input.setText(str(val))

    def apply_formula(self):
        current = self.table_view.currentIndex()
        if not current.isValid():
            return
        
        text = self.sql_input.text()
        self.model.setData(current, text, Qt.EditRole)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        action_name_range = QAction("選択範囲に名前を付ける", self)
        action_name_range.triggered.connect(self.name_selected_range)
        menu.addAction(action_name_range)
        
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def name_selected_range(self):
        selection = self.table_view.selectionModel().selection()
        if selection.isEmpty():
            QMessageBox.warning(self, "エラー", "範囲を選択してください。")
            return
            
        # 単一の連続した矩形選択と仮定
        rect = selection[0]
        start_r = rect.top()
        end_r = rect.bottom()
        start_c = rect.left()
        end_c = rect.right()
        
        name, ok = QInputDialog.getText(self, "範囲に名前を付ける", "範囲名 (SQLのテーブル名として使われます):")
        if ok and name:
            self.model.set_named_range(name, start_r, start_c, end_r, end_c)
            QMessageBox.information(self, "完了", f"「{name}」として範囲を保存しました。\n SQLiteで参照可能です。")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "ファイルを開く", "", "Supported Files (*.csv *.xlsx *.xls)")
        if path:
            try:
                data = load_file(path)
                self.model.load_data(data)
                QMessageBox.information(self, "完了", "読み込みました。\n(CSVの場合、先頭ゼロは保持されています)")
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "ファイルを保存", "", "CSV (*.csv);;Excel (*.xlsx)")
        if path:
            try:
                data = self.model.get_data_list()
                save_file(path, data)
                QMessageBox.information(self, "完了", "保存しました。")
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))

    def test_compare(self):
        """
        簡易的なシート比較テストの実装（同じ位置のセル比較）
        C++オフロードを想定したextension_apiを通じた比較処理の呼び出しを含む
        """
        QMessageBox.information(self, "機能の解説", "「シート及び名前を付けたセル範囲の比較」機能です。\n現在のシート全体同士を仮想的に自身と比較するテストを実行します(機能確認用)。")
        
        data = self.model.get_data_list()
        # 同じデータを比較（モック）し、その結果を表示
        result = extension_api.compare_cells_position(data, data)
        # ログ等で結果を確認 (GUIにはダイアログで一部出力)
        
        if result and result[0]:
            QMessageBox.information(self, "比較結果", f"1行目の比較結果: {result[0]}")
