import re
import jieba
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.post import Post

def tokenize_query(query_str: str) -> list[str]:
    # 1. 提取标识符 (camelCase, snake_case)
    tokens = set()
    raw_words = query_str.split()
    for w in raw_words:
        tokens.add(w.lower())
        # camelCase 拆解
        camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", w)
        for cp in camel_parts:
            if len(cp) > 1:
                tokens.add(cp.lower())
        # snake_case 拆解
        snake_parts = w.split("_")
        for sp in snake_parts:
            if len(sp) > 1:
                tokens.add(sp.lower())

    # 2. 中文 jieba 分词
    seg_list = jieba.cut_for_search(query_str)
    for seg in seg_list:
        seg_clean = seg.strip()
        if len(seg_clean) > 0:
            tokens.add(seg_clean.lower())

    return list(tokens)

async def perform_search(db: AsyncSession, q: str, limit: int = 15) -> list[dict]:
    """
    相关度检索：标题 10 / 标签 5 / 代码 2 / 正文 1 加权（PRD 8.7）。
    博客数据量小（千篇以内），直接在内存中打分比 LIKE + 时间排序准确得多，
    并且能命中代码块里的标识符。
    """
    q = (q or "").strip()
    if not q:
        return []

    tokens = [t for t in tokenize_query(q) if t.strip()]
    # 完整查询优先，其次是较长的分词，避免单字噪声
    phrase = q.lower()
    tokens = sorted(set(tokens), key=len, reverse=True)[:8]
    if phrase not in tokens:
        tokens.insert(0, phrase)

    result = await db.execute(
        select(Post)
        .options(selectinload(Post.tags))
        .where(Post.status == "published", Post.visibility == "public", Post.deleted_at.is_(None))
    )
    posts = result.scalars().all()

    scored = []
    for p in posts:
        title = (p.title or "").lower()
        subtitle = (p.subtitle or "").lower()
        tags = " ".join(t.name.lower() for t in p.tags)
        md = p.content_md or ""
        code = " ".join(re.findall(r"```[\s\S]*?```", md)).lower()
        body = (p.content_text or "").lower()

        score = 0.0
        for i, tok in enumerate(tokens):
            weight = 3.0 if i == 0 else (1.0 if len(tok) > 1 else 0.3)
            score += weight * (
                10 * title.count(tok)
                + 4 * subtitle.count(tok)
                + 5 * tags.count(tok)
                + 2 * min(code.count(tok), 5)
                + 1 * min(body.count(tok), 10)
            )
        if score <= 0:
            continue

        # 上下文片段：优先正文，其次代码
        snippet = ""
        source = p.content_text or ""
        lower = source.lower()
        for tok in tokens:
            idx = lower.find(tok)
            if idx != -1:
                start = max(0, idx - 36)
                end = min(len(source), idx + 84)
                snippet = ("…" if start > 0 else "") + source[start:end].strip() + ("…" if end < len(source) else "")
                break
        if not snippet:
            snippet = p.excerpt or (source[:110] + "…" if len(source) > 110 else source)

        scored.append((score, p.published_at or "", {
            "type": "post",
            "id": p.id,
            "slug": p.slug,
            "title": p.title,
            "snippet": snippet,
            "url": f"/posts/{p.slug}",
            "number": p.number,
            "published_at": p.published_at,
            "tags": [t.name for t in p.tags],
        }))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [hit for _, _, hit in scored[:limit]]
