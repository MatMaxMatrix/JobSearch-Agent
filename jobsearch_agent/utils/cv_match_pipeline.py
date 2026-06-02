"""
CV Match Pipeline.

Reads a PDF CV, extracts a search profile via DeepSeek, scrapes recent LinkedIn
jobs across a list of countries (default: Netherlands, Germany, Italy), scores
each job against the CV with DeepSeek's LLM rubric, and produces a Markdown +
PDF report with a tailored cover letter for the top picks per country.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import dotenv
import requests
from pypdf import PdfReader

from jobsearch_agent.scraper.search.linkedin_scraper.scraper import LinkedInScraperSync
from jobsearch_agent.utils.job_database import JobDatabase

dotenv.load_dotenv()

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_COUNTRIES = ["Netherlands", "Germany", "Italy"]
DEFAULT_TOP_PER_COUNTRY = 5
DEFAULT_JOBS_PER_COUNTRY = 25
DEFAULT_MIN_SCORE = 75


def extract_cv_text(pdf_path: str) -> str:
    """Extract plain text from a PDF CV."""
    reader = PdfReader(pdf_path)
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def deepseek_chat(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 8000,
    timeout: int = 300,
) -> str:
    """Call DeepSeek chat-completions and return the assistant content string."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    # Read the model per call so the model picked in the UI (POST /config) takes effect.
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "stream": False,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(
        DEEPSEEK_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"DeepSeek HTTP {resp.status_code} for model={model!r}: "
            f"{resp.text[:500]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(
            f"DeepSeek returned non-JSON for model={model!r}: "
            f"{resp.text[:500]}"
        ) from e
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(
            f"DeepSeek response missing 'choices[0].message.content' "
            f"for model={model!r}: {json.dumps(data)[:500]}"
        ) from e
    if not content or not content.strip():
        raise RuntimeError(
            f"DeepSeek returned empty content for model={model!r}. "
            f"Full response: {json.dumps(data)[:500]}"
        )
    return content


def extract_cv_profile(cv_text: str) -> Dict[str, Any]:
    """Derive LinkedIn search keywords, seniority, and a summary from the CV."""
    system = (
        "You analyse CVs and extract optimal LinkedIn job-search parameters. "
        "Respond with JSON only, no commentary."
    )
    user = (
        "Read the CV and return JSON with these keys exactly:\n"
        '  "search_keywords": 3-7 word string for a LinkedIn job-search query\n'
        '  "experience_level": one of "internship", "entry_level", "associate", '
        '"mid_senior", "director", "executive"\n'
        '  "summary": single paragraph (~100 words) describing the candidate\n\n'
        f"CV:\n{cv_text}"
    )
    return json.loads(deepseek_chat(system, user, json_mode=True, max_tokens=6000))


def _job_field(job: Dict[str, Any], *names: str) -> Optional[str]:
    for n in names:
        v = job.get(n)
        if v:
            return v
    return None


def _job_for_llm(job: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "title": _job_field(job, "job_title", "title"),
            "company": _job_field(job, "company_name", "company"),
            "location": _job_field(job, "job_location", "location"),
            "description": (_job_field(job, "job_description", "description") or "")[:6000],
        },
        ensure_ascii=False,
    )


def score_job(cv_text: str, job: Dict[str, Any]) -> Dict[str, Any]:
    """Score CV-vs-job fit on 0-100 with a short rationale."""
    system = (
        "You are a senior recruiter. You compare a candidate CV with a job posting "
        "and score the fit. 100 = perfect match, 0 = irrelevant. JSON only."
    )
    user = (
        "Return JSON with keys:\n"
        '  "score": integer 0-100\n'
        '  "rationale": 2-3 sentences covering the strongest matches and the main gaps\n\n'
        f"CV:\n{cv_text}\n\nJOB:\n{_job_for_llm(job)}"
    )
    return json.loads(deepseek_chat(system, user, json_mode=True, max_tokens=6000))


def write_cover_letter(cv_text: str, job: Dict[str, Any]) -> str:
    """Generate a tailored cover letter in Markdown."""
    system = "You write concise, specific cover letters in plain Markdown. No emojis."
    user = (
        "Write a 250-400 word cover letter for the candidate, tailored to this job, "
        "using only facts from the CV. Plain Markdown.\n\n"
        f"CV:\n{cv_text}\n\nJOB:\n{_job_for_llm(job)}"
    )
    return deepseek_chat(system, user, max_tokens=10000)


