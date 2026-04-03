# C++ 拡張開発ガイド

Pythonのみでは処理速度が不足する箇所（数万行以上のデータ比較、複雑なセル計算、行列演算など）を最適化するためのモジュール配置場所です。

## プラグインの追加方法

1. C++モジュールを開発し、DLL（Windows）または .so（Linux）としてビルドします（`pybind11` や標準的なC Interface `ctypes`向けを推奨）。
2. ビルドしたライブラリを本ディレクトリに配置します。
3. ルートディレクトリの `extension_api.py` 内で、配置したライブラリをロードし、関数をバインドする処理を記述してください。

### 例：C++側のインターフェース設計 (ctypes向け)
```cpp
extern "C" {
    // 位置ベース比較処理のC++オフロード用例
    __declspec(dllexport) void compare_ranges_position(
        const char** dataA, int rowsA, int colsA,
        const char** dataB, int rowsB, int colsB,
        char** outData
    ) {
        // C++側の高速処理
    }
}
```
