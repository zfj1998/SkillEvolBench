"""
Scoring rubric for E1-LS1-T3: ts-promise-allSettled-ignored-rejection

  Public tests (P1-P3)             15%  proportional
  H1: core fix                     25%  all_or_nothing
  H2-H5: boundary/isolation        20%  proportional
  H6-H7: auxiliary                 10%  proportional
  P1+P2: rejected handling         20%  all_or_nothing
  P3: error reporting              10%  all_or_nothing
"""
import json, sys

class Dim:
    def __init__(s, name, weight, ids, scoring='proportional'):
        s.name, s.weight, s.ids, s.scoring = name, weight, ids, scoring

RUBRIC = [
    Dim('Public tests (P1-P3)',        15.0, ['TestPublic::test_p1_', 'TestPublic::test_p2_', 'TestPublic::test_p3_']),
    Dim('H1: core fix',               25.0, ['test_h1_failed_sources'], 'all_or_nothing'),
    Dim('H2-H5: boundary/isolation',   20.0, ['test_h2_', 'test_h3_', 'test_h4_', 'test_h5_']),
    Dim('H6-H7: auxiliary',            10.0, ['test_h6_', 'test_h7_']),
    Dim('P1+P2: rejected handling',    20.0, ['TestProcessP1P2'], 'all_or_nothing'),
    Dim('P3: error reporting',         10.0, ['TestProcessP3'], 'all_or_nothing'),
]

def compute_score(results):
    dims, total = [], 0.0
    for d in RUBRIC:
        m = {k: v for k, v in results.items() if any(p.lower() in k.lower() for p in d.ids)}
        n, p = len(m), sum(1 for v in m.values() if v)
        if n == 0: ratio, sc = 0, 0
        elif d.scoring == 'all_or_nothing': ratio = 1.0 if p == n else 0.0; sc = d.weight * ratio
        else: ratio = p / n; sc = d.weight * ratio
        total += sc
        dims.append({'name': d.name, 'weight': d.weight, 'passed': p, 'of': n, 'score': round(sc, 2)})
    return {'total': round(total, 2), 'dims': dims}

def print_report(r):
    print(f"  TOTAL: {r['total']}/100")
    for d in r['dims']:
        t = '✓' if d['score'] == d['weight'] else ('△' if d['score'] > 0 else '✗')
        print(f"  {t} {d['name']:<35s} {d['passed']}/{d['of']}  {d['score']:5.1f}/{d['weight']:.0f}")

if __name__ == '__main__':
    if len(sys.argv) == 3:
        def _l(p):
            with open(p) as f: data = json.load(f)
            return {t['nodeid']: t['outcome'] == 'passed' for t in data.get('tests', [])}
        print_report(compute_score({**_l(sys.argv[1]), **_l(sys.argv[2])}))
