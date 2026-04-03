import csv
import pandas as pd

def load_csv(file_path):
    """
    CSVファイルを読み込む。先頭のゼロを保持するため、すべて文字列として扱う。
    """
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                data.append(row)
    except Exception as e:
        print(f"Failed to load CSV: {e}")
    return data

def save_csv(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
    except Exception as e:
        print(f"Failed to save CSV: {e}")

def load_xlsx(file_path):
    """
    Excelファイルを読み込み、リストのリスト形式で返す（先頭のゼロ保持のため dtype=str を指定）。
    複数シート対応は簡略化のため、最初のシートのみ読み込む。
    """
    try:
        df = pd.read_excel(file_path, sheet_name=0, dtype=str)
        df = df.fillna("")
        header = [str(col) if not str(col).startswith("Unnamed:") else "" for col in df.columns.tolist()]
        data = [header] + df.values.tolist()
        return data
    except Exception as e:
        print(f"Failed to load Excel: {e}")
        return []

def save_xlsx(file_path, data):
    try:
        if not data:
            pd.DataFrame().to_excel(file_path, index=False)
            return
        df = pd.DataFrame(data[1:], columns=data[0])
        df.to_excel(file_path, index=False)
    except Exception as e:
        print(f"Failed to save Excel: {e}")

def load_file(file_path):
    """
    拡張子に応じて適切な読み込み処理をディスパッチする。
    戻り値は二次元リスト（[ [row1_col1, row1_col2, ...], [row2_col1, ...] ]）
    """
    if file_path.lower().endswith('.csv'):
        return load_csv(file_path)
    elif file_path.lower().endswith(('.xlsx', '.xls')):
        return load_xlsx(file_path)
    else:
        raise ValueError("Unsupported file format for loading")

def save_file(file_path, data):
    if file_path.lower().endswith('.csv'):
        save_csv(file_path, data)
    elif file_path.lower().endswith(('.xlsx', '.xls')):
        save_xlsx(file_path, data)
    else:
        raise ValueError("Unsupported file format for saving")
