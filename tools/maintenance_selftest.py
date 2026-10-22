"""Checks transcribed manufacturer prices and due-service behavior."""

import unittest

import maintenance
import server


class MaintenanceTest(unittest.TestCase):
    def test_every_published_variant_has_a_complete_timetable(self):
        self.assertEqual(len(maintenance.CATALOGUE), 25)
        for model in maintenance.CATALOGUE:
            with self.subTest(model=model):
                guide = maintenance.timetable("MY", model, 8421)
                self.assertTrue(guide["supported"])
                self.assertTrue(guide["source"].startswith("https://"))
                self.assertTrue(guide["stops"])
                self.assertIsNotNone(guide["next"])
                for stop in guide["stops"]:
                    self.assertLessEqual(stop["required_price"],
                                         stop["with_recommended_price"])

    def test_published_major_prices(self):
        examples = {
            "Jaecoo J5 EV": (40000, 938.7),
            "Jaecoo J7 AWD": (60000, 1690.9),
            "Jaecoo J7 PHEV": (40000, 987.8),
            "Jaecoo J8 AWD": (120000, 2029.2),
            "Omoda C9 AWD": (60000, 1935.2),
            "Omoda C9 PHEV": (40000, 1527.6),
            "iCAUR 03 iWD": (25000, 611.5),
            "iCAUR V23 RWD": (85000, 487.7),
        }
        for model, (km, expected) in examples.items():
            with self.subTest(model=model):
                stops = maintenance.timetable("MY", model, 0)["stops"]
                actual = next(s["required_price"] for s in stops if s["km"] == km)
                self.assertAlmostEqual(actual, expected)

    def test_next_stop_and_unconfirmed_past(self):
        guide = maintenance.timetable("MY", "J5 EV", 25000, [1000, 20000])
        self.assertEqual(guide["next"]["km"], 40000)
        self.assertEqual(guide["km_remaining"], 15000)
        self.assertEqual(guide["past_unconfirmed"], [])
        self.assertEqual(maintenance.timetable("MY", "J5 EV", 25000)[
            "past_unconfirmed"], [1000, 20000])

    def test_variant_and_country_are_explicit(self):
        self.assertFalse(maintenance.timetable("MY", "iCAUR 03", 0)["supported"])
        self.assertFalse(maintenance.timetable("ID", "Jaecoo J5 EV", 0)["supported"])
        self.assertEqual(maintenance.brand_for("iCAUR 03"), "iCAUR")

    def test_nearest_centres_follow_brand_directory(self):
        for model in ("Jaecoo J5 EV", "Chery Omoda E5", "iCAUR 03"):
            with self.subTest(model=model):
                result = server._service_centres("MY", model, 3.139, 101.687)
                self.assertTrue(result["centres"])
                distances = [centre["distance_km"] for centre in result["centres"]]
                self.assertEqual(distances, sorted(distances))
                self.assertFalse(result["verified_for_model"])


if __name__ == "__main__":
    unittest.main()
