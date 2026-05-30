import re
from collections import Counter


STOPWORDS = {
    "그리고",
    "그러나",
    "또한",
    "대한",
    "관련",
    "이번",
    "있는",
    "했다",
    "한다",
    "지난",
    "최근",
    "위해",
    "통해",
}


def _clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\.{2,}|…", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text):
    sentences = re.split(r"(?<=[.!?。！？다요죠함음])\s+", text)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 12]


def _keywords(text, limit=4):
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", text)
    words = [word for word in words if word not in STOPWORDS]
    return [word for word, _ in Counter(words).most_common(limit)]


def _fallback_summary(text, sentence_count=2):
    sentences = _split_sentences(text)

    if not sentences:
        return text[:120]

    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", text)
    frequencies = Counter(word for word in words if word not in STOPWORDS)

    scored = []
    for index, sentence in enumerate(sentences):
        sentence_words = re.findall(r"[가-힣A-Za-z0-9]{2,}", sentence)
        score = sum(frequencies[word] for word in sentence_words)
        scored.append((score, index, sentence))

    selected = sorted(scored, reverse=True)[:sentence_count]
    ordered = sorted(selected, key=lambda item: item[1])
    return " ".join(sentence for _, _, sentence in ordered)


def _compact_text(text, limit=95):
    text = _clean_text(text)

    if len(text) <= limit:
        return text

    clipped = text[:limit].rstrip()
    breakpoints = [
        clipped.rfind("다."),
        clipped.rfind("요."),
        clipped.rfind("."),
        clipped.rfind(" "),
    ]
    breakpoint = max(breakpoints)

    if breakpoint >= 35:
        clipped = clipped[: breakpoint + 1].rstrip()

    return f"{clipped}..."


def _sumy_summary(text, sentence_count=2):
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.lex_rank import LexRankSummarizer

    parser = PlaintextParser.from_string(text, Tokenizer("korean"))
    summarizer = LexRankSummarizer()
    sentences = summarizer(parser.document, sentence_count)
    return " ".join(str(sentence) for sentence in sentences).strip()


def summarize_news_item(title, description):
    source_text = _clean_text(f"{title}. {description}")
    summary = ""

    try:
        summary = _sumy_summary(source_text, sentence_count=1)
    except Exception:
        summary = _fallback_summary(source_text, sentence_count=1)

    if not summary:
        summary = _fallback_summary(source_text, sentence_count=1)

    keywords = _keywords(source_text)
    keyword_text = ", ".join(keywords[:3]) if keywords else "산업 변화"

    return {
        "summary": _compact_text(summary, limit=105),
        "interview_point": f"{keyword_text} 흐름이 지원 기업의 사업과 직무 역량에 어떤 영향을 주는지 연결해 보세요.",
        "keywords": keywords,
    }
