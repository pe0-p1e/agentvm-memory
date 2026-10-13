import unittest
from scripts.validate_run import validate

class ValidationTests(unittest.TestCase):
    def test_missing_phases_invalid(self):
        report = validate('baseline', [], '')
        self.assertFalse(report['valid'])
        self.assertIn('allocated', report['missing_phases'])
    def test_all_phases_valid(self):
        phases = ['baseline', 'allocated', 'freed', 'control_after_free']
        rows = [{'phase': p, 'sample_ok': '1'} for p in phases for _ in range(2)]
        markers = '\n'.join('FCMEM_STAGE:' + m for m in ['baseline','allocated','freed','agent_reuse','retouch_start','retouched','done'])
        report = validate('baseline', rows, markers)
        self.assertTrue(report['valid'])

if __name__ == '__main__':
    unittest.main()
