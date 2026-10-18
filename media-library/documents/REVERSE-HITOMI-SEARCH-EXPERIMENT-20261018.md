# 正規リンクからHitomi投稿を探す実験

実施：2026-10-18。機能実装ではなく読み取り専用の探索実験。

## 結果

| 正規サイト | 対象 | 正規メタデータ取得 | 題名中心の探索で登録済みID回収 | 表記補正・作者補助後の回収 | 題名順位で上位5件に入ったもの |
| --- | --- | --- | --- | --- | --- |
| FANBOX | 5 | 4 | 4 | 4 | 4 |
| DLsite／DLsite Play | 5 | 5 | 3 | 4 | 4 |
| FANZA同人／ブックス | 5 | 5 | 1 | 3 | 2 |

合計15件中、題名中心で8件、補助込みで11件の登録済みHitomi投稿IDが候補集合に含まれた。補助込みのうち10件は、単純な題名類似度で上位5件に入った。公開情報を取得できた14件だけを分母にすると候補回収は11/14。

**これは自動的な同一作品確定率ではない。** 11件中1件は雑誌の途中ページと個別販売作品の対応。FANBOXの抜粋公開と本編、ページ数の異なる版もあり、投稿ID回収と全内容の同一性を区別する。

## 選定と探索条件

- 私有APIのリンク検索で有効エントリを確認。Hitomiと両方のリンクを持つ件数はFANBOX14、DLsite19、FANZA系22（サイト別件数は重複し得る）。その集合からIDのハッシュ順で各5件、同じ個人エントリを重複させず選定。購入済み・評価等での選別はしていない。
- 選定時は保存済みリンクを使うが、探索用には正規URLだけを渡した。既存のFolioタイトル・タグ・作者別名・取得タイトル履歴は使っていない。保存済みHitomiリンクは別ファイルに分離。
- 正規ページから今回新しく公開題名・作者・サークル等を取得。認証情報、支援者限定本文、作品画像は取得しない。FANBOXの1件を匿名取得できないため15件から除外・差し替えはしていない。
- 第1段階はHitomi自身の公開検索インデックスへ公式題名と題名断片を問い合わせ、少数候補のメタデータを読む。取得したJavaScriptは仕様確認用に読むだけで、実行していない。
- 第2段階は公式題名のプラン・版表記・空白・末尾巻話表記を検索語から整理する。これは作品統合の正規化ルールではない。一部の公式作者名からローマ字表記を人が仮に作り、作者索引を検索する補助も実施した。作者別名表が既に存在する、または全自動であるとは扱わない。
- キーワード検索は1語40件以下の集合を主に採用。第1段階の各ケースでメタデータ最大40件、第2段階は作者の最新40件を含め最大60件を上限とした。全索引・作品画像・本文の一括収集はしていない。
- 探索後に初めて答え合わせスクリプトが登録済み投稿IDと照合。題名の簡易スコアはNFKC・大小・空白・記号を整理してSequenceMatcherで順位付けしただけで、作者一致や収録関係の確定を表すスコアではない。
- 未発見・順位不良のケースは探索終了後に保存済みIDのメタデータを読み、原因を確認した。この事後取得を探索成功へ加えておらず、確認した別名や正解題名を検索へ戻していない。
- 一般検索エンジンのsite:hitomi.la検索も4語組試したが、有用な結果は得られなかった。サイト全体が未登録・検索不能という結論にはしない。

## ケース別

Folioリンクは本人のTailscale内でのみ閲覧可能。Hitomi投稿IDは答え合わせ用の識別値であり、画像・本文の確認はしていない。

