"""Offline conversion only. No login, browser or network operations."""
import argparse,json,sys
from pathlib import Path
import dlsite_purchases as purchases

def main():
    parser=argparse.ArgumentParser(description='Convert an already supplied DLsite Play inventory to Folio bookmark HTML. This does not collect purchases or log in.')
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--report',type=Path,help='Optional private report with product IDs/titles requiring review')
    args=parser.parse_args()
    try:
        with args.input.open('rb') as source:raw=source.read(purchases.MAX_BYTES+1)
        if len(raw)>purchases.MAX_BYTES:raise purchases.InventoryError('Purchase inventory file exceeds 12 MB')
        bundle=json.loads(raw.decode('utf-8-sig'));result=purchases.normalize(bundle)
        print(json.dumps({'counts':result['counts'],'complete':result['complete'],'warnings':result['warnings']},ensure_ascii=True))
        destinations=[args.output]+([args.report] if args.report else [])
        if len({p.resolve() for p in destinations})!=len(destinations) or any(p.resolve()==args.input.resolve() or p.exists() for p in destinations):
            raise purchases.InventoryError('Choose new, separate output files; existing files are never overwritten')
        # A report can be produced for partial data, but importing partial lists is blocked.
        if args.report:
            with args.report.open('x',encoding='utf-8') as report:json.dump(result,report,ensure_ascii=False,indent=2)
        text=purchases.bookmarks(result)
        with args.output.open('x',encoding='utf-8',newline='\n') as output:output.write(text)
        print('Bookmark HTML exported. Review it in Folio Imports before starting a job.')
        return 0
    except (OSError,UnicodeError,ValueError) as error:
        print(str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
