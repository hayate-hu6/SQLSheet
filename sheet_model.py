import re
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QFont
from sql_engine import sql_engine
from formula_parser import FormulaParser, extract_dependencies

class SheetCommand:
    """Undo/Redo用のコマンドオブジェクト"""
    def __init__(self, model, changes):
        self.model = model
        self.changes = changes  # [ {"r": r, "c": c, "old_val": ov, "new_val": nv, "old_f": of, "new_f": nf, "old_bg": ob, "new_bg": nb, "old_font": ofnt, "new_font": nfnt} ]
        
    def undo(self):
        for chg in self.changes:
            r, c = chg["r"], chg["c"]
            if chg.get("old_val") is not None:
                self.model.values[(r, c)] = chg["old_val"]
            if chg.get("old_f") is not None:
                if chg["old_f"] == "":
                    self.model.formulas.pop((r, c), None)
                else:
                    self.model.formulas[(r, c)] = chg["old_f"]
            if chg.get("old_bg") is not None:
                self.model.backgrounds[(r, c)] = chg["old_bg"]
            if chg.get("old_font") is not None:
                self.model.fonts[(r, c)] = chg["old_font"]
            self.model.dataChanged.emit(self.model.index(r, c), self.model.index(r, c), [])
        self.model.recalculate_all()

    def redo(self):
        for chg in self.changes:
            r, c = chg["r"], chg["c"]
            if chg.get("new_val") is not None:
                self.model.values[(r, c)] = chg["new_val"]
            if chg.get("new_f") is not None:
                if chg["new_f"] == "":
                    self.model.formulas.pop((r, c), None)
                else:
                    self.model.formulas[(r, c)] = chg["new_f"]
            if chg.get("new_bg") is not None:
                self.model.backgrounds[(r, c)] = chg["new_bg"]
            if chg.get("new_font") is not None:
                self.model.fonts[(r, c)] = chg["new_font"]
            self.model.dataChanged.emit(self.model.index(r, c), self.model.index(r, c), [])
        self.model.recalculate_all()


