import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_profile_badges import (
    BadgeConfigError,
    END,
    START,
    load_config,
    render,
    replace_owned_block,
    safe_aggregate_value,
)


class ProfileBadgeTests(unittest.TestCase):
    def test_render_is_deterministic_and_keeps_labels_repository_owned(self):
        config = load_config(Path("profile-badges.json"))
        first = render(config, {"active_agents": "3", "unknown_server_key": "nope"})
        second = render(config, {"active_agents": "3", "unknown_server_key": "changed"})
        self.assertEqual(first, second)
        self.assertIn("active%20agents-3", first)
        self.assertIn("logoColor=FFFFFF", first)
        self.assertIn("logoColor=000000", first)
        self.assertNotIn("unknown_server_key", first)

    def test_replacement_changes_only_the_owned_marker_block(self):
        original = f"before\n{START}\nold\n{END}\nafter\n"
        block = f"{START}\nnew\n{END}"
        self.assertEqual(replace_owned_block(original, block), f"before\n{block}\nafter\n")

    def test_missing_or_duplicate_markers_fail_closed(self):
        with self.assertRaises(BadgeConfigError):
            replace_owned_block("no markers", "replacement")
        with self.assertRaises(BadgeConfigError):
            replace_owned_block(f"{START}{START}{END}", "replacement")
        with self.assertRaises(BadgeConfigError):
            replace_owned_block(f"{END}{START}", "replacement")

    def test_aggregate_values_are_bounded_and_inert(self):
        self.assertEqual(safe_aggregate_value(12), "12")
        self.assertEqual(safe_aggregate_value(False), "no")
        self.assertIsNone(safe_aggregate_value("![injection](https://example.com)"))
        self.assertIsNone(safe_aggregate_value({"html": "<script>"}))

    def test_invalid_dynamic_key_is_rejected(self):
        config = json.loads(Path("profile-badges.json").read_text())
        config["roost"]["aggregates"][0]["key"] = "../../secret"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config))
            with self.assertRaises(BadgeConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
