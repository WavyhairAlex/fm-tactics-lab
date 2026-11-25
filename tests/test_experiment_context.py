import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from desktop_experiment_context import comparison_context, numbered_name, old_tactics, tactic_description


class ExperimentContextTests(unittest.TestCase):
    def setUp(self):
        self.scenario = {'teams': [{'name': 'Own', 'tactic_name': 'Tactic', 'mentality': 4},
                                   {'name': 'Opponent', 'mentality': 4}]}
        self.engine = {'actual_dll_sha256': 'dll', 'resource_fingerprint': 'resource'}

    def test_comparison_allows_tactic_changes_and_detects_different_opponent_and_seed(self):
        previous = comparison_context(self.scenario, self.engine, [4, 5])
        changed = copy.deepcopy(self.scenario)
        changed['teams'][0]['mentality'] = 5
        current = comparison_context(changed, self.engine, [6, 7])
        self.assertEqual(previous['settings'], current['settings'])
        self.assertNotEqual(previous['sample'], current['sample'])
        self.assertNotEqual(tactic_description(self.scenario)['strategy'], tactic_description(changed)['strategy'])
        changed['teams'][1]['mentality'] = 5
        self.assertNotEqual(previous['settings'], comparison_context(changed, self.engine, [4, 5])['settings'])

    def test_save_comparison_uses_opponent_set_and_seeds_of_the_reported_round(self):
        rounds = [{'seeds': [1, 2]}, {'seeds': [3, 4]}]
        first = comparison_context(self.scenario, self.engine, [1, 2, 3, 4],
                                   save='source', opponents=['a', 'b'], rounds=rounds)
        second = comparison_context(self.scenario, self.engine, [7, 8, 3, 4],
                                    save='source', opponents=['b', 'a'],
                                    rounds=[{'seeds': [7, 8]}, rounds[-1]])
        self.assertEqual(first, second)

    def test_auto_name_reserves_number_after_manual_rename(self):
        first = numbered_name('Tactic', [])
        first['name'] = 'My first test'
        next_name = numbered_name('Tactic', [first, {'name': 'Tactic #02'}])
        self.assertEqual(next_name['name'], 'Tactic #03')

    def test_old_away_fixture_displays_the_tested_tactic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'A_0_A.json').write_text(json.dumps(self.scenario), encoding='utf8')
            result = old_tactics({'_dir': root, 'schedule': {'A_0_A': {'group': 'A', 'tested_side': 1}}})
            self.assertEqual(result['A']['team'], 'Opponent')
            self.assertIsNone(result['A']['name'])