class SheetModel(QAbstractTableModel):
    dataChangedSignal = Signal(int, int)

    def __init__(self, rows=100, cols=26, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        
        self.formulas = {}
        self.values = {}
        self.backgrounds = {}
        self.fonts = {}
        self.named_ranges = {}
        
        # 依存グラフ deps[(r, c)] = [(dep_r, dep_c), ...] （(r, c) が更新されたら依存先も更新）
        self.deps = {}
        self.parser = FormulaParser(self.get_value_for_parser)
        
        # Undo/Redoスタック
        self.undo_stack = []
        self.redo_stack = []

    def get_value_for_parser(self, r, c):
        return self.values.get((r, c), "")

    def rowCount(self, parent=QModelIndex()):
        return self._rows

    def columnCount(self, parent=QModelIndex()):
        return self._cols

    def load_data(self, data_list):
        self.beginResetModel()
        self.formulas.clear()
        self.values.clear()
        self.backgrounds.clear()
        self.fonts.clear()
        self.named_ranges.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.deps.clear()
        
        for r, row in enumerate(data_list):
            for c, val in enumerate(row):
                if val is not None and str(val) != "":
                    self.values[(r, c)] = str(val)
        
        if data_list:
            if len(data_list) > self._rows:
                self._rows = len(data_list) + 10
            max_col = max(len(r) for r in data_list)
            if max_col > self._cols:
                self._cols = max_col + 5
                
        self.endResetModel()

    def get_data_list(self):
        max_r, max_c = 0, 0
        if self.values:
            max_r = max(r for r, c in self.values.keys())
            max_c = max(c for r, c in self.values.keys())
            
        result = []
        for r in range(max_r + 1):
            row = []
            for c in range(max_c + 1):
                val = self.formulas.get((r, c), self.values.get((r, c), ""))
                row.append(val)
            result.append(row)
        return result

    def set_named_range(self, name, start_r, start_c, end_r, end_c):
        self.named_ranges[name] = (start_r, start_c, end_r, end_c)
        data = []
        for r in range(start_r, end_r + 1):
            row = []
            for c in range(start_c, end_c + 1):
                row.append(self.values.get((r, c), ""))
            data.append(row)
        sql_engine.update_named_range(name, data)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        
        if role == Qt.DisplayRole:
            return self.values.get((r, c), "")
        elif role == Qt.EditRole:
            if (r, c) in self.formulas:
                return self.formulas[(r, c)]
            return self.values.get((r, c), "")
        elif role == Qt.BackgroundRole:
            if (r, c) in self.backgrounds:
                return self.backgrounds[(r, c)]
        elif role == Qt.FontRole:
            if (r, c) in self.fonts:
                f = QFont()
                f.setBold(self.fonts[(r, c)].get("bold", False))
                return f
        return None

    def execute_command(self, changes):
        """状態変更をコマンドとして実行し、Undoスタックに積む"""
        cmd = SheetCommand(self, changes)
        cmd.redo() # ここでは値の適用のみ。再計算は後で行う
        self.undo_stack.append(cmd)
        self.redo_stack.clear()
        
    def undo(self):
        if self.undo_stack:
            cmd = self.undo_stack.pop()
            cmd.undo()
            self.redo_stack.append(cmd)

    def redo(self):
        if self.redo_stack:
            cmd = self.redo_stack.pop()
            cmd.redo()
            self.undo_stack.append(cmd)

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
            
        r, c = index.row(), index.column()
        value = str(value).strip()
        
        old_val = self.values.get((r, c), "")
        old_f = self.formulas.get((r, c), "")
        
        change = {
            "r": r, "c": c,
            "old_val": old_val, "old_f": old_f,
            "new_val": "", "new_f": ""
        }

        if value.startswith("="):
            change["new_f"] = value
        else:
            change["new_val"] = value

        # Undoスタックに登録して即時適用
        self.execute_command([change])

        # 計算が必要なら行う
        if value.startswith("="):
            self.update_dependencies(r, c, value)
        else:
            # 自分が更新されたため、自分に依存するセルも再計算する
            pass 
        
        # 全体再計算（依存グラフに基づいて処理するのが理想だがMVPのため一旦全走査）
        self.recalculate_all()
        return True

    def set_cell_style(self, indexes, bg_color=None, bold=None):
        changes = []
        for idx in indexes:
            r, c = idx.row(), idx.column()
            chg = {"r": r, "c": c}
            if bg_color is not None:
                chg["old_bg"] = self.backgrounds.get((r, c), QColor(Qt.white))
                chg["new_bg"] = bg_color
            if bold is not None:
                old_f = self.fonts.get((r, c), {"bold": False})
                chg["old_font"] = old_f
                chg["new_font"] = {"bold": bold}
            changes.append(chg)
        if changes:
            self.execute_command(changes)

    def update_dependencies(self, r, c, formula_text):
        # 以前の依存関係をクリア（双方向管理は一旦略、単純のため）
        deps = extract_dependencies(formula_text)
        # r, c は deps に依存する
        # (MVPのため全走査による再計算で代用し、厳密な依存グラフは省略)
        pass

    def recalculate_all(self):
        # SQL数式と通常数式を評価する
        for (r, c), f_text in self.formulas.items():
            upper = f_text.upper()
            if upper.startswith("=SQL("):
                match = re.search(r'=sql\(\s*[\'"](.*?)[\'"]\s*\)', f_text, re.IGNORECASE)
                if match:
                    query = match.group(1)
                    result_data = sql_engine.execute_sql(query)
                    self.spill_result(r, c, result_data)
                else:
                    self.values[(r, c)] = "Error"
            else:
                res = self.parser.evaluate(f_text)
                self.values[(r, c)] = res
                
        self.dataChanged.emit(self.index(0, 0), self.index(self._rows-1, self._cols-1), [Qt.DisplayRole])

    def spill_result(self, start_r, start_c, result_data):
        if not result_data:
            self.values[(start_r, start_c)] = ""
            return
            
        row_count = len(result_data)
        col_count = len(result_data[0]) if row_count > 0 else 0
        
        if start_r + row_count > self._rows:
            self.beginInsertRows(QModelIndex(), self._rows, start_r + row_count - 1)
            self._rows = start_r + row_count
            self.endInsertRows()
            
        max_col_needed = start_c + col_count
        if max_col_needed > self._cols:
            self.beginInsertColumns(QModelIndex(), self._cols, max_col_needed - 1)
            self._cols = max_col_needed
            self.endInsertColumns()
            
        for i, row in enumerate(result_data):
            for j, val in enumerate(row):
                self.values[(start_r + i, start_c + j)] = str(val)

    def insertRows(self, row, count, parent=QModelIndex()):
        self.beginInsertRows(parent, row, row + count - 1)
        # 座標のシフト処理 (MVPのため今回は全データの再構築を行うか、シンプルに拡張のみ)
        # 本格対応には values 辞書のキー(r, c)のrをインクリメントする処理が必要
        new_values = {}
        for (r, c), v in self.values.items():
            if r >= row:
                new_values[(r + count, c)] = v
            else:
                new_values[(r, c)] = v
        self.values = new_values

        new_formulas = {}
        for (r, c), v in self.formulas.items():
            if r >= row:
                new_formulas[(r + count, c)] = v
            else:
                new_formulas[(r, c)] = v
        self.formulas = new_formulas
        
        self._rows += count
        self.endInsertRows()
        return True

    def insertColumns(self, column, count, parent=QModelIndex()):
        self.beginInsertColumns(parent, column, column + count - 1)
        new_values = {}
        for (r, c), v in self.values.items():
            if c >= column:
                new_values[(r, c + count)] = v
            else:
                new_values[(r, c)] = v
        self.values = new_values
        self._cols += count
        self.endInsertColumns()
        return True

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
