import ctypes
import os
import platform

class CppExtension:
    """
    重い処理（広範囲のセル比較など）をC++にオフロードするためのインターフェース層。
    現在はモック実装として動作し、Python側で処理を行います。
    C++ライブラリがロード可能な場合はそちらに処理を委譲します。
    """
    def __init__(self):
        self._lib = None
        self._load_library()

    def _load_library(self):
        try:
            # 将来的にDLLやsoがビルドされた際に読み込むためのパス
            ext_dir = os.path.join(os.path.dirname(__file__), "cpp_extension")
            ext = ".dll" if platform.system() == "Windows" else ".so"
            lib_path = os.path.join(ext_dir, f"sqlsheet_ext{ext}")
            
            if os.path.exists(lib_path):
                self._lib = ctypes.CDLL(lib_path)
                # print("C++ Extension loaded.")
        except Exception as e:
            # print(f"C++ Extension not loaded. Using Python fallback: {e}")
            pass

    def compare_cells_position(self, table_a, table_b):
        """
        位置ベースの比較
        table_a, table_b = [[col1, col2, ...], [col1, col2, ...], ...]
        戻り値:
        一致する場合、差異がある場合のハイライト情報を返す
        """
        if self._lib:
            # C++実装へ処理を委譲する想定
            pass
        
        # Pythonによるフォールバック実装
        max_rows = max(len(table_a), len(table_b))
        max_cols = 0
        for r in table_a + table_b:
            max_cols = max(max_cols, len(r))
            
        result = []
        for r in range(max_rows):
            row_result = []
            for c in range(max_cols):
                val_a = table_a[r][c] if r < len(table_a) and c < len(table_a[r]) else None
                val_b = table_b[r][c] if r < len(table_b) and c < len(table_b[r]) else None
                
                if val_a == val_b:
                    row_result.append({"status": "match", "val": val_a})
                else:
                    row_result.append({"status": "diff", "val": f"{val_a} -> {val_b}"})
            result.append(row_result)
        return result

    def compare_cells_key(self, table_a, table_b, key_indices):
        """
        キー指定による比較
        key_indices: 主キーとして扱う列のインデックスリスト
        """
        if self._lib:
            pass

        # Python実装
        # 各行のキーを元に辞書を作成して比較
        dict_a = {}
        for row in table_a:
            key = tuple(row[i] for i in key_indices if i < len(row))
            dict_a[key] = row
            
        dict_b = {}
        for row in table_b:
            key = tuple(row[i] for i in key_indices if i < len(row))
            dict_b[key] = row
            
        result = []
        all_keys = set(dict_a.keys()).union(set(dict_b.keys()))
        for key in all_keys:
            if key not in dict_a:
                result.append({"status": "added", "val_b": dict_b[key]})
            elif key not in dict_b:
                result.append({"status": "deleted", "val_a": dict_a[key]})
            else:
                row_a = dict_a[key]
                row_b = dict_b[key]
                if row_a == row_b:
                    result.append({"status": "match", "val_a": row_a, "val_b": row_b})
                else:
                    result.append({"status": "modified", "val_a": row_a, "val_b": row_b})
                    
        return result

extension_api = CppExtension()
