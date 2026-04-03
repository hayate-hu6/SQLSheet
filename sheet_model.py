import re
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from sql_engine import sql_engine

class SheetModel(QAbstractTableModel):
    # 値が変更されたときにシグナルを発火（UI連携用）
    dataChangedSignal = Signal(int, int)

    def __init__(self, rows=100, cols=26, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        
        # formulas: {(row, col): "=sql(...)"}
        self.formulas = {}
        # values: {(row, col): "Result value"}
        self.values = {}
        
        # 名前付き範囲: {"TableName": (start_row, start_col, end_row, end_col)}
        self.named_ranges = {}

    def rowCount(self, parent=QModelIndex()):
        return self._rows

    def columnCount(self, parent=QModelIndex()):
        return self._cols

    def load_data(self, data_list):
        """
        ファイル読み込み時など、二次元リストからデータを流し込む
        """
        self.beginResetModel()
        self.formulas.clear()
        self.values.clear()
        self.named_ranges.clear()
        
        for r, row in enumerate(data_list):
            for c, val in enumerate(row):
                if val is not None and str(val) != "":
                    # CSV等からの読み込み時はすべて値として扱う
                    self.values[(r, c)] = str(val)
        
        # 必要に応じてテーブルサイズを拡張
        if data_list:
            if len(data_list) > self._rows:
                self._rows = len(data_list) + 10
            max_col = max(len(r) for r in data_list)
            if max_col > self._cols:
                self._cols = max_col + 5
                
        self.endResetModel()

    def get_data_list(self):
        """
        保存用に二次元リストを返す（値として表示されているもの）
        """
        max_r, max_c = 0, 0
        if self.values:
            max_r = max(r for r, c in self.values.keys())
            max_c = max(c for r, c in self.values.keys())
            
        result = []
        for r in range(max_r + 1):
            row = []
            for c in range(max_c + 1):
                val = self.values.get((r, c), "")
                row.append(val)
            result.append(row)
        return result

    def get_range_data(self, start_r, start_c, end_r, end_c):
        """
        指定範囲のデータを2次元リストで抽出する
        """
        data = []
        r_min, r_max = min(start_r, end_r), max(start_r, end_r)
        c_min, c_max = min(start_c, end_c), max(start_c, end_c)
        for r in range(r_min, r_max + 1):
            row = []
            for c in range(c_min, c_max + 1):
                row.append(self.values.get((r, c), ""))
            data.append(row)
        return data

    def set_named_range(self, name, start_r, start_c, end_r, end_c):
        self.named_ranges[name] = (start_r, start_c, end_r, end_c)
        # SQLiteエンジンに転送
        data = self.get_range_data(start_r, start_c, end_r, end_c)
        sql_engine.update_named_range(name, data)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
            
        r, c = index.row(), index.column()
        
        if role == Qt.DisplayRole:
            # 表示時は結果(values)を返す
            return self.values.get((r, c), "")
        elif role == Qt.EditRole:
            # 編集時は数式(formulas)があればそれを、なければ結果を返す
            if (r, c) in self.formulas:
                return self.formulas[(r, c)]
            return self.values.get((r, c), "")
            
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
            
        r, c = index.row(), index.column()
        value = str(value).strip()
        
        if value.startswith("="):
            self.formulas[(r, c)] = value
            self.evaluate_formula(r, c, value)
        else:
            if (r, c) in self.formulas:
                del self.formulas[(r, c)]
            self.values[(r, c)] = value
            
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled

    def evaluate_formula(self, r, c, formula_text):
        """
        数式の評価（標準の計算や、=sql()に対応）
        """
        upper_text = formula_text.upper()
        if upper_text.startswith("=SQL("):
            # =sql("select ...") の構文をパース
            match = re.search(r'=sql\(\s*[\'"](.*?)[\'"]\s*\)', formula_text, re.IGNORECASE)
            if match:
                query = match.group(1)
                result_data = sql_engine.execute_sql(query)
                self.spill_result(r, c, result_data)
            else:
                self.values[(r, c)] = "Error: Invalid SQL Syntax"
        else:
            # 簡易数式処理(=A1+B1などを実装できるが今回は簡略版)
            try:
                # 非常に限られた安全な評価のみ（※プロダクションではevalを使わない）
                expr = formula_text[1:]
                # TODO: セル参照の変換処理(A1 -> self.values[0,0])が必要
                # 今回は最小構成として実装をスキップし、そのまま表示
                self.values[(r, c)] = f"Formula: {expr}"
            except Exception as e:
                self.values[(r, c)] = f"Error: {e}"

    def spill_result(self, start_r, start_c, result_data):
        """
        複数行・複数列の結果を起点セルから展開（スピル）する
        """
        if not result_data:
            self.values[(start_r, start_c)] = ""
            return
            
        row_count = len(result_data)
        col_count = len(result_data[0]) if row_count > 0 else 0
        
        # 必要ならテーブル自体をリサイズ
        if start_r + row_count > self._rows:
            self.beginInsertRows(QModelIndex(), self._rows, start_r + row_count - 1)
            self._rows = start_r + row_count
            self.endInsertRows()
            
        max_col_needed = start_c + col_count
        if max_col_needed > self._cols:
            self.beginInsertColumns(QModelIndex(), self._cols, max_col_needed - 1)
            self._cols = max_col_needed
            self.endInsertColumns()
            
        # 展開処理
        for i, row in enumerate(result_data):
            for j, val in enumerate(row):
                # 数式は上書きせず値のみスピルする（Excelと同様の挙動にするにはより複雑になるが今回は簡略）
                self.values[(start_r + i, start_c + j)] = str(val)
                
        # 変更シグナル発行
        top_left = self.index(start_r, start_c)
        bottom_right = self.index(start_r + row_count - 1, start_c + col_count - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

