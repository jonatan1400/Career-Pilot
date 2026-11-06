"""Dependency-free tests: python -m unittest discover -s tests -p test_core.py."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from documents import clean_text, ground_document, extract_text, DocumentError, MAX_BYTES
from limits import UsageLimiter, CoachError
from formatting import escape_text


class CoreTests(unittest.TestCase):
    def test_untrusted_markdown_is_escaped(self):
        value = escape_text('![image](https://example.com) <script>')
        self.assertIn(r'\!\[image\]\(', value)
        self.assertIn(r'\<script\>', value)

    def test_clean_text(self):
        self.assertEqual(clean_text('  SQL\x00 Python  '), 'SQL Python')

    def test_empty_text(self):
        with self.assertRaisesRegex(DocumentError, 'no readable text'):
            clean_text('  ')

    def test_large_text(self):
        with self.assertRaisesRegex(DocumentError, 'too long'):
            clean_text('x' * 40001)

    def test_upload_limits(self):
        for content in [b'', b'x' * (MAX_BYTES + 1)]:
            with self.assertRaisesRegex(DocumentError, '5 MB'):
                extract_text(content, 'resume.pdf')

    def test_unsupported_extension(self):
        with self.assertRaisesRegex(DocumentError, 'Only PDF and DOCX'):
            extract_text(b'content', 'resume.exe')

    def test_short_grounding_complete(self):
        result = ground_document('Built a Python project.', 'Python', 'R')
        self.assertFalse(result['partial'])
        self.assertEqual(result['sections'], [{'id': 'R1', 'text': 'Built a Python project.'}])

    def test_retrieval_finds_late_evidence(self):
        document = 'background ' * 2800 + '\nPyTorch recommender deployed portfolio\n'
        result = ground_document(document, 'PyTorch recommender deployed portfolio', 'R')
        self.assertTrue(result['partial'])
        self.assertLessEqual(sum(len(s['text']) for s in result['sections']), 18000)
        self.assertIn('PyTorch', ' '.join(s['text'] for s in result['sections']))
        self.assertEqual(result['sections'][0]['id'], 'R1')

    def test_empty_grounding(self):
        self.assertEqual(ground_document('', 'role', 'J'), {'sections': [], 'partial': False})

    def test_quota_expires(self):
        limiter = UsageLimiter(2)
        limiter.reserve(0)
        limiter.reserve(1)
        with self.assertRaises(CoachError):
            limiter.reserve(2)
        limiter.reserve(3600)
        self.assertEqual(len(limiter.calls), 2)

    def test_concurrent_quota(self):
        limiter = UsageLimiter(5)
        def reserve(_):
            try:
                limiter.reserve(100)
                return True
            except CoachError:
                return False
        with ThreadPoolExecutor(max_workers=10) as pool:
            self.assertEqual(sum(pool.map(reserve, range(30))), 5)


if __name__ == '__main__':
    unittest.main()
