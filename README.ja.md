# Folio — パーソナルメディアライブラリ

[English](README.md) | [日本語](README.ja.md)

作品の情報を整理するための個人用メディアライブラリです。英語・日本語に対応したレスポンシブUIで、メタデータと別名、自由に設定できる評価軸、検索、ブックマークのインポート、メモリ内だけで画像を扱うサムネイル中継機能を提供します。Pythonの標準ライブラリ、SQLite、ブラウザのJavaScriptで動作します。

## ローカルで起動する

Python 3.11以降が必要です。リポジトリのフォルダで、次のコマンドを実行します。

```sh
cd media-library
python server.py --host 127.0.0.1 --port 8765
```

ブラウザで http://localhost:8765 を開きます。Windows用の起動スクリプト、自動起動、LANからの接続方法、機能の詳細、テスト方法は[アプリの利用ガイド](media-library/README.ja.md)をご覧ください。

現在のバージョンは、アカウント認証のない、共通のローカルライブラリを利用します。自分のPCまたは信頼できるLAN内で運用してください。アカウント登録とインターネットへの公開は今後の対応事項です。

## 開発資料

- [今後の開発・運用ロードマップ（日本語）](media-library/ROADMAP.md) — 新しい要望・提案、決定内容、着手状況、完了をこの資料で管理します。記載された候補が実装承認済みとは限りません。
- [公開版の仕様会議記録](media-library/PUBLIC-EDITION-DISCUSSION.md) — ユーザーの方針、共有カタログへの提案、未決定事項を分けて記録しています。
- [公開版の設計・タグ属性・移行課題](media-library/PUBLIC-EDITION-DESIGN.md)／[常時稼働環境の比較](media-library/HOSTING-COMPARISON.md) — 次回相談用の提案資料です。
- [momon-gaインポーターの実装仕様](media-library/MOMONGA-SPEC.md) — 対応URL・メタデータ・共通タグ方式・RAM内表紙中継。[当初の調査](media-library/MOMONGA-RESEARCH.md)。

以下の資料は英語です。

- [要件仕様書](Personal-Media-Database-Requirements-v2.0.md)
- [検証記録](media-library/VERIFICATION.md)
- [サムネイルの調査記録](media-library/THUMBNAIL-INVESTIGATION.md)
- [nhentai対応と重複判定の検討案](media-library/NHENTAI-AND-DUPLICATES.md)

リポジトリにはアプリのソースコードとドキュメントを含めています。個人のライブラリデータベース、バックアップ、ログ、インポートしたブックマークファイル、ローカルのテスト出力は含めません。新しくインストールすると、空のデータベースが作成されます。

- [F-002 / F-003 / F-013 import specification (日本語)](media-library/IMPORT-SPEC.md)
