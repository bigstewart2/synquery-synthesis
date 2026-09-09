"""Export the canonical demo inputs. Run --check in QA; optionally copy to a portfolio."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
from _harbor import BRIEF, DEMO_ID, SAMPLES


def assets():
    brief = ('FICTIONAL DEMO PROJECT — Not a real company or investment recommendation.\n\n'
             + BRIEF['project'] + '\n\nDecision\n' + BRIEF['decision']
             + '\n\nResearch questions\n'
             + '\n'.join(f'{i}. {q}' for i, q in enumerate(BRIEF['questions'], 1))
             + '\n\nSources\nDavid Okafor — Operations perspective\nMaria Castellanos — Sales perspective\n'
             + '\nThe brief guides extraction; it is context, not evidence.\n')
    return {'harbor-project-brief.txt': brief, **{s['filename']: s['text'] for s in SAMPLES.values()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--portfolio', type=Path)
    args = parser.parse_args()
    outputs = {ROOT / 'public/samples' / name: text for name, text in assets().items()}
    if args.portfolio:
        outputs.update({args.portfolio / 'public/samples' / name: text for name, text in assets().items()})
    page = ROOT / 'public/index.html'
    html = page.read_text()
    a, b = html.index('// BEGIN HARBOR MANIFEST'), html.index('// END HARBOR MANIFEST')
    manifest = {'id': DEMO_ID, 'brief': BRIEF,
                'samples': [{k: v for k, v in s.items() if k != 'text'} for s in SAMPLES.values()]}
    outputs[page] = html[:a] + '// BEGIN HARBOR MANIFEST\nconst HARBOR = ' + json.dumps(manifest, ensure_ascii=False) + ';\n' + html[b:]
    for path, text in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f'Demo asset is missing or stale: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print(f'{"Checked" if args.check else "Exported"} {len(outputs)} Harbor assets; source bytes and download line numbers match.')


if __name__ == '__main__':
    main()
