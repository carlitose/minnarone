from minnarone.original_chat_output import normalize_original_chat_response


def test_normalizes_exact_re_msg_response():
    response = normalize_original_chat_response(
        "RE: boss fight\nMSG: bella giocata"
    )

    assert response.reason == "boss fight"
    assert response.message == "bella giocata"
    assert response.end_conversation is False
    assert response.raw_text == "RE: boss fight\nMSG: bella giocata"
    assert response.display_text == "RE: boss fight\nMSG: bella giocata"


def test_tolerates_minor_label_formatting_and_preamble():
    response = normalize_original_chat_response(
        "Certo, ecco:\n\nre :  boss fight  \nmsg :  bella giocata  "
    )

    assert response.reason == "boss fight"
    assert response.message == "bella giocata"
    assert response.display_text == "RE: boss fight\nMSG: bella giocata"


def test_normalizes_missing_colons_to_canonical_re_msg_lines():
    response = normalize_original_chat_response(
        "RE boss fight\nMSG bella giocata"
    )

    assert response.reason == "boss fight"
    assert response.message == "bella giocata"
    assert response.display_text == "RE: boss fight\nMSG: bella giocata"


def test_normalizes_malformed_msg_separator_to_canonical_re_msg_lines():
    response = normalize_original_chat_response(
        "RE: boss fight\nMSG - bella giocata"
    )

    assert response.reason == "boss fight"
    assert response.message == "bella giocata"
    assert response.display_text == "RE: boss fight\nMSG: bella giocata"


def test_uses_unlabeled_body_as_message_when_msg_label_is_missing():
    response = normalize_original_chat_response(
        "RE: boss fight\nbella giocata"
    )

    assert response.reason == "boss fight"
    assert response.message == "bella giocata"
    assert response.display_text == "RE: boss fight\nMSG: bella giocata"


def test_display_text_keeps_both_labels_when_reason_is_missing():
    response = normalize_original_chat_response("MSG: bella giocata")

    assert response.reason == ""
    assert response.message == "bella giocata"
    assert response.display_text == "RE: \nMSG: bella giocata"


def test_uses_unlabeled_response_as_message_when_both_labels_are_missing():
    response = normalize_original_chat_response("bella giocata")

    assert response.reason == ""
    assert response.message == "bella giocata"
    assert response.display_text == "RE: \nMSG: bella giocata"


def test_marks_end_conv_without_hiding_it_from_display_text():
    response = normalize_original_chat_response("RE: idle\nMSG: #end_conv")

    assert response.message == "#end_conv"
    assert response.end_conversation is True
    assert response.display_text == "RE: idle\nMSG: #end_conv\n(skip: not sent)"
