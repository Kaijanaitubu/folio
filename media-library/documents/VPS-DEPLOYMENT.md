# 個人版FolioのLinux VPS運用

移行日：2026-10-14。Ubuntu 24.04・1GB VPSで、FolioをTailscale内に提供している。一般公開版のアカウント・共有カタログは別の改修。

## 配置

- コード：`/opt/folio`（管理者が更新。実行ユーザーから書き換えない）
- DB：`/var/lib/folio/library.sqlite3`
- SQLiteスナップショット：`/var/lib/folio/backups`（直近7世代）
- アプリ実行ユーザー：`folio`（ログイン不可）
- アプリ接続：`127.0.0.1:8765`、外部にはTailscale ServeのHTTPSから接続
- 実行設定：[folio.service](../deploy/linux/folio.service)。自動起動・障害時再起動・権限制限・メモリ上限を設定

初期構築では `apt install git python3-pil python3-cryptography ca-certificates curl` を利用。Pillowは画像縮小、cryptographyはLinuxのAPIキー暗号化に使用する。Windows版の標準ライブラリ動作とDPAPI保存を維持する。

ソースを `/opt/folio` に管理者所有で配置してから、`sudo sh /opt/folio/media-library/deploy/linux/install.sh` を実行する。実行ユーザー・DB保存ディレクトリ・サーバー用暗号鍵・systemd設定を作り、Folioを起動する。既存の暗号鍵は上書きしない。クラウド用のunitは配置するが、タイマーは自動で有効にしない。Tailscaleの登録・Serve設定、DB移行、SSH／ファイアウォール設定はこのインストーラーとは別に行う。

