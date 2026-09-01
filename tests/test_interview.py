from scripts.interview import start_interview, next_question


def test_first_question_asks_year_in_plain_language():
    state = start_interview()
    assert "哪一年" in state.question
    assert "税收居民" not in state.question
    assert "买入" not in state.question


def test_unknown_residence_does_not_use_tax_resident_term():
    state = start_interview()
    state = next_question(state, "2024")
    state = next_question(state, "我也不清楚")
    assert "税收居民" not in state.question
    assert "住" in state.question or "半年" in state.question


def test_never_asks_for_buy_price_or_id_card():
    texts = []
    state = start_interview()
    for answer in ["2024", "大部分时间在国内", "华泰", "先这些单子", "不知道"]:
        texts.append(state.question)
        state = next_question(state, answer)
    texts.append(state.question or "")
    blob = "".join(texts)
    assert "买入价" not in blob
    assert "身份证" not in blob
    assert "TIN" not in blob
