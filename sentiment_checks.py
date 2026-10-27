import unittest
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import Mock, patch
from sentiment import Analyzer, safe_cell
from review_dashboard import App


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = Analyzer()

    def test_labels(self):
        cases = [('배송이 빠르고 아주 만족합니다', '긍정'), ('불량이고 최악입니다', '부정'), ('검정색을 주문했습니다', '중립'), ('  ', '분석 불가')]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.analyzer.analyze(text)['label'], expected)

    def test_negation(self):
        cases = [('좋지 않아요', '부정'), ('추천하지 않습니다', '부정'), ('안 좋아요', '부정'), ('나쁘지 않아요', '긍정'), ('불편하지 않아요', '긍정')]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.analyzer.analyze(text)['label'], expected)

    def test_longer_phrase_wins(self):
        result = self.analyzer.analyze('불친절하고 불만족스럽습니다')
        self.assertEqual([row['term'] for row in result['matches']], ['불친절', '불만족'])
        self.assertEqual(result['label'], '부정')

    def test_contrast_and_evidence(self):
        result = self.analyzer.analyze('좋아요. 하지만 최악이었어요')
        self.assertEqual(result['label'], '부정')
        self.assertIn('최악', result['reason'])

    def test_csv_formula_escaping(self):
        self.assertTrue(safe_cell('=1+1').startswith("'"))
        self.assertEqual(safe_cell('일반 리뷰'), '일반 리뷰')

    def test_invalid_encoding_preserves_previous_data(self):
        previous = [{'review': '이전 리뷰'}]
        state = SimpleNamespace(busy=False, rows=previous)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'broken.csv'
            path.write_bytes(b'review\n' + b'normal text\n'*3000 + b'\xff\n')
            with patch('review_dashboard.messagebox.showerror') as error:
                App.load_csv(state, path)
            error.assert_called_once()
            self.assertIs(state.rows, previous)

    def test_cp949_csv(self):
        state = SimpleNamespace(busy=False, rows=[], column_box=Mock(), column=Mock(), tree=Mock(), draw_chart=Mock(), status=Mock())
        state.tree.get_children.return_value = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'reviews.csv'
            path.write_text('review\n좋아요\n불친절합니다\n', encoding='cp949')
            with patch('review_dashboard.messagebox.showerror') as error:
                App.load_csv(state, path)
            error.assert_not_called()
            self.assertEqual(state.rows, [{'review': '좋아요'}, {'review': '불친절합니다'}])


if __name__ == '__main__':
    unittest.main()