| ケース／Folio | 正規ページ | 初期回収 | 補助後回収 | 候補数／正解順位 | 登録済み投稿ID | 観察 |
| --- | --- | --- | --- | --- | --- | --- |
| [fanbox-1](https://folio-vps.tail93424f.ts.net/#/work/e345b17a517b4733aa189a3b9bab18df) | [正規リンク](https://lemonteaoicy.fanbox.cc/posts/6911984) | ○ | ○ | 2件／1 | 3262574 | 日付・プラン表記を含む候補から登録済みIDを回収。 |
| [fanbox-2](https://folio-vps.tail93424f.ts.net/#/work/409ec841cd6d4b4a94499b738f83e601) | [正規リンク](https://r18-ay.fanbox.cc/posts/7690364) | ○ | ○ | 24件／2 | 3268020 | 本文題名の断片検索で回収。初期候補24件、題名スコア2位。 |
| [fanbox-3](https://folio-vps.tail93424f.ts.net/#/work/28ebe815e0f748d1a3f4335f165c6b05) | [正規リンク](https://sasanon.fanbox.cc/posts/12375381) | ○ | ○ | 1件／1 | 4098606 | 日付だけの題名から回収。ただし日付一致だけで自動確定はしない。 |
| [fanbox-4](https://folio-vps.tail93424f.ts.net/#/work/f4e299cf57f54b16887cce8fcae8f2a6) | [正規リンク](https://zealark.fanbox.cc/posts/12581383) | ○ | ○ | 4件／1 | 4197492 | 無料公開部分の投稿と本編の関係。登録済みIDを回収したが全内容の同一性は未確認。 |
| [fanbox-5](https://folio-vps.tail93424f.ts.net/#/work/b0cc794e53e24de5888f4841b7e663b1) | [正規リンク](https://sanaan39.fanbox.cc/posts/11184489) | — | — | 0件／圏外 | 3818517 | 正規投稿の公開メタデータを匿名取得できず。ログイン要求・非公開・削除等の区別は未確定。 |
| [dlsite-1](https://folio-vps.tail93424f.ts.net/#/work/8507145b8af24e4eb2ce73e47b642d4a) | [正規リンク](https://www.dlsite.com/maniax-touch/work/=/product_id/RJ01044734.html) | ○ | ○ | 18件／1 | 2560207 | 題名の断片検索で回収。初期候補18件、題名スコア1位。 |
| [dlsite-2](https://folio-vps.tail93424f.ts.net/#/work/29f1e503d68241ddab6f7b4db005b3c9) | [正規リンク](https://play.dlsite.com/work/RJ419353) | ○ | ○ | 5件／1 | 2496508 | DLsite Playの公式商品ページから取得して回収。公式54ページ・候補55ページ。 |
| [dlsite-3](https://folio-vps.tail93424f.ts.net/#/work/c504b96f0fb5487eb560d040d167df61) | [正規リンク](https://www.dlsite.com/books-touch/work/=/product_id/BJ02848556.html) | ○ | ○ | 1件／1 | 4016509 | 題名から回収。公式231ページ・候補226ページで内容差の確認は別途必要。 |
| [dlsite-4](https://folio-vps.tail93424f.ts.net/#/work/c102cf75c2834b4b95222627789df553) | [正規リンク](https://www.dlsite.com/maniax-touch/work/=/product_id/RJ01732685.html) | — | — | 1件／圏外 | 4260489 | 公式は人名の一文字を伏せ字にし、差分枚数の接頭辞もある。探索失敗。正解確認後の題名を検索へ戻していない。 |
| [dlsite-5](https://folio-vps.tail93424f.ts.net/#/work/1cdc715e049d4c0d9817764f8c94bebc) | [正規リンク](https://www.dlsite.com/maniax-touch/work/=/product_id/RJ01633387.html) | — | ○ | 19件／1 | 2466231 | 末尾の時限目を検索語だけから外してシリーズ名を検索し回収。別話を一律同一扱いにする仕様ではない。 |
| [fanza-1](https://folio-vps.tail93424f.ts.net/#/work/4ebd8e8e24464d319c1ef2439302f80f) | [正規リンク](https://www.dmm.co.jp/dc/doujin/-/detail/=/cid=d_398061/) | ○ | ○ | 5件／1 | 2945710 | 題名検索で回収。 |
| [fanza-2](https://folio-vps.tail93424f.ts.net/#/work/fe671020cec84a798b4486c79fb8459e) | [正規リンク](https://book.dmm.co.jp/product/6284941/b079akroe01838/) | — | ○ | 23件／23 | 4089047 | 作者zuugaの候補23件に登録済みIDを回収したが題名順位23位。Hitomiは484ページの雑誌で登録URLは282ページ目、正規販売は26ページの個別作品。作品全体が同じという成功には扱わない。 |
| [fanza-3](https://folio-vps.tail93424f.ts.net/#/work/3e9913360704442ba887f33cce2b83c0) | [正規リンク](https://www.dmm.co.jp/dc/doujin/-/detail/=/cid=d_172059/) | — | — | 0件／圏外 | 1556254 | 記号・ハート・区切り線の差で失敗。正解確認では作者表記もoohira sunsetで、漢字からの単純な読み推定には頼れない。 |
| [fanza-4](https://folio-vps.tail93424f.ts.net/#/work/c11861c10847416c87e979aaa59fcb88) | [正規リンク](https://book.dmm.co.jp/product/804701/b915awnmg00829/) | — | ○ | 40件／1 | 3361664 | 正規側の特装版表示と題名の空白・ハート差。作者yanyoの100件から最新40件のメタデータを読み、題名順位1位で回収。 |
| [fanza-5](https://folio-vps.tail93424f.ts.net/#/work/4c138403ae5c4be796dbe62592544d46) | [正規リンク](https://book.dmm.co.jp/product/4110940/dmmmg_3253/) | — | — | 0件／圏外 | 1999729 | 題名が漢字1字で285件。上限を超えたため全件メタデータ走査はせず、仮の作者表記ikuhana niiroも索引なし。正解確認時の表記はikuhana niro。 |

## 判断と次の改善候補

正規情報からHitomi候補を探す経路は成立する。一方、短い題名、伏せ字、記号、翻訳・読みの差、作者別名、抜粋・収録関係で結果が変わる。「候補の提示」には使えても、正規作品と投稿全体を自動統合する根拠には不足する。

改善案は、Unicodeの空白・記号を考慮した検索語生成、既に確認済みの組み合わせからの作者別名候補作成、作者と題名の集合の絞り込み、巻・話・版・収録範囲の別評価。特に「丹」の285件は作者表記が正しければ絞れる余地があるが、今回その改善後の成功率を測ったわけではない。

このサンプルは既に両リンクを持ち、少なくとも対応先が知られている集合である。未掲載作品や未知のURLを含む実利用全体の発見率へ一般化しない。候補に入ること、上位へ来ること、内容が一致することは別の評価指標とする。

アプリへの自動検索機能・リンク追加・作者別名の保存は実装していない。私有ライブラリの作品・リンク・評価・閲覧日時に書き込みを行っていない。正式版で転載リンクを公開しない既存方針も変更していない。

## 再現用資料

Git対象外test-output内：select_reverse_samples.py、reverse-seeds.json、reverse-answers.json、reverse_fetch_official.py、reverse-official.json、reverse_hitomi_search.py、reverse-discovery.json、reverse_supplement.py、reverse-supplement.json、evaluate_reverse.py、reverse-evaluation.json、inspect_reverse_failures.py、reverse-posthoc-inspection.json。

公開検索の仕様確認：[Hitomi検索クライアント](https://ltn.gold-usergeneratedcontent.net/search.js)、[検索補助コード](https://ltn.gold-usergeneratedcontent.net/searchlib.js)。仕様・索引は変更され得る。

使用索引バージョン：`1792306857`。第1段階HTTP取得277回、第2段階146回（正規側取得・事後確認を除く）。静的索引の小さなRange取得を含む回数で、作品数・画像数ではない。
