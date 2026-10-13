export function searchHelpHTML(config,lang,esc){
 const ja=lang==='ja',s=(en,jp)=>ja?jp:en;
 const firstRating=(config.dimensions||[])[0];
 const ratingExample=firstRating?`rating${firstRating.number}:>=${Math.min(4,firstRating.maximum)}`:'pages:>=20';
 const code=value=>`<code>${esc(value)}</code>`;
 const rows=items=>`<table class="search-help-table"><tbody>${items.map(([example,text])=>`<tr><th scope="row">${code(example)}</th><td>${esc(text)}</td></tr>`).join('')}</tbody></table>`;
 const section=(heading,html)=>`<section><h3>${esc(heading)}</h3>${html}</section>`;
 let html=`<div class="search-help-header"><h2>${s('Search help','検索ヘルプ')}</h2><button type="button" id="search-help-close" class="iconbtn" aria-label="${s('Close','閉じる')}" title="${s('Close','閉じる')}">×</button></div><p>${s('Combine words and fields to find works in your library. Searches ignore letter case. Trash entries are excluded.','単語や項目を組み合わせて作品を検索できます。大文字・小文字は区別しません。ゴミ箱の作品は対象外です。')}</p>`;
 html+=section(s('Words and operators','単語と演算子'),rows([
  ['sketch',s('Partial match in title, category, language, authors, circles, tags, series and characters, including aliases. Notes and URLs are not included.','タイトル・カテゴリ・言語・作者・サークル・タグ・シリーズ・キャラクターと別名の部分一致。レビューやURLは含みません。')],
  ['author:alice tag:original',s('A space means AND: both conditions must match.','空白はAND：両方の条件に一致。')],
  ['author:alice/author:bob',s('A slash means OR: either condition may match. Do not put spaces around the slash.','/ はOR：どちらかに一致。/ の前後には空白を入れません。')],
  ['-tag:original',s('A leading minus excludes a condition.','先頭の - は条件の除外（NOT）。')],
  ['author:"Alice Smith"',s('Double quotes preserve spaces, slashes and punctuation inside a value.','値を半角の二重引用符で囲むと、空白・/・記号をそのまま検索できます。')],
  [`author:alice/author:bob ${ratingExample}`,s('OR is grouped first: (Alice OR Bob) AND the last condition. Parentheses themselves cannot be entered.','ORが先にまとまります：(Alice または Bob) かつ最後の条件。検索式に括弧は入力できません。')]
 ]));
 html+=section(s('Available fields','検索できる項目'),rows([
  ['title:"night sketch"',s('Partial match in the displayed work title.','表示している作品タイトルの部分一致。')],['review:"read again"',s('Partial match in your review / notes only.','レビュー・メモの部分一致。')],
  ['author:alice',s('Exact author name or alias.','作者名・別名の完全一致。')],['circle:"circle name"',s('Exact circle name or alias. group: is equivalent.','サークル名・別名の完全一致。group: も同じ意味。')],
  ['tag:original',s('Exact tag name or alias, across every attribute.','タグ名・別名の完全一致。属性を問わず検索。')],['female:original',s('Exact tag, restricted to Female. male: restricts to Male.','女性属性のタグ。male: は男性属性に限定。')],
  ['none:original',s('Exact tag without an attribute. neutral: is an equivalent legacy spelling.','属性なしのタグ。従来の neutral: も利用可能。')],['series:"Blue Archive"',s('Exact series name or alias.','シリーズ名・別名の完全一致。')],['character:alice',s('Exact character name or alias.','キャラクター名・別名の完全一致。')],
  ['category:doujinshi',s('Exact category. Japanese category names also work.','カテゴリの完全一致。日本語のカテゴリ名も利用可能。')],['language:japanese',s('Exact stored language value; use quotes for values containing spaces.','保存している言語名の完全一致。空白を含む場合は引用符で囲みます。')],
  ['pages:>=30',s('Page comparisons: =, >, <, >=, <=; pages:30 means exactly 30. Missing page counts do not match numeric comparisons.','ページ数：=、>、<、>=、<=。pages:30 は30ページ。未設定は数値条件に一致しません。')]
 ]));
 html+=section(s('Your rating dimensions','現在の評価軸'),`<p>${firstRating?s('Use the fixed rating number and an integer comparison.','固定された評価番号と整数の比較を使います。'):s('Add a rating dimension on the Ratings page to search by rating.','評価ページで評価軸を追加すると、評価で検索できます。')}</p>`+rows((config.dimensions||[]).map(d=>[`rating${d.number}:>=${Math.min(4,d.maximum)}`,`${d.number}. ${d.name} · 1–${d.maximum}`]))+(firstRating?rows([[`-rating${firstRating.number}:>=1`,s('Unrated for this dimension. Use an existing dimension number.','この軸の未評価。存在する評価番号を指定します。')]]):''));
 html+=section(s('Five independent marks','5個のマーク'),rows((config.marks||[]).map(d=>[`mark:${d.number}`,`${d.off} / ${d.on} · ${d.label||(d.number===1?s('Purchased','購入済み'):s('Mark ','マーク ')+d.number)}`]))+rows([
  ['mark:124',s('Marks 1, 2 and 4 must all be on; 3 and 5 can be either. mark:421 is equivalent.','1・2・4がすべてオン。3・5はどちらでも可。mark:421 も同じ。')],
  ['mark:=124',s('Only 1, 2 and 4 are on; 3 and 5 must be off.','1・2・4だけがオン。3・5はオフ。')],['mark:1/mark:4',s('Mark 1 OR mark 4 is on.','1または4がオン。')],['-mark:2',s('Mark 2 is off.','2がオフ。')],['mark:none',s('All five marks are off.','すべてオフ。')],['mark:any',s('At least one mark is on.','少なくとも1つオン。')],['mark1:yes',s('Single-mark spelling; yes/no and true/false are supported for mark1 through mark5.','1個を指定する別表記。mark1〜mark5 で yes/no・true/false が利用可能。')],['bought:yes',s('Legacy spelling for mark 1 on. bought:no means mark 1 off.','従来の購入済み検索。マーク1がオン。bought:no は1がオフ。')],['-mark:124',s('Excludes works where ALL 1, 2 and 4 are on; this does not mean all three are off.','1・2・4がすべてオンの作品を除外。「3個ともオフ」という意味ではありません。')]
 ]));
 html+=section(s('Combined examples','組み合わせの例'),rows([
  ['female:original mark:14',s('Female original tag, with marks 1 and 4 on.','女性属性の original タグ、かつマーク1・4がオン。')],
  ['author:"Alice Smith" pages:>=20 -mark:2',s('Alice Smith, at least 20 pages, mark 2 off.','作者 Alice Smith、20ページ以上、マーク2がオフ。')],
  ['mark:=124 language:japanese',s('Exactly marks 1, 2 and 4, in Japanese.','マーク1・2・4だけオン、言語が japanese。')]
 ]));
 html+=section(s('Category names and quoting','カテゴリ名・引用符'),rows(Object.entries(config.categories||{}).map(([key,value])=>[`category:${JSON.stringify(key)}`,value]))+`<p>${s('Inside quoted values, escape a literal quote as \\" and a backslash as \\\\. Use integer ratings within the dimension’s range. Unknown fields and incomplete expressions show an error.','引用符の中の二重引用符は \\"、バックスラッシュは \\\\ と書きます。評価はその軸の範囲内の整数を指定します。不明な項目や途中で終わった検索式はエラーになります。')}</p>`);
 return html;
}
