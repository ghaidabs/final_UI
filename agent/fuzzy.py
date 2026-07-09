from rapidfuzz import fuzz, process

FUZZY_FLOOR = 75  

def find_fuzzy(query: str, candidates: list[dict], key_fn, top_k: int = 3) -> list[dict]:
    if not candidates:
        return []

    choices = {i: key_fn(c) for i, c in enumerate(candidates)}
    matches = process.extract(
        query, choices, scorer=fuzz.WRatio, limit=top_k
    )
    
    # matches: list of (matched_string, score, choice_key)
    results = []
    for matched_str, score, idx in matches:
        if score >= FUZZY_FLOOR:
            results.append({**candidates[idx], "_fuzzy_score": score / 100})
    return results