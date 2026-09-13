
import re
import logging

logger = logging.getLogger(__name__)

BAD_WORDS = [
    'хуй', 'пизда', 'ебал', 'ебать', 'блядь', 'бля', 'пиздец', 'охуенно', 'охуенный',
    'ебу', 'выеб', 'заеб', 'наеб', 'съеб', 'уеб', 'выебан', 'долбоеб', 'мудак',
    'гандон', 'пидор', 'пидорас', 'шлюха', 'мразь', 'сука', 'тварь', 'ублюдок',
    'fuck', 'shit', 'asshole', 'bitch', 'bastard', 'dick', 'pussy', 'cunt', 'whore',
]

def _create_bad_words_pattern():
    words_pattern = '|'.join(re.escape(word) for word in BAD_WORDS)
    return re.compile(r'\b(' + words_pattern + r')\b', re.IGNORECASE)

_bad_words_pattern = _create_bad_words_pattern()

def contains_bad_words(text: str | None) -> bool:
   
    if not text:
        return False
    return _bad_words_pattern.search(text) is not None
