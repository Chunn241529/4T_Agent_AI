
OLLAMA_API_URL = "http://localhost:11434/api"
brief_history_model = "4T-S"
history = []  # Danh sách lưu lịch sử hội thoại

async def summarize_history(session, past_conversations: list, prompt: str) -> str:

    """Tóm tắt lịch sử hội thoại sử dụng LLM."""
    if not past_conversations:
        return ""

    past_messages_flat = [msg for conv in past_conversations for msg in conv]
    history_str = "\n\n".join([
        f"[{msg['role'].capitalize()}]: {msg['content']}"
        for msg in past_messages_flat
        if msg["role"] in ["user", "assistant"]
    ])

    summary_prompt = f"""
    Tóm tắt lịch sử hội thoại sau bằng tiếng Việt, liên quan đến `{prompt}`:
    {history_str}
    Giữ thông tin cần thiết, ý chính trong history. Chỉ cần trả ra tóm tắt. Không thêm bất kì thông tin nào khác.
    """

    payload = {
        "model": brief_history_model,
        "messages": [{"role": "user", "content": summary_prompt}],
        "stream": False,
        "options": {"temperature": 0.35, "num_predict": -1}
    }

    try:
        async with session.post(f"{OLLAMA_API_URL}/chat", json=payload) as response:
            if response.status == 200:
                data = await response.json()
                summary = data.get("message", {}).get("content", "").strip()

                return summary
            else:
                return ""
    except Exception as e:
        return ""

