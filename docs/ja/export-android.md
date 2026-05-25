# Androidエクスポート

Android向けには、Androidプロジェクト、Debug APK、Release APKを書き出せます。

プロジェクトに `assets/images/ui/loading.png` がある場合、Androidアプリ内のWeb起動中ローディング画像として使われます。`assets/images/ui/app_icon.png` がある場合は、Androidのランチャーアイコンへ変換されます。詳しくは [素材と音声](assets-and-audio.md) を見てください。

## メニュー

| メニュー | 出力 | 用途 |
| --- | --- | --- |
| `[ANDROID PROJECT]` | Androidプロジェクト | Android StudioやGradleで扱う |
| `[ANDROID APK DEBUG]` | Debug APK | 手元の端末確認 |
| `[ANDROID APK RELEASE]` | Release APK と `.sha256` | 署名済み配布候補 |

## 必要なもの

Android書き出しには、Android Studio、Android SDK、Android Studio同梱JDKまたはJava 17、Node.js/npm、Python依存パッケージが必要です。Release APKを作る場合は署名設定も必要です。

## Android Project

`[ANDROID PROJECT]` は、CapacitorベースのAndroidプロジェクトを書き出します。出力先には、ゲーム本体のWebファイルに加えて、確認用スクリプトとドキュメントが生成されます。

| ファイル | 用途 |
| --- | --- |
| `www/index.html` | 通常起動用のWeb本体 |
| `www/pvnm_diagnostics.html` | storage/audio/inputなどの診断ページ |
| `www/pvnm_debug.html` | デバッグHUD付き起動ページ |
| `serve_web.sh` | Androidビルド前にWeb版をローカル確認するスクリプト |
| `build_android.sh` | `sync` / `open` / `run` / `build-debug` / `build-release` を実行するスクリプト |
| `android_log.sh` | 端末やWebViewのログ確認用スクリプト |
| `README_PVNM_CAPACITOR.md` | 生成プロジェクトの説明 |

生成後は、まず出力フォルダで次を確認します。

```bash
./serve_web.sh diagnostics
./serve_web.sh debug
```

Android Studioで開く場合は次を実行します。

```bash
./build_android.sh open
```

## Debug APK

`[ANDROID APK DEBUG]` は動作確認用です。PVNMは中間Androidプロジェクトを作り、`build_android.sh build-debug` 相当の処理を実行して、生成された `app-debug.apk` を指定した出力先へコピーします。

手元のAndroid端末にインストールして、画面表示、音声、セーブ、EXTRASなどを確認します。

## Release APK

`[ANDROID APK RELEASE]` は配布候補です。PVNMは中間Androidプロジェクトを作り、`build_android.sh build-release` 相当の処理を実行して、署名済み `app-release.apk` を指定した出力先へコピーします。Release APKでは、同じ場所に `.sha256` も生成されます。

ローカルで初めてReleaseビルドを行うと、中間Androidプロジェクト内に `pvnm-signing/release.jks` と `pvnm-release-signing.properties` が作られます。これは今後のアップデートにも必要な署名鍵です。なくすと同じアプリとして更新できなくなるため、必ずバックアップしてください。Gitにはcommitしないでください。

出力先を変えると中間Androidプロジェクトの場所も変わるため、別の署名鍵が作られることがあります。同じアプリを継続配布する場合は、同じ中間プロジェクトを使うか、既存の署名鍵を環境変数で渡してください。

環境変数で既存の署名鍵を渡すこともできます。

| 環境変数 | 内容 |
| --- | --- |
| `PVNM_ANDROID_KEYSTORE_BASE64` | keystoreをbase64化した文字列 |
| `PVNM_ANDROID_KEYSTORE_FILE` / `PVNM_ANDROID_KEYSTORE_PATH` | 既存keystoreファイルのパス |
| `PVNM_ANDROID_KEYSTORE_PASSWORD` | keystoreパスワード |
| `PVNM_ANDROID_KEY_ALIAS` | key alias。未指定なら `pvnm` |
| `PVNM_ANDROID_KEY_PASSWORD` | key password。未指定ならkeystoreパスワード |

Release APKは署名済みであることを確認し、GitHub Releasesなどへアップロードして配布します。

配布前には、実機で次の項目を確認してください。

| 項目 | 確認内容 |
| --- | --- |
| 起動 | タイトル画面が表示される |
| 画像 | 背景、立ち絵、CGが表示される |
| 音声 | BGMとSEが再生される |
| 操作 | テキスト送り、選択肢、メニュー操作ができる |
| セーブ | セーブ/ロードが動く |
| EXTRAS | エンディング後に開放される |

## 成果物が見つからない場合

出力先を指定しても何も生成されていないように見える場合は、ビルドが最終コピーまで進む前に失敗している可能性があります。Android SDK、Java/JDK、Node.js/npm、Gradle、署名設定、出力先の権限を確認してください。

中間Androidプロジェクトが生成されている場合は、そのフォルダで次を実行して原因を確認します。

```bash
./build_android.sh build-debug
./build_android.sh build-release
./android_log.sh pvnm
```

## GitHub ActionsでRelease APKを作る場合

PVNMのメニューからAndroid用GitHub Actionsを直接起動する機能は現状ありません。Actionsで署名済みRelease APKを作りたい場合は、作品リポジトリ側にAndroidビルド用workflowを用意し、GitHub上で手動実行するか、`v*` タグpushなどで起動する運用にします。

Actionsで署名済みRelease APKを作るには、GitHub Secretsに署名鍵を設定します。

| Secret | 必須 | 内容 |
| --- | --- | --- |
| `ANDROID_KEYSTORE_BASE64` | 必須 | keystoreをbase64化した文字列 |
| `ANDROID_KEYSTORE_PASSWORD` | 必須 | keystoreパスワード |
| `ANDROID_KEY_ALIAS` | 任意 | key alias。未指定なら `pvnm` |
| `ANDROID_KEY_PASSWORD` | 任意 | key password。未指定ならkeystoreパスワード |

Releaseアップロードまで行うworkflowを用意している場合、`v1.0.0` のようなタグで起動して、Release APKと `.sha256` を同じタグのGitHub Releaseへアップロードする構成にできます。手動実行の場合はActions Artifactとして確認する運用が分かりやすいです。
