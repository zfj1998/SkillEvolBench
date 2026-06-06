"""
Scoring rubric for E1-LS1-T2: express-auth-chain-silent-bypass

Rubric:
  Public tests (P1-P4)             15%  proportional
  H1: core bypass                  20%  all_or_nothing
  H2-H6: security tests           25%  proportional
  H7-H8: auxiliary                 10%  proportional
  P1+P2: tokenValidator fix        15%  all_or_nothing
  P3: roleChecker defense          10%  all_or_nothing
  P5: no 200 on rejection           5%  all_or_nothing
"""

import json
import sys
from typing import Dict, List


class Dimension:
    def __init__(self, name, weight, test_ids, scoring='proportional'):
        self.name = name
        self.weight = weight
        self.test_ids = test_ids
        self.scoring = scoring


RUBRIC = [
    Dimension('Public tests (P1-P4)',         15.0, ['TestPublic::test_p1_', 'TestPublic::test_p2_', 'TestPublic::test_p3_', 'TestPublic::test_p4_']),
    Dimension('H1: core bypass',              20.0, ['test_h1_crafted'], 'all_or_nothing'),
    Dimension('H2-H6: security tests',        25.0, ['test_h2_', 'test_h3_', 'test_h4_', 'test_h5_', 'test_h6_']),
    Dimension('H7-H8: auxiliary',             10.0, ['test_h7_', 'test_h8_']),
    Dimension('P1+P2: tokenValidator fix',    15.0, ['TestProcessP1P2'], 'all_or_nothing'),
    Dimension('P3: roleChecker defense',      10.0, ['TestProcessP3'], 'all_or_nothing'),
    Dimension('P5: no 200 on rejection',       5.0, ['TestProcessP5'], 'all_or_nothing'),
]


def _match(results, patterns):
    matched = {}
    for node_id, passed in results.items():
        for pat in patterns:
            if pat.lower() in node_id.lower():
                matched[node_id] = passed
                break
    return matched


def compute_score(results):
    dims = []
    total = 0.0
    for d in RUBRIC:
        m = _match(results, d.test_ids)
        n = len(m)
        p = sum(1 for v in m.values() if v)
        if n == 0:
            ratio, sc = 0.0, 0.0
        elif d.scoring == 'all_or_nothing':
            ratio = 1.0 if p == n else 0.0
            sc = d.weight * ratio
        else:
            ratio = p / n
            sc = d.weight * ratio
        total += sc
        dims.append({'name': d.name, 'weight': d.weight, 'matched': n, 'passed': p, 'scoring': d.scoring, 'ratio': round(ratio, 3), 'score': round(sc, 2)})
    return {'total_score': round(total, 2), 'max_score': 100.0, 'dimensions': dims}


def print_report(report):
    print('=' * 65)
    print(f"  E1-LS1-T2 SCORING — Total: {report['total_score']}/{report['max_score']}")
    print('=' * 65)
    for d in report['dimensions']:
        tag = '✓' if d['ratio'] == 1.0 else ('△' if d['ratio'] > 0 else '✗')
        print(f"  {tag}  {d['name']:<35s}  {d['passed']}/{d['matched']}  ({d['scoring'][:4]})  {d['score']:5.1f} / {d['weight']:.0f}")
    print('-' * 65)
    print(f"  TOTAL: {report['total_score']:.1f} / {report['max_score']:.0f}")


if __name__ == '__main__':
    if len(sys.argv) == 3:
        def _load(p):
            with open(p) as f:
                data = json.load(f)
            return {t['nodeid']: t['outcome'] == 'passed' for t in data.get('tests', [])}
        all_results = {**_load(sys.argv[1]), **_load(sys.argv[2])}
    else:
        print('Usage: python score.py <outcome_report.json> <process_report.json>')
        sys.exit(1)
    report = compute_score(all_results)
    print_report(report)
    with open('score_report.json', 'w') as f:
        json.dump(report, f, indent=2)
