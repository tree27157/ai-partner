"""文本切分策略。纯函数、无副作用，API 和脚本共用这一份。"""
import re

# ============ 策略 1：固定长度 ============
def split_fixed(text, size=300):
    chunks = []
    for i in range(0, len(text), size):
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
    return chunks


# ============ 策略 2：按标题 + 合并 ============
def split_by_head(text, target=350, min_size=150):
    # 第一步：按 1-2 级标题切（\n 后面紧跟 # 或 ##）
    sections = [s.strip() for s in re.split(r"\n(?=#{1,2} )", text) if s.strip()]

    # 第二步：从左往右，太小就并进来
    chunks, buf = [], ""
    for sec in sections:
        if not buf:
            buf = sec                              # 第一块
        elif len(buf) < min_size or len(buf) + len(sec) <= target:
            buf = buf + "\n\n" + sec               # 太小 / 装得下 → 合并
        else:
            chunks.append(buf)                     # 装不下了 → 收工，另起
            buf = sec
    if buf:
        chunks.append(buf)
    return chunks


# ============ 策略 3：策略 2 + 重叠 ============
def split_by_head_overlap(text, overlap=50):
    base = split_by_head(text)
    chunks = []
    for i, c in enumerate(base):
        if i == 0:
            chunks.append(c)
        else:
            chunks.append(base[i - 1][-overlap:] + "\n" + c)   # 拼上一块尾巴
    return chunks


STRATEGIES = {
    "fixed":   split_fixed,
    "head":    split_by_head,
    "overlap": split_by_head_overlap,
}