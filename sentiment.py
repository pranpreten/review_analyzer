from pathlib import Path
import json
import math
import re


class Analyzer:
    def __init__(self, path=None):
        path = Path(path) if path else Path(__file__).with_name('sentiment_lexicon.json')
        self.lexicon = json.loads(path.read_text(encoding='utf-8'))
        ordered = sorted(self.lexicon, key=len, reverse=True)
        self.pattern = re.compile('|'.join(re.escape(term) for term in ordered), re.IGNORECASE)

    def analyze(self, text):
        text = re.sub(r'\s+', ' ', str(text)).strip()
        if not text:
            return {'label': '분석 불가', 'score': 0.0, 'matches': [], 'reason': '빈 리뷰'}
        matches = []
        contrasts = list(re.finditer(r'하지만|그런데|그러나|다만', text))
        pivot = contrasts[-1].end() if contrasts else None
        for match in self.pattern.finditer(text):
            term = match.group().lower()
            value = float(self.lexicon[term])
            before = text[max(0, match.start()-8):match.start()]
            after = text[match.end():match.end()+15]
            prefix_negation = re.search(r'(?:^|\s)(?:안|못|별로)\s*$', before)
            suffix_negation = re.match(r'(?:(?:하)?(?:지는|진|지)|하지는|하진|은|는)?\s*(?:않|못)', after)
            negated = bool(prefix_negation) != bool(suffix_negation)
            if negated:
                value *= -0.8
            if re.search(r'(정말|매우|아주|너무|완전)\s*$', before):
                value *= 1.3
            if pivot:
                value *= 1.25 if match.start() >= pivot else 0.75
            matches.append({'term': match.group(), 'value': round(value, 2), 'negated': negated})
        score = sum(item['value'] for item in matches) / math.sqrt(max(1, len(matches)))
        label = '긍정' if score >= 0.65 else '부정' if score <= -0.65 else '중립'
        reason = ', '.join(f"{item['term']}{' (부정어 반영)' if item['negated'] else ''}" for item in matches) or '사전에 일치하는 표현 없음'
        return {'label': label, 'score': round(score, 3), 'matches': matches, 'reason': reason}


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text
