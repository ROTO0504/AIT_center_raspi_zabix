# GPIO Test Program - 改良版

## 変更内容

### 重要な修正

1. **Pin 17 の問題を解決**: GPIO 17 は 3.3V 電源ピンのため、GPIO 16 (物理ピン 36 番) に変更
2. **エラーハンドリングの強化**: GPIO 設定エラーを適切にキャッチして表示
3. **ピン可用性チェック**: GPIO ピンが使用可能かどうかを事前に確認
4. **クリーンアップの改善**: GPIO クリーンアップ時のエラーを適切に処理

### 現在のピン設定

- **SWITCH_PIN**: GPIO 16 (物理ピン 36 番) - 元々の GPIO 17 から変更
- **LIGHT_PIN**: GPIO 18 (物理ピン 12 番) - 変更なし

## 使用方法

### 基本的なテスト

```bash
# 自動テストシーケンスを実行
python3 GPIO_test.py --test

# GPIO 16のみをONにする
python3 GPIO_test.py --pin16-on

# 手動制御モード
python3 GPIO_test.py --manual

# 点滅テスト
python3 GPIO_test.py --blink
```

### Raspberry Pi 以外の環境での強制実行

```bash
# 環境変数を使用
FORCE_RASPBERRY_PI=1 python3 GPIO_test.py --test

# コマンドラインオプションを使用
python3 GPIO_test.py --force-raspi --test
```

## エラー解決

### "GPIO channel has not been set up as an OUTPUT" エラーの対処

1. **GPIO ピンの競合**: 他のプロセスが GPIO を使用していないか確認
2. **権限の問題**: `sudo` でプログラムを実行してみる
3. **ピンの物理的確認**: GPIO 16 (物理ピン 36 番) が正しく接続されているか確認

### デバッグ情報の確認

プログラムは詳細なエラー情報を表示するので、以下を確認してください：

- GPIO 初期化時のエラーメッセージ
- ピン可用性チェックの結果
- プラットフォーム検出の状況

## トラブルシューティング

### GPIO 16 が使用できない場合

プログラム内の`SWITCH_PIN`を別の GPIO ピンに変更してください：

```python
SWITCH_PIN = 20  # 例：GPIO 20に変更
```

### 利用可能な GPIO ピン（Raspberry Pi）

- GPIO 2, 3, 4, 5, 6, 12, 13, 16, 19, 20, 21, 26 など
- 避けるべきピン：GPIO 17 (3.3V 電源)、GPIO 14/15 (UART)

## 改良点

1. GPIO 初期化フラグによる重複初期化の防止
2. 各 GPIO 操作での個別エラーハンドリング
3. ピン可用性の事前チェック機能
4. より詳細なエラーメッセージと解決のヒント
