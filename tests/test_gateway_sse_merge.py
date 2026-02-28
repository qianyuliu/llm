from app.gateway import Gateway


def test_merge_sse_chunks_to_chat_completion() -> None:
    raw = (
        'data:{"id":"chatcmpl-1","created":123,"model":"qwen","object":"chat.completion.chunk",'
        '"choices":[{"index":0,"delta":{"role":"assistant","content":"你"}}]}\n\n'
        'data:{"id":"chatcmpl-1","created":123,"model":"qwen","object":"chat.completion.chunk",'
        '"choices":[{"index":0,"delta":{"content":"好"}}]}\n\n'
        'data:{"id":"chatcmpl-1","created":123,"model":"qwen","object":"chat.completion.chunk",'
        '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    )
    merged = Gateway._merge_sse_chunks_to_chat_completion(
        raw_text=raw,
        requested_model="neibu_qwen3_coder",
    )
    assert merged is not None
    assert merged["object"] == "chat.completion"
    assert merged["model"] == "neibu_qwen3_coder"
    assert merged["choices"][0]["message"]["content"] == "你好"
    assert merged["choices"][0]["finish_reason"] == "stop"

