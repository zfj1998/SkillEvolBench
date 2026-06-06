"""Scoring rubric for E1-LS1-T6."""
import json, sys

class Dim:
    def __init__(s, n, w, ids, m='proportional'):
        s.name, s.weight, s.ids, s.mode = n, w, ids, m

RUBRIC = [
    Dim('Public tests', 15.0, ['TestPublic']),
    Dim('H1 root-cause', 20.0, ['test_h1_'], 'all_or_nothing'),
    Dim('H2-H3 error handling', 15.0, ['test_h2_', 'test_h3_']),
    Dim('H4-H6 auxiliary', 10.0, ['test_h4_', 'test_h5_', 'test_h6_']),
    Dim('P1: 4 files modified', 15.0, ['TestProcessP1'], 'all_or_nothing'),
    Dim('P2: URL encoding', 10.0, ['TestProcessP2'], 'all_or_nothing'),
    Dim('P3-P5: error refactor', 15.0, ['TestProcessP3', 'TestProcessP4', 'TestProcessP5']),
]

def compute_score(results):
    dims, total = [], 0.0
    for d in RUBRIC:
        m = {k: v for k, v in results.items() if any(p.lower() in k.lower() for p in d.ids)}
        n, p = len(m), sum(1 for v in m.values() if v)
        if n == 0:
            r, sc = 0, 0
        elif d.mode == 'all_or_nothing':
            r = 1.0 if p == n else 0.0
            sc = d.weight * r
        else:
            r = p / n
            sc = d.weight * r
        total += sc
        dims.append({'name': d.name, 'w': d.weight, 'p': p, 'n': n, 'sc': round(sc, 1)})
    return round(total, 1), dims

if __name__ == '__main__':
    def _load(path):
        with open(path) as f:
            data = json.load(f)
        return {t['nodeid']: t['outcome'] == 'passed' for t in data.get('tests', [])}
    total, dims = compute_score({**_load(sys.argv[1]), **_load(sys.argv[2])})
    print(f'TOTAL: {total}/100')
    for d in dims:
        print(f"  {'✓' if d['sc']==d['w'] else '△' if d['sc']>0 else '✗'} {d['name']:<25s} {d['p']}/{d['n']}  {d['sc']}/{d['w']}")
