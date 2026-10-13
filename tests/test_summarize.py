import unittest
from scripts.summarize import summarize


class SummaryTests(unittest.TestCase):
    def test_valid_samples_median(self):
        sample = lambda x: {'sample_ok':'1', 'phase':'baseline', 'host_rss_mib':str(x), 'host_rssanon_mib':'10', 'balloon_actual_mib':'0', 'guest_available_mib':'700', 'guest_major_faults':'2'}
        result = summarize([sample(100), sample(120), sample(110), {'sample_ok':'0', 'phase':'baseline'}])
        self.assertEqual(result['baseline']['samples'], 3)
        self.assertEqual(result['baseline']['host_rss_mib_median'], 110)

    def test_empty(self):
        self.assertEqual(summarize([]), {})


if __name__ == '__main__':
    unittest.main()
