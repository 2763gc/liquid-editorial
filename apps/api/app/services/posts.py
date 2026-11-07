import re
import json
from pypinyin import lazy_pinyin

def slugify(text: str) -> str:
    # 中文拼音转换 + 字符清理
    pinyin_parts = lazy_pinyin(text)
    joined = "-".join(pinyin_parts)
    cleaned = re.sub(r"[^a-zA-Z0-9\-_]", "", joined).lower()
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "untitled"

def extract_toc(markdown_text: str) -> list[dict]:
    toc = []
    # 匹配 ## 标题 与 ### 标题
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    for match in heading_pattern.finditer(markdown_text):
        level = len(match.group(1))
        title = match.group(2).strip()
        # 清除行内 markdown 标记
        clean_title = re.sub(r"[`*_{}\[\]()#+\-.!]", "", title).strip()
        anchor = slugify(clean_title)
        toc.append({
            "level": level,
            "text": clean_title,
            "anchor": anchor
        })
    return toc

def calculate_reading_metrics(markdown_text: str) -> tuple[int, int, str]:
    # 移除代码块与标记，提取纯文本
    text_clean = re.sub(r"```[\s\S]*?```", "", markdown_text)
    text_clean = re.sub(r"!\[.*?\]\(.*?\)", "", text_clean)
    text_clean = re.sub(r"\[.*?\]\(.*?\)", "", text_clean)
    text_clean = re.sub(r"[#*`>~_\-]", " ", text_clean)

    # 汉字计数
    chinese_chars = len(re.findall(r"[\u4e00-\u9fa5]", text_clean))
    # 英文单词计数
    english_words = len(re.findall(r"\b[a-zA-Z]+\b", text_clean))
    # 代码块中行数附加
    code_blocks = re.findall(r"```[\s\S]*?```", markdown_text)
    code_lines = sum(len(cb.splitlines()) for cb in code_blocks)

    total_words = chinese_chars + english_words + (code_lines * 5)
    # 按中文 400字/分钟，代码 50行/分钟估算
    reading_minutes = max(1, round(total_words / 350))

    # 纯文本供搜索
    plain_text = re.sub(r"\s+", " ", text_clean).strip()
    return total_words, reading_minutes, plain_text
