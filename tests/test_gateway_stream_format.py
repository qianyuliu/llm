from app.gateway import Gateway


def test_to_sse_bytes_has_data_prefix_and_double_newline() -> None:
    payload = {"error": {"message": "upstream stream interrupted"}}
    raw = Gateway._to_sse_bytes(payload).decode("utf-8")
    assert raw.startswith("data:")
    assert raw.endswith("\n\n")

