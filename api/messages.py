

def estimate_tokens(text:str):
    return int(len(text)/1.5) + 1

def trim_by_tokens(messages, max_tokens: int= 6000):
    total = sum(estimate_tokens(msg.get("content" or "")) for msg in messages)
    print(f"裁剪前tokens:{total}")
    if total < max_tokens:
        return messages
    acc, start = 0, len(messages)
    for i in range(len(messages)-1,-1,-1):
        acc += estimate_tokens(messages[i].get("content" or ""))
        if acc > max_tokens:
            break
        start = i

    while start < len(messages) and messages[start]["role"] != "user":
        start += 1

    if start >= len(messages):
        for j in range(len(messages) - 1, -1, -1):
            if messages[j]["role"] == "user":
                start = j
                break
        print("预算不足，已放宽一次以保住结构")
    kept = messages[start:]
    new_total = sum(estimate_tokens(msg.get("content" or "")) for msg in kept)
    print(f"裁剪后tokens:{new_total}")
    return kept


def clip_tool_result(text, limit: int = 2000) -> str:
    s = str(text)
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n\n…（内容过长已截断，原长 {len(s)} 字符）"

def check_and_fix_messages(messages):
    """
        检查并修复 messages 的两条结构不变量，返回发现的问题。
        1. 首条必须是 user
        2. assistant 的每个 tool_call 必须有配对的 tool 回复；孤立的 tool 消息必须删掉
        用 if + 日志降级，不用 assert（python -O 会删掉 assert）
        """
    problems = []
    msgs = messages
    print("  [检查前]", [(m["role"], bool(m.get("tool_calls"))) for m in msgs])

    idx = 0
    while idx < len(msgs) and msgs[idx]["role"] != "user":
        problems.append(f"丢弃开头 {msgs[idx]['role']} 消息")
        idx += 1

    kept = []
    for m in msgs[idx:]:
        if m["role"] == "tool":
            tid = m.get("tool_call_id")
            has_call = any(
                k["role"] == "assistant"
                and any(tc["id"] == tid for tc in k.get("tool_calls", []))
                for k in kept
            )
            if not has_call:
                problems.append(f"丢弃孤立 tool 消息（id={tid}）")
                continue
        kept.append(m)

    answered = {m.get("tool_call_id") for m in kept if m["role"] == "tool"}
    repaired = []
    for m in list(kept):
        repaired.append(m)
        if m["role"] == "assistant":
            for tc in m.get("tool_calls", []):
                if tc["id"] not in answered:
                    problems.append(f"补占位 tool 回复（id={tc['id']}）")
                    repaired.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": "该工具调用已被系统跳过，不要重试。请基于已有信息直接回答用户。",
                    })
    kept = repaired
    print("  [检查后]", [(m["role"], bool(m.get("tool_calls"))) for m in kept])

    if problems:
        print("[结构告警]", problems)
    return kept
