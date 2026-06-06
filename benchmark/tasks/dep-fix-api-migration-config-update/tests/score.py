"""Scoring rubric for E1-LS2-T6."""
import json, sys
class Dim:
    def __init__(self, name, weight, ids, mode='proportional'):
        self.name, self.weight, self.ids, self.mode = name, weight, ids, mode
RUBRIC = [
    Dim('Public tests', 15.0, ['TestPublic']),
    Dim('H1 Config', 10.0, ['test_h1_'], 'all_or_nothing'),
    Dim('H2-H4 functionality', 25.0, ['test_h2_', 'test_h3_', 'test_h4_']),
    Dim('H3 commit persistence', 15.0, ['test_h3_'], 'all_or_nothing'),
    Dim('H5-H6 auxiliary', 10.0, ['test_h5_', 'test_h6_']),
    Dim('P1-P5 process', 25.0, ['test_process_']),
]
def _collect(report):
    passed, failed = set(), set()
    for test in report.get('tests', []):
        nodeid, outcome = test.get('nodeid',''), test.get('outcome')
        if outcome == 'passed': passed.add(nodeid)
        elif outcome == 'failed': failed.add(nodeid)
    return passed, failed
def _match(nodeid, patterns): return any(p in nodeid for p in patterns)
def _score_dim(dim, passed, failed):
    matched = [t for t in passed | failed if _match(t, dim.ids)]
    if not matched: return dim.weight
    pass_count = sum(1 for t in matched if t in passed)
    return dim.weight if dim.mode == 'all_or_nothing' and pass_count == len(matched) else (0.0 if dim.mode == 'all_or_nothing' else dim.weight * (pass_count/len(matched)))
def main():
    report = json.load(sys.stdin); passed, failed = _collect(report); total=0.0; details=[]
    for dim in RUBRIC:
        s = _score_dim(dim, passed, failed); total += s; details.append({'name': dim.name, 'score': round(s,2), 'weight': dim.weight})
    print(json.dumps({'score': round(total,2), 'details': details}, indent=2))
if __name__ == '__main__': main()
