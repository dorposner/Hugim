import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os

# Add parent directory to path to import googlesheets
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import googlesheets

class TestAnalytics(unittest.TestCase):

    @patch('googlesheets.get_all_camp_names')
    @patch('googlesheets.read_config')
    def test_get_all_camps_analytics(self, mock_read_config, mock_get_names):
        # Mock camp names
        mock_get_names.return_value = ['Camp A', 'Camp B', 'Camp C']

        # Mock read_config behavior
        def side_effect(camp_name, spreadsheet_id=None):
            if camp_name == 'Camp A':
                # Full data
                return {
                    'prefs_df': pd.DataFrame({'a': [1, 2, 3]}),
                    'hugim_df': pd.DataFrame({'b': [1, 2]}),
                    'periods': ['p1', 'p2'],
                    'assignments_df': pd.DataFrame({
                        'p1_Assigned': ['Val', None, ''],
                        'p2_Assigned': ['Val', 'Val', 'nan'],
                        'Other': [1, 2, 3]
                    })
                }
            elif camp_name == 'Camp B':
                # Missing assignments
                return {
                    'prefs_df': pd.DataFrame({'a': [1]}),
                    'hugim_df': pd.DataFrame({'b': [1]}),
                    'periods': ['p1']
                }
            elif camp_name == 'Camp C':
                # Error (None returned)
                return None
            return {}

        mock_read_config.side_effect = side_effect

        # Run function
        df = googlesheets.get_all_camps_analytics()

        # Verify DataFrame structure
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 3)
        self.assertListEqual(list(df.columns), ['Camp Name', 'Campers', 'Activities', 'Periods', 'Unassigned Slots', 'Status'])

        # Verify Camp A
        row_a = df[df['Camp Name'] == 'Camp A'].iloc[0]
        self.assertEqual(row_a['Campers'], 3)
        self.assertEqual(row_a['Activities'], 2)
        self.assertEqual(row_a['Periods'], 2)
        # Unassigned:
        # p1_Assigned: None (1), '' (1) -> 2
        # p2_Assigned: 'nan' (1) -> 1
        # Total: 3
        self.assertEqual(row_a['Unassigned Slots'], 3)
        self.assertEqual(row_a['Status'], 'OK')

        # Verify Camp B
        row_b = df[df['Camp Name'] == 'Camp B'].iloc[0]
        self.assertEqual(row_b['Campers'], 1)
        self.assertEqual(row_b['Activities'], 1)
        self.assertEqual(row_b['Periods'], 1)
        self.assertEqual(row_b['Unassigned Slots'], 0) # No assignments df
        self.assertEqual(row_b['Status'], 'OK')

        # Verify Camp C
        row_c = df[df['Camp Name'] == 'Camp C'].iloc[0]
        self.assertEqual(row_c['Status'], 'Error (Read Failed)')

if __name__ == '__main__':
    unittest.main()
