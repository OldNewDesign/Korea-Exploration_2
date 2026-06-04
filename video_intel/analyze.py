"""Analysis step: turn metadata + transcript into structured, categorized,
English-friendly fields using Claude. Falls back to a heuristic (no network)
if ANTHROPIC_API_KEY is unset, so the pipeline still produces output."""
import json
import re
from . import config


def _client():
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except Exception:
        return None
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _prompt(meta, transcript_text, transcript_lang, url, platform):
    cats = ", ".join(config.CATEGORIES)
    tags = " ".join("#" + t for t in (meta.get("tags") or []))
    blob = "\n".join(filter(None, [
        f"Title/caption: {meta.get('title','')}",
        f"Description: {meta.get('description','')}",
        f"Hashtags: {tags}" if tags else "",
        f"Detected audio language: {transcript_lang}" if transcript_lang else "",
        f"Spoken transcript: {transcript_text}" if transcript_text else "",
    ]))
    return (
        "You are a multilingual short-video metadata analyst. Analyze ONE saved "
        "social video and return structured data.\n\n"
        f"URL: {url}\nPlatform: {platform}\n"
        f"Uploader (may be blank): {meta.get('uploader','')}\n\n"
        "Source material (any language) is between <START> and <END>:\n<START>\n"
        f"{blob}\n<END>\n\n"
        "Choose main_category from EXACTLY this list (single best fit; use the "
        f"last item if none fit):\n{cats}\n\n"
        "Return ONLY a minified JSON object (no markdown, no prose) with keys:\n"
        '{"creator_username":string,"detected_language":string,'
        '"caption_english":string,"caption_original":string,"summary":string,'
        '"main_category":string,"sub_category":string,"location_mentioned":string,'
        '"hashtags":string[],"keywords":string[],"usefulness_score":number,'
        '"action_type":string,"confidence":number}\n'
        "Rules: caption_english = clean English version (translate if needed). "
        "caption_original = original-language text only if non-English, else \"\". "
        "summary = 1-2 sentence English summary. location_mentioned = place name + "
        "area/address if present, else \"\". hashtags = without #. usefulness_score "
        "= 1-5. action_type = one of visit, save, research, ignore, share, "
        "create_content. confidence = 0-1 for the category choice."
    )


def _parse_json(text):
    text = re.sub(r"```json", "", text, flags=re.I).replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("model did not return JSON")
        return json.loads(m.group(0))


def _norm_list(x):
    if not isinstance(x, list):
        return []
    return [str(s).lstrip("#").strip() for s in x if str(s).strip()]


def _normalize(j, meta, transcript_text, transcript_lang, platform_cls):
    cats = config.CATEGORIES
    topic = (j.get("main_category") or "").strip()
    if topic not in cats:
        topic = cats[-1]
    try:
        score = max(1, min(5, int(round(float(j.get("usefulness_score", 3))))))
    except Exception:
        score = 3
    try:
        conf = max(0.0, min(1.0, float(j.get("confidence", 0.6))))
    except Exception:
        conf = 0.6
    summary = (j.get("summary") or j.get("caption_english") or "").strip()
    return {
        "creator": (j.get("creator_username") or meta.get("uploader") or "Unknown").strip() or "Unknown",
        "topic": topic,
        "sub_category": (j.get("sub_category") or "").strip(),
        "summary": summary,
        "caption_english": (j.get("caption_english") or "").strip(),
        "caption_original": (j.get("caption_original") or "").strip(),
        "transcript_original": transcript_text or "",
        "detected_language": (j.get("detected_language") or transcript_lang or "").strip(),
        "location": (j.get("location_mentioned") or "").strip(),
        "hashtags": ", ".join(_norm_list(j.get("hashtags")) or list(meta.get("tags") or [])),
        "keywords": ", ".join(_norm_list(j.get("keywords"))),
        "usefulness": score,
        "action": (j.get("action_type") or "save").strip(),
        "confidence": conf,
        "needs_review": 1 if (topic == cats[-1] or score <= 2 or conf < 0.4) else 0,
    }


def _heuristic(meta, transcript_text, transcript_lang, platform_cls):
    """No-API fallback: keep raw text, bucket as Other, flag for review."""
    summary = (meta.get("title") or meta.get("description") or transcript_text or "").strip()
    summary = (summary[:200] + "\u2026") if len(summary) > 200 else summary
    return {
        "creator": (meta.get("uploader") or "Unknown").strip() or "Unknown",
        "topic": config.CATEGORIES[-1],
        "sub_category": "",
        "summary": summary or "(no text captured)",
        "caption_english": "",
        "caption_original": "",
        "transcript_original": transcript_text or "",
        "detected_language": transcript_lang or "",
        "location": "",
        "hashtags": ", ".join(meta.get("tags") or []),
        "keywords": "",
        "usefulness": 3,
        "action": "research",
        "confidence": 0.0,
        "needs_review": 1,
    }


def analyze(meta, transcript_text, transcript_lang, url, platform, platform_cls):
    client = _client()
    if client is None:
        return _heuristic(meta, transcript_text, transcript_lang, platform_cls)
    prompt = _prompt(meta, transcript_text, transcript_lang, url, platform)
    for attempt in range(2):
        p = prompt if attempt == 0 else prompt + "\n\nIMPORTANT: respond with ONLY the JSON object, nothing else."
        try:
            msg = client.messages.create(
                model=config.ANALYZE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": p}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            j = _parse_json(text)
            return _normalize(j, meta, transcript_text, transcript_lang, platform_cls)
        except Exception:
            continue
    # couldn't get clean JSON after retry -> keep the video, flag for review
    return _heuristic(meta, transcript_text, transcript_lang, platform_cls)
