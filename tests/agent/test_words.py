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


from app.agent.words import unbacked_claim


@pytest.mark.parametrize("text", ["Kerala Fancy-ku girls pant 50 piece add panren.", "Order add panniten",
                                  "I have added it", "சேர்த்துட்டேன்", "मैंने जोड़ दिया", "S 6 M 6 nu potten",
                                  "saved the order"])
def test_claims_without_a_tool_are_caught(text):
    assert unbacked_claim(text, tool_called=False)


def test_claim_backed_by_a_tool_is_fine():
    assert not unbacked_claim("add panren", tool_called=True)


@pytest.mark.parametrize("text", ["Which customer is this for?", "எத்தனை பீஸ் M size-ல?", "Kitne piece chahiye?"])
def test_questions_are_not_claims(text):
    assert not unbacked_claim(text, tool_called=False)
