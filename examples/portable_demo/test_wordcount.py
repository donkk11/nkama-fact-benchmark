import unittest
from wordcount import word_count, unique_words

class WordCountTests(unittest.TestCase):
    def test_counts_words(self):
        self.assertEqual(word_count("a b c"), 3)
    def test_empty(self):
        self.assertEqual(word_count(""), 0)
    def test_unique_case_insensitive(self):
        self.assertEqual(unique_words("The the THE cat"), 2)

if __name__ == "__main__":
    unittest.main()
