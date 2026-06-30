"""
test_parser.py
--------------
Unit tests for parser.py.   Run with:  python test_parser.py
(No pytest required — uses the stdlib unittest module.)
"""

import unittest
from parser import parse_message

class TestAmountParsing(unittest.TestCase):

    def _amt(self, msg):
        r = parse_message(msg)
        self.assertIsNotNone(r, f"parse_message returned None for: {msg!r}")
        return r['amount']

    def test_bare_integer(self):
        self.assertEqual(self._amt("spent 500 on ola"), 500)

    def test_with_commas(self):
        self.assertEqual(self._amt("rs 1,250 electricity"), 1250)

    def test_k_suffix(self):
        self.assertEqual(self._amt("1.5k myntra"), 1500)

    def test_l_suffix(self):
        self.assertEqual(self._amt("2l stocks investment"), 200_000)

    def test_rupee_prefix(self):
        self.assertEqual(self._amt("₹250 chai"), 250)

    def test_rs_prefix(self):
        self.assertEqual(self._amt("rs500 petrol"), 500)

    def test_rs_suffix(self):
        self.assertEqual(self._amt("500rs petrol"), 500)

    def test_inr_prefix(self):
        self.assertEqual(self._amt("inr 800 medicine"), 800)

    def test_large_with_commas(self):
        self.assertEqual(self._amt("got salary 75,000"), 75_000)


class TestCategoryGuessing(unittest.TestCase):

    def _cat(self, msg):
        r = parse_message(msg)
        self.assertIsNotNone(r)
        return r['category']

    def test_travel_ola(self):     self.assertEqual(self._cat("500 ola"), "travel")
    def test_travel_uber(self):    self.assertEqual(self._cat("uber 300"), "travel")
    def test_food_swiggy(self):    self.assertEqual(self._cat("swiggy 420"), "food")
    def test_food_zomato(self):    self.assertEqual(self._cat("zomato dinner 180"), "food")
    def test_food_chai(self):      self.assertEqual(self._cat("60 chai biscuits"), "food")
    def test_groceries_blinkit(self): self.assertEqual(self._cat("blinkit 900"), "groceries")
    def test_groceries_zepto(self):   self.assertEqual(self._cat("zepto 1200 vegetables"), "groceries")
    def test_clothes_myntra(self): self.assertEqual(self._cat("1.5k myntra shirt"), "clothes")
    def test_rent(self):           self.assertEqual(self._cat("15000 rent"), "rent")
    def test_bills_electricity(self): self.assertEqual(self._cat("1250 electricity bill"), "bills")
    def test_luxuries_netflix(self):  self.assertEqual(self._cat("999 netflix"), "luxuries")
    def test_investments_sip(self):   self.assertEqual(self._cat("5000 sip mutual fund"), "investments")
    def test_health_doctor(self):     self.assertEqual(self._cat("800 doctor visit"), "health")
    def test_education_udemy(self):   self.assertEqual(self._cat("1500 udemy course"), "education")
    def test_fallback_other(self):    self.assertEqual(self._cat("500 random unknown thing"), "other")


class TestTypeDetection(unittest.TestCase):

    def _type(self, msg):
        r = parse_message(msg)
        self.assertIsNotNone(r)
        return r['type']

    def test_salary_is_income(self):      self.assertEqual(self._type("got salary 75000"), "income")
    def test_cashback_is_income(self):    self.assertEqual(self._type("received cashback 45"), "income")
    def test_refund_is_income(self):      self.assertEqual(self._type("refund 200 amazon"), "income")
    def test_credited_is_income(self):    self.assertEqual(self._type("75000 credited salary"), "income")
    def test_expense_default(self):       self.assertEqual(self._type("swiggy 420"), "expense")
    def test_expense_ola(self):           self.assertEqual(self._type("spent 500 on ola"), "expense")


class TestNoteExtraction(unittest.TestCase):

    def _note(self, msg):
        r = parse_message(msg)
        self.assertIsNotNone(r)
        return r['note'].lower()

    def test_note_drops_amount(self):
        self.assertNotIn('500', self._note("spent 500 on ola"))

    def test_note_drops_filler(self):
        note = self._note("spent 500 on ola")
        self.assertNotIn('spent', note)
        self.assertNotIn('on', note)

    def test_note_keeps_merchant(self):
        self.assertIn('ola', self._note("spent 500 on ola"))

    def test_note_keeps_context(self):
        note = self._note("swiggy 420 dinner with team")
        self.assertIn('swiggy', note)
        self.assertIn('dinner', note)


class TestEdgeCases(unittest.TestCase):

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_message(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(parse_message("   "))

    def test_no_amount_returns_none(self):
        self.assertIsNone(parse_message("went to the market"))

    def test_zero_amount_returns_none(self):
        # "0" alone should not be treated as a valid amount
        r = parse_message("spent 0 on nothing")
        self.assertIsNone(r)


if __name__ == '__main__':
    unittest.main(verbosity=2)
