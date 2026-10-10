"""Focused regressions for the two experimental reconstruction layouts."""

import copy
import json
import unittest
from pathlib import Path

from results.table_benchmark.reconstruct_structure import (
    detect_full_width_sections,
    reconstruct,
    reconstructed_markdown,
)


HERE = Path(__file__).resolve().parent


def source(table_id):
    return json.loads((HERE / "json" / f"{table_id}.json").read_text(encoding="utf-8"))


class ReconstructionTest(unittest.TestCase):
    def test_cw_multilevel_headers_colspan_and_grouped_ewt(self):
        raw = source("cyberrow_cw_p10_performance")
        original = copy.deepcopy(raw)
        result = reconstruct(raw)
        self.assertEqual(raw, original)
        self.assertEqual(result["raw_extraction"], original)
        self.assertEqual(len(result["records"]), 30)
        self.assertEqual([s["row"] for s in result["full_width_sections"]], [2, 9, 16, 23, 30])
        self.assertTrue(all(s["colspan"] == 8 and s["evidence"]["span_ratio"] >= 0.95
                            for s in result["full_width_sections"]))
        headers = result["column_headers"]
        self.assertEqual(
            [(h["parent_header_raw"], h["unit"]) for h in headers[2:]],
            [
                ("Net Total Capacity", "Btu/h"), ("Net Total Capacity", "kW"),
                ("Net Sensible Capacity", "Btu/h"), ("Net Sensible Capacity", "kW"),
                ("Flow Rate", "GPM"), ("Total System\nPressure Drop", "ftH2O"),
            ],
        )
        self.assertEqual(headers[7]["unit_raw"], "ftH 0\n2")
        self.assertEqual(headers[7]["association_status"], "needs_review")
        first, second, next_section = result["records"][0], result["records"][1], result["records"][6]
        self.assertEqual(first["equipment"], {"model": "CRS-090-C", "cabinet": "12 in Cabinet"})
        self.assertEqual((first["EWT"]["value"], first["delta_T"]["value"]), (40.0, 10.0))
        self.assertEqual(first["operating_conditions"]["dry_bulb_F"], 100.0)
        self.assertEqual(first["measurements"][0]["value"], 129617)
        self.assertEqual(first["measurements"][0]["source_cell"], raw["cells"][3][2])
        self.assertEqual((second["EWT"]["source_row"], second["EWT"]["forward_filled"]), (3, True))
        self.assertEqual(next_section["operating_conditions"]["dry_bulb_F"], 95.0)
        self.assertFalse(next_section["EWT"]["forward_filled"])
        self.assertIn("100°FDB / 69.2°FWB Entering Air Temperature", reconstructed_markdown(result))

    def test_sparse_row_is_not_a_section_and_ewt_does_not_cross_sections(self):
        raw = source("cyberrow_cw_p10_performance")
        altered = copy.deepcopy(raw)
        for column in range(1, altered["column_count"]):
            altered["raw_grid"][3][column] = None
            altered["cells"][3][column]["text"] = None
            altered["cells"][3][column]["bbox"] = None
        self.assertNotIn(3, [s["row"] for s in detect_full_width_sections(altered)])

        altered = copy.deepcopy(raw)
        altered["raw_grid"][10][0] = None
        altered["cells"][10][0]["text"] = None
        result = reconstruct(altered)
        self.assertIsNone(result["records"][6]["EWT"])
        self.assertIn("ewt_missing_after_section", {f["code"] for f in result["review_flags"]})

    def test_dx_model_column_layout_and_raw_numeric_anomalies(self):
        raw = source("cyberrow_dx_p12_performance")
        result = reconstruct(raw)
        self.assertEqual(len(result["records"]), 30)
        self.assertEqual(len(result["full_width_sections"]), 6)
        self.assertEqual(result["full_width_sections"][0]["kind"], "measurement_scope")
        first = result["records"][0]
        self.assertEqual(first["equipment"]["model"], "CRS-042-AR")
        self.assertIsNone(first["EWT"])
        self.assertIsNone(first["delta_T"])
        self.assertEqual(
            [(m["name"], m["unit"], m["raw_value"]) for m in first["measurements"]],
            [
                ("Net DX Cooling Capacity - Total", "MBH", "52.0"),
                ("Net DX Cooling Capacity - Sensible", "MBH", "52.0"),
                ("Net DX Cooling Capacity - Total", "kW", "15.1"),
                ("Net DX Cooling Capacity - Sensible", "kW", "15.1"),
            ],
        )
        anomalous = next(record for record in result["records"]
                         if record["operating_conditions"]["dry_bulb_F"] == 85.0
                         and record["equipment"]["model"] == "CRS-042-AR")
        self.assertEqual(anomalous["measurements"][0]["raw_value"], "44,0")
        self.assertIsNone(anomalous["measurements"][0]["value"])
        self.assertIn("numeric_value_unparsed", {f["code"] for f in result["review_flags"]})
        self.assertEqual(anomalous["measurements"][0]["source_cell"], raw["cells"][18][2])


if __name__ == "__main__":
    unittest.main()
