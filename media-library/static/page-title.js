// Keep browser titles stable across UI languages and include actual search text.
export function pageTitle(path, params, workTitle='') {
 const names={'/library':'Library','/metadata':'metadata','/ratings':'Ratings','/imports':'Imports','/saved-searches':'Saved searches','/trash':'Trash','/history':'History','/settings':'Settings','/new':'New work','/source':'Open source','/share':'Share'};
 const query=params.get('q')?.trim();
 let content=names[path]||'Page';
 if(path==='/library'&&query)content=query+' Search';
 else if(path.startsWith('/work/'))content=workTitle||'Work';
 else if(path.startsWith('/edit/'))content=workTitle?workTitle+' Edit':'Edit work';
 else if(path.startsWith('/job/'))content='Import job';
 return content+' - Folio';
}
