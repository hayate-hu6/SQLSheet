import sqlite3
import re

class SQLEngine:
    """
    オンメモリSQLiteを利用して、名前付き範囲の仮想テーブル化や、
    SQL文の実行を担当するクラス。
    """
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        # ユーザー定義関数等の登録領域
        pass

    def _sanitize_column_name(self, name, index, seen_names):
        """カラム名をSQLで扱いやすいようにサニタイズ（空や重複を回避）"""
        name = str(name).strip()
        if not name:
            name = f"col_{index}"
        
        # SQLiteの予約語や特殊記号をエスケープする簡易処理
        name = re.sub(r'\W+', '_', name)
        
        original_name = name
        counter = 1
        while name in seen_names:
            name = f"{original_name}_{counter}"
            counter += 1
            
        seen_names.add(name)
        return name

    def update_named_range(self, table_name, data):
        """
        名前付き範囲を一時テーブルとして保存する。
        data: [[col1, col2, ...], [row1_data, ...], ...]
        先頭の行をヘッダーとして扱う。
        """
        if not data or len(data) < 2:
            return # ヘッダーと1行以上のデータがないとテーブル化に不向き
        
        raw_header = data[0]
        rows = data[1:]
        
        seen_names = set()
        columns = [self._sanitize_column_name(h, i, seen_names) for i, h in enumerate(raw_header)]
        
        # 既存テーブルをDrop
        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # テーブル作成
        cols_def = ", ".join([f"{col} TEXT" for col in columns])
        create_sql = f"CREATE TABLE {table_name} ({cols_def})"
        self.conn.execute(create_sql)
        
        # データ挿入
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
        
        # データ側の列数がヘッダーと合わない場合の調整
        adjusted_rows = []
        for row in rows:
            adj = list(row)[:len(columns)]
            # 足りない場合は空埋め
            adj += [""] * (len(columns) - len(adj))
            adjusted_rows.append(adj)
            
        self.conn.executemany(insert_sql, adjusted_rows)
        self.conn.commit()

    def execute_sql(self, sql_query):
        """
        任意のSQLクエリを実行し、結果を二次元リストで返す。
        最初の要素はヘッダー（カラム名の一覧）のリスト。
        失敗した場合は例外を投げるかエラーメッセージを含むレコードを返す。
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql_query)
            
            headers = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            if not headers and not rows:
                return []
                
            result = [headers]
            for row in rows:
                result.append(list(row))
                
            return result
        except Exception as e:
            # エラー時はセルに表示するためにエラー文字を返す
            return [[f"SQL Error: {e}"]]

sql_engine = SQLEngine()