Tailscaleは [公式Linux手順](https://tailscale.com/docs/install/linux) で導入し、利用者自身がログインを承認する。既存のPC／スマホと同じtailnetへ登録する。[Serve](https://tailscale.com/docs/features/tailscale-serve) で `127.0.0.1:8765` をHTTPS中継する。Funnelによるインターネット公開は使わない。

## APIキーの保存

Windowsに保存したDPAPI暗号文はVPSへ移さない。Importsでキーを再接続する。

Linuxでは、systemdの `LoadCredential` が32バイトのサーバー専用鍵を実行プロセスへ渡す。元鍵は `/etc/folio/nhentai-master` に管理者だけが読める権限で保存する。`FOLIO_KEY_FILE` と鍵の双方が設定された場合だけ「保存」を有効にする。

保存形式は [cryptographyのAES-GCM](https://cryptography.io/en/latest/hazmat/primitives/aead/) による認証付き暗号化。毎回新しい12バイトnonceを生成し、暗号文は `/var/lib/folio/private/nhentai-api-key.aesgcm` へ0600で原子的に保存する。SQLite・Git・DBバックアップにはキーと復号鍵を含めない。暗号文が壊れている／鍵が違う場合は未接続として扱い、手動再接続する。これらのファイルを失った場合も再入力で復旧する。

## 外部バックアップ

**2026-10-14：利用者の希望でOneDrive接続は後回しに変更。** 空き容量を整理するまでは、設定画面の「データベースのバックアップをダウンロード」で別端末へ手動保存する。VPS内の毎日の7世代バックアップは継続する。以下のクラウド設定は準備資料であり、タイマーは無効、アップロード・復元は未確認。

ダウンロードはトークンとOriginを確認したPOSTで、一貫したSQLiteスナップショットを作り、ZIPに圧縮して送る。ZIP内にはSQLiteファイルが一つ入る。ゴミ箱・履歴・取込ジョブも含む全DBであり、画像・APIキー・rclone設定は含まない。DB自体は暗号化していないので、バックアップは本人だけがアクセスできる場所で管理する。サーバー内だけのバックアップはVPS自体の障害を防げないため、手元へ定期保存する。

設定画面からダウンロードし、端末のダウンロード先にZIPが保存されたことを確認する。現行ライブラリでは約13MBのZIP（展開後約40MB）になる。回線によって数分かかる場合がある。ボタンの完了表示だけでなく、端末側で保存されたファイルを確認する。

復元時はZIPを展開し、SQLiteファイルをVPSの `/var/lib/folio/imports/` など、folioユーザーだけが読める場所へ置く。動作中のインポートや編集中の作品がないことを確認し、サービスを停止して次のように復元する。ファイル名は実際の保存名に置き換える。

```sh
sudo systemctl stop folio
sudo -u folio env MEDIA_DB=/var/lib/folio/library.sqlite3 MEDIA_BACKUPS=/var/lib/folio/backups python3 /opt/folio/media-library/server.py --restore /var/lib/folio/imports/library-YYYYMMDD-HHMMSS-NNNNNN.sqlite3
sudo systemctl start folio
```

復元処理は入力ファイルの整合性と外部キーを検査し、既存DBをバックアップしてから置き換える。失敗した場合は原因を調べ、未確認のファイルで運用を再開しない。

PCのOneDrive同期はLinuxには引き継がれない。VPSからrcloneでOneDriveへ直接送る方式を用意する。利用者のMicrosoftログイン・同意と、送信先ドライブの確認が完了するまで接続済みとは扱わない。

- rclone設定：`/var/lib/folio/private/rclone.conf`、folioのみが読める0600。アクセストークン等はGit・チャットへ出さない
- 初期送信先：`onedrive:tubu/Programing/folio/vps-backups`。利用者が指定した専用フォルダの子フォルダ
- [cloud_backup.py](../deploy/linux/cloud_backup.py) はSQLite backup APIで一貫したスナップショットを作成し、整合性を検査後、一ファイルだけアップロードする
- アップロード後はrclone checkでリモートをダウンロード比較し、成功時だけローカルの `last-cloud-backup.json` を更新
- [バックアップサービス](../deploy/linux/folio-cloud-backup.service) と [タイマー](../deploy/linux/folio-cloud-backup.timer) で毎日日本時間04:15頃に実行。構成・初回アップロード・復元試験が通ってからタイマーを有効化
- OneDriveの既存ファイルの削除や同期はしない。外部の世代削除方針は後で決める

## 移行の順序

1. 空DBでサーバー・検索・各取得元のメタデータとRAM画像・再起動を確認。
2. 別端末へ保存できるバックアップを確認。クラウド自動バックアップは利用者の希望で保留にし、手動ダウンロードを使う。
3. PC版の実ジョブ・接続状態を調べ、一括取込の途中で停止しない。
4. PC版の書き込みを停止して最終SQLiteバックアップを取得。DBスナップショットだけをVPSへ送る。
5. VPSのDBを復元し、全テーブルの内容・件数・整合性を照合。確認前にVPSのジョブを勝手に再開しない。
6. PC版の自動起動を止め、スマホのPWAとブックマークレットをVPSのURLへ変更。
7. PC停止中のスマホアクセス、VPS再起動後の自動復旧、バックアップを確認。

切り戻す場合はVPS運用後の最新スナップショットをPCへ戻す。古いPCのDBをそのまま再開すると、新しく編集した情報が欠落する。

## 管理操作

VPS内で実行する。

```sh
sudo systemctl status folio
sudo journalctl -u folio -n 50
sudo systemctl restart folio
sudo tailscale serve status
sudo systemctl status folio-cloud-backup.timer
sudo journalctl -u folio-cloud-backup -n 30
```

資料へ管理パスワード・認証トークン・秘密鍵を記録しない。アプリの更新ではコードだけを配備し、`/var/lib/folio` と `/etc/folio` をソースコードで上書きしない。Windowsから取得したLinux用スクリプト・unitファイルはLFを使う（Git属性で指定）。

## 2026-10-14：試験配備の確認

- 空DBでsystemdサービスが起動し、127.0.0.1:8765にだけ待ち受けていることを確認。Tailscale登録は利用者が承認済み、Serve経由のHTTPSでconfig・作品一覧・キー保存状態がHTTP 200。
- Linuxの独立した試験フォルダでPython195件を実行し成功、Windows専用DPAPIテスト1件はスキップ。暗号文の改ざん・異なる鍵・新nonce・再読込・0600・消去を合成キーで検証。
- Windowsでキー関連24件（1件Linux専用スキップ）と画像縮小5件が成功。
- Ubuntu標準PillowのAVIF非搭載に対応し、使用可能なデコーダーだけを選択する。未対応形式や不正画像は既存のエラー／フォールバックへ渡す。
- VPSからHitomi・momon-ga・DLsite・FANZAのメタデータとRAM画像取得を確認。nhentaiは既存のnhentai画像URL一件の取得を確認し、APIキーを必要とするメタデータ・Favoritesは未接続。
- この試験配備の時点では本番切り替え前だった。後述の切り替えで実DB移行・PC版停止・管理接続設定を完了した。OneDriveは保留。

## 2026-10-14：本番データの切り替え

- 利用者が追加の管理接続設定を明示承認したため、UFWのSSH／Tailscale受信許可とSSH鍵限定・rootログイン禁止を適用。適用後もSSH鍵で再接続できることを確認。
- OneDriveのログイン承認は完了したがドライブ取得でHTTP 400になり、利用者の希望で作業を中断。自動アップロードはしていない。rcloneの設定は非公開のprivateフォルダのみ。公式rclone 1.75.1は公式の署名鍵fingerprintとGPG署名・SHA256を確認して導入した。
- PC版は動作中インポートがないことを確認して停止。最終DBは登録中4,285件、ゴミ箱154件、21テーブルの全内容がVPSへ復元後も一致。整合性ok、外部キー違反なし。
- PCのFolio自動起動ショートカットは `data/vps-migration/` に移し、復旧用に保管した。元のPCのDBも残すが、移行後の普段使いでは再起動しない。
- 手動バックアップのHTTPSダウンロードを試験DBで確認。実DBは圧縮前の転送が途中で止まったためZIPへ変更し、再開後の検証で全12,778,804バイトを約235秒で取得した。ZIPのCRC検査、展開したDBの整合性ok・外部キー違反なし、登録中4,286件・ゴミ箱154件を確認。移行後のユーザー編集を含むため、初期移行時とは件数が異なる。
- Linux上で圧縮ダウンロード・認証／Origin制限・暗号化キー保存・合成クラウド転送の7件を再検証して成功。クラウド試験は模擬転送であり、OneDrive接続が確認できたという意味ではない。
- VPSのFolioサービスは自動起動有効。メモリ上限512MB、RAM画像／キーをコアダンプに書かないようLimitCORE=0。swapは追加していない。
- ユーザーによるPC停止後のスマホ利用、PWAの新URLでの再追加、ブックマークレットの新接続先への再コピーが必要。Windows保存済みのnhentaiキーは移していないため、必要時は新しいImports画面で再接続する。

このPC固有の接続先・SSH鍵パス・切り替え記録は、Git対象外の `data/vps-migration/deployment.json` に保存する。

## 2026-10-14：再開後の最終確認

- Ubuntuの更新を適用し、カーネル6.8.0-147でVPSを実際に再起動。Folio・tailscaled・Serve HTTPSが自動復旧し、SSH鍵で再接続できた。
- 再起動直前と直後の全21テーブルの行内容をハッシュで比較して一致。整合性ok・外部キー違反なし。実HTTPS一覧も4,286件を返した。
- UFW、SSH鍵限定、rootログイン禁止、127.0.0.1:8765の待ち受けが再起動後も維持された。クラウドタイマーは無効のまま、サーバー内のSQLiteバックアップは7世代。
- `apparmor` と `libapparmor1` の更新はUbuntu側の段階配信（phased 10%）により保留。強制適用していない。ほかの更新処理は成功。
- 配備したapp.js・feature-text.js・sw.jsがHTTPS配信の内容と一致。VPS向けの説明とバックアップ取得中の表示を確認した。
- nhentaiは未接続だが、Linuxの暗号化保存機能は利用可能。キーの再接続は利用者がImportsで行う。停止していたインポートジョブを勝手に再開していない。

サーバー側の移行・再起動・手動バックアップ検証は完了。残る利用確認は、PC停止中のスマホアクセス、新URLでのホーム画面追加・ブックマークレット更新。OneDriveは保留のままとする。
