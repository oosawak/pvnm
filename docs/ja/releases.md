# リリース配布

PVNMで作った成果物は、GitHub Releasesで配布する前提で整理すると扱いやすくなります。

## 一時ビルドとリリースビルド

| 種類 | 置き場所 | 用途 |
| --- | --- | --- |
| Actions Artifact | GitHub Actionsの実行結果 | テスト用、一時確認用 |
| GitHub Release Asset | Releasesページ | 正規配布用 |

Actions Artifactは、ビルドできたかを確認するための一時的な成果物です。正規配布には、Releaseを作成してzipやAPKをRelease Assetとしてアップロードします。

Artifactをダウンロードできる範囲はリポジトリの権限に従います。Release Assetは、そのReleaseにアクセスできる利用者向けの配布物です。公開用Webサイトからリンクする場合は、正規配布先をRelease Assetに揃えると案内しやすくなります。

## 推奨フロー

1. PVNMで作品を完成させる。
2. 各形式でエクスポートする。
3. Windows EXEはActions Artifactをダウンロードするか、`v*` タグでRelease用ビルドを走らせる。
4. macOS、Web、Androidの成果物を手元またはActions上で確認する。
5. 配布用リポジトリのGitHub Releasesへ成果物をアップロードする。
6. WebサイトからRelease Assetへリンクする。

作品を紹介するWebサイトを別に作る場合は、[作品紹介サイトの作り方](work-website.md) も参照してください。

## 別リポジトリで配布する場合

作品の開発リポジトリと、配布用Webサイトのリポジトリを分ける運用もできます。たとえば、作品リポジトリでWindows EXEをビルドし、Webサイト用リポジトリのReleasesへ成果物をアップロードする流れです。

この場合は、どのリポジトリのどのReleaseが正規配布なのかをWebサイト上で明確にしてください。

## タグ

`v1.0.0` のようなタグは、一般的なリリースバージョンとして使います。`pvnm-windows-build-...` のようなタグは、PVNMからWindows EXEビルドを起動するための一時的なトリガーとして使います。

正規配布では、利用者に見せるバージョンは `v1.0.0` のようなわかりやすいタグに揃えるのがおすすめです。

作品リポジトリ側にRelease用workflowを用意している場合、`v*` タグでWindows EXEやAndroid Release APKのRelease Assetアップロードを走らせる構成にできます。`pvnm-windows-build-*` はWindows確認用Artifactを作るための一時タグで、Release Assetは作りません。
