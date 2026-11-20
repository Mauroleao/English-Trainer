from app.textutil import check_answer, extract_words, make_pt_flag, tokenize


def test_contractions_are_equivalent():
    assert check_answer("I am Paulo", ["I'm Paulo"]).correct
    assert check_answer("I'm Paulo", ["I am Paulo"]).correct
    assert check_answer("Do not go", ["Don't go"]).correct
    assert check_answer("Let us keep in touch", ["Let's keep in touch"]).correct


def test_curly_apostrophe_and_case_and_punctuation_ignored():
    assert check_answer("i’m paulo!!", ["I'm Paulo."]).correct
    assert check_answer("  hello   world ", ["Hello, world."]).correct


def test_spelling_must_be_exact():
    r = check_answer("I would like the chiken", ["I would like the chicken"])
    assert not r.correct
    assert [m.status for m in r.marks][-1] == "close"  # quase: erro de digitação


def test_accents_matter_by_default_and_can_be_ignored():
    r = check_answer("voce tem uma reserva", ["Você tem uma reserva"], lang="pt")
    assert not r.correct
    assert r.marks[0].status == "close"
    assert check_answer("voce tem uma reserva", ["Você tem uma reserva"], lang="pt", ignore_accents=True).correct


def test_missing_and_wrong_words():
    r = check_answer("I would like the chicken", ["I would like the chicken with rice please"])
    assert not r.correct
    assert r.missing == 3
    assert all(m.status == "ok" for m in r.marks)
    r = check_answer("I would like the pizza with rice please", ["I would like the chicken with rice please"])
    assert [m.status for m in r.marks if m.text == "pizza"] == ["wrong"]


def test_strict_exact_requires_case_and_punctuation():
    r = check_answer("i would like a table", ["I would like a table."], strict_exact=True)
    assert not r.correct and r.format_issue
    assert check_answer("I would like a table.", ["I would like a table."], strict_exact=True).correct


def test_alternative_translations():
    alts = ["Você tem uma reserva?", "Tem reserva?"]
    assert check_answer("tem reserva", alts, lang="pt").correct


def test_empty_answer_is_wrong():
    r = check_answer("", ["Hello"])
    assert not r.correct and r.missing == 1


def test_portuguese_words_are_detected_and_corrected():
    pt = "Eu gostaria de uma mesa para dois."
    en = "I would like a table for two."
    flag = make_pt_flag(pt, en)
    r = check_answer("I would like a mesa for two", [en], pt_flag=flag)
    assert not r.correct
    assert r.corrections == [{"you_wrote": "mesa", "should_be": "table", "kind": "portuguese", "explanation": ""}]


def test_missing_and_extra_corrections():
    r = check_answer("I like a very table for two", ["I would like a table for two"])
    kinds = {(c["you_wrote"], c["should_be"], c["kind"]) for c in r.corrections}
    assert ("", "would", "missing") in kinds
    assert ("very", "", "extra") in kinds


def test_extract_words():
    words = dict(extract_words("John's dog is here. The dog runs; 3 cats."))
    assert list(words) == ["john", "dog", "is", "here", "the", "runs", "cats"]
    assert words["dog"] == "John's dog is here."  # frase da primeira ocorrência
    assert "3" not in words


def test_extract_words_keeps_contractions_but_strips_possessive():
    words = [w for w, _ in extract_words("Let's go. It's John's car, isn't it?")]
    assert words == ["let's", "go", "it's", "john", "car", "isn't", "it"]


def test_tokenize_keeps_hyphen_and_apostrophe():
    assert tokenize("My mother-in-law doesn't know.") == ["My", "mother-in-law", "doesn't", "know"]
