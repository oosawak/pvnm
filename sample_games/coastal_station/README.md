# 潮待ちステーション

PVNM で作った短編アドベンチャーゲームのサンプルです。

## 内容

- 16 シーン
- 2 箇所の選択肢分岐
- 合流ルート
- エンディング
- EXTRA TEXT
- 生成背景 1 枚
- 悠真の立ち絵 1 枚
- 追加登場人物: 凪、蓮

## 開く

リポジトリルートで PVNM を起動します。

```bash
python3 main.py
```

起動後、`OPEN` から次のファイルを開きます。

```text
sample_games/coastal_station/coastal_station.pvnm
```

## 再生成

台本や分岐をコード側で直したあと、次のコマンドで `.pvnm` を作り直せます。

```bash
python3 sample_games/coastal_station/build_project.py
```

## ファイル

```text
coastal_station.pvnm              PVNM で開くプロジェクト
coastal_station.md                Markdown 取り込み用の台本
build_project.py                  分岐とエンディング込みで .pvnm を生成
assets/coastal_station_dusk.png   背景画像
assets/chars/yuma.png             悠真の立ち絵
```

Markdown 取り込みだけを使う場合、選択肢の遷移先は PVNM 上で設定してください。
`build_project.py` から生成した `.pvnm` には遷移先が設定済みです。