def render_markdown_report(
    profile: Dict[str, Any],
    grouped: Dict[str, List[Dict[str, Any]]],
    min_score: int = DEFAULT_MIN_SCORE,
) -> str:
    parts: List[str] = ["# Job Match Report", ""]
    parts.append(f"**Search keywords:** {profile.get('search_keywords', '')}  ")
    parts.append(f"**Experience level:** {profile.get('experience_level', '')}  ")
    parts.append(f"**Minimum match score:** {min_score}/100  ")
    parts.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("")
    if profile.get("summary"):
        parts.append(f"> {profile['summary']}")
        parts.append("")

    total = sum(len(v) for v in grouped.values())

    parts.append("## Quick Apply")
    parts.append("")
    if total == 0:
        parts.append(f"_No jobs scored at or above {min_score}/100 in the last 24 hours._")
        parts.append("")
    else:
        parts.append(f"All {total} positions below scored ≥ {min_score}/100. Click to apply directly.")
        parts.append("")
        parts.append("| Score | Country | Role | Company | Apply |")
        parts.append("|---|---|---|---|---|")
        for country, jobs in grouped.items():
            for j in jobs:
                title = _job_field(j, "job_title", "title") or "Unknown role"
                company = _job_field(j, "company_name", "company") or "Unknown company"
                url = _job_field(j, "source_url", "url", "job_url") or ""
                score = j.get("_match_score", "?")
                link = f"[Open]({url})" if url else "—"
                parts.append(f"| {score} | {country} | {title} | {company} | {link} |")
        parts.append("")

    parts.append("---")
    parts.append("")

    for country, jobs in grouped.items():
        parts.append(f"## {country}")
        parts.append("")
        if not jobs:
            parts.append(f"_No jobs scored at or above {min_score}/100 in the last 24 hours._")
            parts.append("")
            continue
        for i, j in enumerate(jobs, 1):
            title = _job_field(j, "job_title", "title") or "Unknown role"
            company = _job_field(j, "company_name", "company") or "Unknown company"
            location = _job_field(j, "job_location", "location") or country
            url = _job_field(j, "source_url", "url", "job_url") or ""
            score = j.get("_match_score", "?")
            rationale = j.get("_match_rationale", "")
            cover = (j.get("_cover_letter") or "").strip()

            parts.append(f"### {i}. {title} — {company}")
            parts.append(f"- **Location:** {location}")
            parts.append(f"- **Match score:** {score}/100")
            if url:
                parts.append(f"- **Apply:** [{url}]({url})")
            parts.append("")
            if rationale:
                parts.append(f"**Why it fits:** {rationale}")
                parts.append("")
            if cover:
                parts.append("**Cover letter**")
                parts.append("")
                parts.append(cover)
                parts.append("")
        parts.append("")

    return "\n".join(parts)


def markdown_to_pdf(md_text: str, out_path: str) -> None:
    from markdown_pdf import MarkdownPdf, Section

    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(md_text, toc=False))
    pdf.save(out_path)


def run_cv_match(
    cv_pdf_path: str,
    out_dir: str,
    match_id: str,
    countries: Optional[List[str]] = None,
    top_per_country: int = DEFAULT_TOP_PER_COUNTRY,
    jobs_per_country: int = DEFAULT_JOBS_PER_COUNTRY,
    min_score: int = DEFAULT_MIN_SCORE,
) -> Dict[str, Any]:
    """Run the full pipeline. Returns paths to the generated MD/PDF and the profile."""
    countries = countries or DEFAULT_COUNTRIES
    os.makedirs(out_dir, exist_ok=True)

    cv_text = extract_cv_text(cv_pdf_path)
    if not cv_text:
        raise ValueError("CV PDF is empty or unreadable")

    profile = extract_cv_profile(cv_text)
    keywords = profile["search_keywords"]
    experience_level = profile.get("experience_level")

    scraper = LinkedInScraperSync(headless=True)
    db = JobDatabase()
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    try:
        for country in countries:
            print(f"[MATCH] Scraping {country}...")
            max_pages = max(1, (jobs_per_country + 24) // 25)
            try:
                links = scraper.collect_job_links(
                    keywords=keywords,
                    location=country,
                    max_pages=max_pages,
                    experience_levels=None,
                    date_posted="past_24_hours",
                    sort_by="recent",
                )
            except Exception as e:
                msg = str(e)
                print(f"[MATCH] Scrape failed for {country}: {msg}")
                if "LinkedIn login is required" in msg or "login failed" in msg.lower():
                    raise RuntimeError(
                        "LinkedIn rejected the login (likely rate-limit or security challenge). "
                        "Wait several hours, then log into LinkedIn manually in a real browser "
                        "before retrying. Aborting run."
                    ) from e
                links = []

            links = links[:jobs_per_country]
            print(f"[MATCH] {country}: {len(links)} candidate links")

            scored: List[Dict[str, Any]] = []
            for url in links:
                try:
                    job = scraper.get_job_details(url)
                except Exception as e:
                    print(f"[MATCH] Detail fetch failed for {url}: {e}")
                    continue
                if not job:
                    continue
                job["source"] = "linkedin"
                job["source_url"] = url

                desc = (job.get("description") or job.get("job_description") or "").strip()
                if len(desc) < 200 or desc.lower().startswith("no description"):
                    print(f"[MATCH] Skipping {url}: description too short ({len(desc)} chars)")
                    continue

                try:
                    db.add_job(job)
                except Exception:
                    pass

                try:
                    s = score_job(cv_text, job)
                except Exception as e:
                    print(f"[MATCH] Scoring failed for {url}: {e}")
                    continue
                job["_match_score"] = int(s.get("score", 0))
                job["_match_rationale"] = s.get("rationale", "")
                scored.append(job)
                time.sleep(1)

            qualifying = [j for j in scored if j.get("_match_score", 0) >= min_score]
            qualifying.sort(key=lambda j: j.get("_match_score", 0), reverse=True)
            top = qualifying[:top_per_country]
            dropped = len(scored) - len(qualifying)
            print(
                f"[MATCH] {country}: {len(scored)} scored, "
                f"{dropped} below {min_score}, keeping top {len(top)}"
            )
            for j in top:
                try:
                    j["_cover_letter"] = write_cover_letter(cv_text, j)
                except Exception as e:
                    j["_cover_letter"] = f"_(cover letter generation failed: {e})_"
            grouped[country] = top
    finally:
        try:
            scraper.close()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass

    md = render_markdown_report(profile, grouped, min_score=min_score)
    md_path = os.path.join(out_dir, f"{match_id}.md")
    pdf_path = os.path.join(out_dir, f"{match_id}.pdf")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    pdf_ok = True
    try:
        markdown_to_pdf(md, pdf_path)
    except Exception as e:
        print(f"[MATCH] PDF render failed: {e}")
        pdf_ok = False

    return {
        "markdown": md_path,
        "pdf": pdf_path if pdf_ok else None,
        "profile": profile,
        "grouped_counts": {c: len(v) for c, v in grouped.items()},
    }
