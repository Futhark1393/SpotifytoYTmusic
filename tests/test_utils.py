import unittest

from utils import normalize_text


class NormalizeTextTests(unittest.TestCase):
    def test_removes_noise_tokens(self) -> None:
        text = "Artist - Song (feat. Someone) [Remix]"
        self.assertEqual(normalize_text(text), "artist - song")

    def test_collapses_whitespace(self) -> None:
        text = "Artist   -   Song"
        self.assertEqual(normalize_text(text), "artist - song")


if __name__ == "__main__":
    unittest.main()
