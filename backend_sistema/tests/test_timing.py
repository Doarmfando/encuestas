import unittest

from app.automation.timing import (
    DEFAULT_EXECUTION_PROFILE,
    build_runtime_config,
    get_execution_profile_options,
    resolve_execution_profile,
)


class TimingProfilesTest(unittest.TestCase):
    def test_resolve_default_profile(self):
        profile = resolve_execution_profile()
        self.assertEqual(profile["id"], DEFAULT_EXECUTION_PROFILE)
        self.assertGreater(profile["survey_pause_max"], profile["survey_pause_min"])

    def test_resolve_invalid_profile_raises(self):
        with self.assertRaises(ValueError):
            resolve_execution_profile("invalid_profile")

    def test_build_runtime_config_embeds_profile_and_headless(self):
        runtime_config = build_runtime_config("fast", headless=True)
        self.assertEqual(runtime_config["speed_profile"], "fast")
        self.assertTrue(runtime_config["headless"])
        self.assertEqual(runtime_config["timing"]["id"], "fast")

    def test_profile_options_are_ui_friendly(self):
        options = get_execution_profile_options()
        option_ids = {item["id"] for item in options}
        self.assertEqual(option_ids, {"fast", "balanced", "safe", "turbo", "turbo_plus"})
        for option in options:
            self.assertIn("label", option)
            self.assertIn("description", option)


if __name__ == "__main__":
    unittest.main()
