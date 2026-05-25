# トラブルシュート

よくある詰まりどころをまとめます。

短く逆引きしたい場合は [FAQ](faq.md) も見てください。

## Windows EXEエクスポートが始まらない

未commitの変更があると、GitHub Actionsはローカルの内容をビルドできません。`git status` を確認し、必要な変更をcommitしてpushしてください。

## GitHub authentication is not configured と表示される

PVNMからGitHub Actionsを起動できない状態です。`gh auth login` を実行する、`PVNM_GITHUB_TOKEN` を設定する、またはSSHキーをGitHubへ登録して `git push` が通る状態にしてください。

## Actionsにエラー表示があるがSuccessになっている

ビルド全体がSuccessならArtifactsは生成されています。ただしログのannotationに古い失敗ログや警告が残って見える場合があります。成果物が生成されているか、実行ログの最終結果がSuccessかを確認してください。

## Web HTMLで素材が表示されない

HTMLだけを移動している可能性があります。`.html`、`<name>_assets/`、`pyxel/` を同じ関係で配置してください。

## Android APKが出力されない

Android SDK、Java/JDK、Node.js/npm、Gradle、署名設定、出力先の権限を確認してください。Release APKの場合は署名設定が必要です。

中間Androidプロジェクトが生成されている場合は、そのフォルダで `./build_android.sh build-debug` または `./build_android.sh build-release` を実行すると、失敗箇所を確認しやすくなります。

## Android Release署名で失敗する

ローカルReleaseビルドでは `pvnm-signing/release.jks` と `pvnm-release-signing.properties` が必要です。初回生成後は必ずバックアップしてください。ActionsでRelease APKを作る場合は、`ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD` のGitHub Secretsを確認してください。

## 画像の色味が環境で違う

表示環境やエクスポート形式によって見え方が変わることがあります。VN Palette Toolで調整し、最終的には配布対象の環境で確認してください。
