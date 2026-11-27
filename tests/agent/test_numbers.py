import pytest

from app.agent.numbers import digits


@pytest.mark.parametrize("said, want", [
    ("Kerala Fancy-ku irupathu naalu print palazzo venum", "Kerala Fancy-ku 24 print palazzo venum"),
    ("Kerala Fancyki irupathinaalu Plain Palaso venum", "Kerala Fancyki 24 Plain Palaso venum"),
    ("crop top S aaru M aaru L aaru", "crop top S 6 M 6 L 6"),
    ("crop top S pathu M pathu", "crop top S 10 M 10"),
    ("M-a pannendu aakkunga", "M-a 12 aakkunga"),
    ("print palazzo randu dozen venam", "print palazzo 24 venam"),
    ("aimbathu piece", "50 piece"),
    ("aayiram rupees UPI-la", "1000 rupees UPI-la"),
    ("paththayiram cash", "10000 cash"),
    ("muppathu stone pant", "30 stone pant"),
])
def test_tamil_number_words_become_digits(said, want):
    assert digits(said) == want


@pytest.mark.parametrize("text", ["Sari, correct.", "Girnar Transport se bhej dena", "Kerala Fancy bill podunga",
                                  "girls pant 1 se 10 saal 50 piece"])
def test_other_text_is_unchanged(text):
    assert digits(text) == text


@pytest.mark.parametrize("said, want", [
    ("24 Plain Palaso venum, SR, M6, L6, XL6.", "24 Plain Palaso venum, S 6, M6, L6, XL6."),
    ("SR, MR, LR, XLR", "S 6, M 6, L 6, XL 6"),
    ("S R, M R, L R, XL R", "S 6, M 6, L 6, XL 6"),
])
def test_size_letter_with_r_is_aaru(said, want):
    """Live STT writes 'S aaru' (S six) as 'SR' or 'S R' (seen in four live runs on 27 Nov)."""
    assert digits(said) == want


def test_words_ending_in_r_are_untouched():
    assert digits("KPR Transport, Sir, MR Traders") == "KPR Transport, Sir, MR Traders"
