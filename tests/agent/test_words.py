import pytest

from app.agent.words import classify


@pytest.mark.parametrize("text", ["சரி", "Sari, correct.", "haan", "ठीक है", "okay", "howdu", "ಸರಿ", "ശരി", "seri seri"])
def test_yes_words(text):
    assert classify(text) == "yes"


def test_classify_yes_tamil():
    assert classify("சரி") == "yes"


def test_classify_howdu_kannada():
    assert classify("Howdu") == "yes"


@pytest.mark.parametrize("text", ["vendaam", "வேண்டாம்", "nahi", "cancel it", "नहीं"])
def test_classify_no(text):
    assert classify(text) == "no"


def test_classify_no_vendaam():
    assert classify("Vendaam") == "no"


def test_classify_book_is_not_ok():
    assert classify("book it") == "other"


def test_classify_also_add_ten_shorts_is_other():
    assert classify("sari, also add ten shorts") == "other"


def test_yes_and_no_together_is_other():
    assert classify("sari vendaam") == "other"


def test_empty_is_other():
    assert classify("") == "other"
