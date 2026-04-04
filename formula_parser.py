import re
import ast

def col_letter_to_index(letter):
    idx = 0
    for char in letter.upper():
        idx = idx * 26 + (ord(char) - ord('A') + 1)
    return idx - 1

def index_to_col_letter(idx):
    res = ""
    s = idx
    while s >= 0:
        res = chr(65 + (s % 26)) + res
        s = s // 26 - 1
    return res

def parse_cell_ref(ref):
    """'A1' -> (0, 0)"""
    match = re.match(r"^([A-Z]+)(\d+)$", ref, re.IGNORECASE)
    if not match:
        return None
    col_str, row_str = match.groups()
    col = col_letter_to_index(col_str)
    row = int(row_str) - 1
    return (row, col)

def extract_dependencies(formula_text):
    """"=A1+B1" から ['A1', 'B1'] などの依存先座標タプルリストを抽出"""
    if not formula_text.startswith("="):
        return []
    
    # セル参照らしい文字列を抽出
    # ただしSUM(A1:A5)の範囲表現もあるため少し複雑になる
    refs = set()
    # A1, Z99 などの単一参照
    matches = re.findall(r"\b([A-Z]+\d+)\b", formula_text.upper())
    for m in matches:
        coord = parse_cell_ref(m)
        if coord:
            refs.add(coord)
            
    # A1:B3 などの範囲参照
    range_matches = re.findall(r"\b([A-Z]+\d+:[A-Z]+\d+)\b", formula_text.upper())
    for r_str in range_matches:
        start_str, end_str = r_str.split(":")
        start_c = parse_cell_ref(start_str)
        end_c = parse_cell_ref(end_str)
        if start_c and end_c:
            for r in range(min(start_c[0], end_c[0]), max(start_c[0], end_c[0]) + 1):
                for c in range(min(start_c[1], end_c[1]), max(start_c[1], end_c[1]) + 1):
                    refs.add((r, c))
    return list(refs)

class FormulaParser:
    def __init__(self, data_provider):
        """
        data_provider: 引数 (row, col) を受け取り、現在の評価値を返す関数
        """
        self.data_provider = data_provider

    def _get_value(self, ref_str):
        coord = parse_cell_ref(ref_str)
        if not coord:
            return 0
        val = self.data_provider(*coord)
        try:
            return float(val) if val != "" else 0.0
        except ValueError:
            return 0.0

    def evaluate(self, formula_text):
        if not formula_text.startswith("="):
            return formula_text
            
        expr = formula_text[1:].upper()

        if expr.startswith("SQL("):
            # SQL関数は専用処理するためここでは扱わない（sheet_model側でキャッチする想定）
            return formula_text

        # 簡易的な SUM 関数の展開 SUM(A1:A3) -> (valA1 + valA2 + valA3)
        def replace_sum(match):
            inner = match.group(1)
            # A1:A3 形式か A1,A2 形式か
            if ":" in inner:
                start_str, end_str = inner.split(":")
                start_c = parse_cell_ref(start_str.strip())
                end_c = parse_cell_ref(end_str.strip())
                if start_c and end_c:
                    vals = []
                    for r in range(min(start_c[0], end_c[0]), max(start_c[0], end_c[0]) + 1):
                        for c in range(min(start_c[1], end_c[1]), max(start_c[1], end_c[1]) + 1):
                            val = self.data_provider(r, c)
                            try:
                                vals.append(float(val) if val != "" else 0.0)
                            except ValueError:
                                vals.append(0.0)
                    return str(sum(vals))
            return "0"

        expr = re.sub(r'SUM\(([^)]+)\)', replace_sum, expr)
        
        # AVERAGE の展開
        def replace_avg(match):
            inner = match.group(1)
            if ":" in inner:
                start_str, end_str = inner.split(":")
                start_c = parse_cell_ref(start_str.strip())
                end_c = parse_cell_ref(end_str.strip())
                if start_c and end_c:
                    vals = []
                    for r in range(min(start_c[0], end_c[0]), max(start_c[0], end_c[0]) + 1):
                        for c in range(min(start_c[1], end_c[1]), max(start_c[1], end_c[1]) + 1):
                            val = self.data_provider(r, c)
                            try:
                                vals.append(float(val) if val != "" else 0.0)
                            except ValueError:
                                pass
                    return str(sum(vals)/len(vals)) if vals else "0"
            return "0"

        expr = re.sub(r'AVERAGE\(([^)]+)\)', replace_avg, expr)

        # 残りのセル参照（A1とか）の展開
        def replace_cell(match):
            ref = match.group(1)
            return str(self._get_value(ref))
            
        expr = re.sub(r"\b([A-Z]+\d+)\b", replace_cell, expr)
        
        # 安全な評価のための ast.literal_eval を行うと数式(+ - * /)が解けないので、
        # ast.parse を用いて安全な数式のみを評価する簡易Evalを実装。
        # 今回はPython標準の制限付き eval を利用（MVPのため）
        try:
            allowed_names = {"__builtins__": None}
            result = eval(expr, allowed_names, {})
            # 小数点以下が不要なら整数化
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except Exception as e:
            return f"#ERROR! ({e})"
