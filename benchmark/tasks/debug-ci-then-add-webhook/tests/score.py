"""Scoring rubric for E1-LS1-T4."""
import json, sys

class Dim:
    def __init__(s, n, w, ids, m='proportional'):
        s.name, s.weight, s.ids, s.mode = n, w, ids, m

RUBRIC = [
    Dim('Bug fixes (public)',  20.0, ['TestPublicBugFixes']),
    Dim('Webhook H1-H5',      35.0, ['test_h1_', 'test_h2_', 'test_h3_', 'test_h4_', 'test_h5_']),
    Dim('P1: all 3 bugs',     15.0, ['TestProcessP1'], 'all_or_nothing'),
    Dim('P2-P4: fix quality',  15.0, ['TestProcessP2', 'TestProcessP3', 'TestProcessP4']),
    Dim('P5: HMAC',           15.0, ['TestProcessP5'], 'all_or_nothing'),
]

def compute_score(results):
    dims, total = [], 0.0
    for d in RUBRIC:
        m = {k: v for k, v in results.items() if any(p.lower() in k.lower() for p in d.ids)}
        n, p = len(m), sum(1 for v in m.values() if v)
        if n == 0: r, sc = 0, 0
        elif d.mode == 'all_or_nothing': r = 1.0 if p == n else 0.0; sc = d.weight * r
        else: r = p / n; sc = d.weight * r
        total += sc; dims.append({'name': d.name, 'w': d.weight, 'p': p, 'n': n, 'sc': round(sc, 1)})
    return round(total, 1), dims

if __name__ == '__main__':
    if len(sys.argv) != 3: print('Usage: score.py out.json proc.json'); sys.exit(1)
    def _l(p):
        with open(p) as f: d = json.load(f)
        return {t['nodeid']: t['outcome'] == 'passed' for t in d.get('tests', [])}
    t, dims = compute_score({**_l(sys.argv[1]), **_l(sys.argv[2])})
    print(f'TOTAL: {t}/100')
    for d in dims: print(f"  {'✓' if d['sc']==d['w'] else '△' if d['sc']>0 else '✗'} {d['name']:<25s} {d['p']}/{d['n']}  {d['sc']}/{d['w']}")
