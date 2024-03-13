import unittest
from unittest.mock import MagicMock
from event_handler import EventHandler


class TestEventHandler(unittest.TestCase):

    def setUp(self):
        self.handler = EventHandler(version="1.0")

    def test_get_region_from_string(self):
        region = self.handler.get_region_from_string("us-east-1-config.yaml")
        self.assertEqual(region, "us-east-1")

        with self.assertRaises(EventHandler.FormatError):
            self.handler.get_region_from_string("invalid-filename.yaml")

    def test_validate_file_name(self):
        valid_filename = "us-east-1-config.yaml"
        invalid_filename = "invalid-filename.yaml"

        self.assertTrue(self.handler.validate_file_name(valid_filename))
        self.assertFalse(self.handler.validate_file_name(invalid_filename))

    # Add more test methods for other functions in EventHandler


if __name__ == "__main__":
    unittest.main()
