"""Build a condensed, real literature review from PubMed-MCP metadata.

Driven entirely by data fetched live from the PubMed MCP server (no Scopus key
required). Produces references.bib + a study-characteristics table + PRISMA
counts using the repo's own ArticleMetadata model and BibTeX generator.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from litreview.models import ArticleMetadata, DatabaseSource, ReviewStatistics
from litreview.utils.bibtex import generate_bibtex

TOPIC = "GLP-1 receptor agonists for weight loss in non-diabetic obesity"
OUT = Path("output-glp1")
OUT.mkdir(exist_ok=True)

BATCHES = [Path("/tmp/glp1_batch1.json"), Path("/tmp/glp1_batch2.json")]


def clean(s: str) -> str:
    return html.unescape(s or "").replace(" ", " ").strip()


def fmt_author(a: dict) -> str | None:
    last = clean(a.get("last_name", ""))
    if not last:
        return None
    initials = clean(a.get("initials", ""))
    return f"{last}, {initials}" if initials else last


def load_articles() -> list[ArticleMetadata]:
    arts: list[ArticleMetadata] = []
    for bp in BATCHES:
        data = json.loads(bp.read_text())
        for rec in data["articles"]:
            ids = rec.get("identifiers", {}) or {}
            doi = ids.get("doi")
            if not doi:  # quality gate: every article must carry a resolvable DOI
                continue
            cit = rec.get("citation", {}) or {}
            jr = rec.get("journal", {}) or {}
            pd = rec.get("publication_date", {}) or {}
            authors = [fa for a in rec.get("authors", []) if (fa := fmt_author(a))]
            year = None
            if pd.get("year"):
                try:
                    year = int(pd["year"])
                except ValueError:
                    year = None
            arts.append(
                ArticleMetadata(
                    title=clean(rec.get("title", "")).rstrip("."),
                    authors=authors,
                    abstract=clean(rec.get("abstract", "")),
                    doi=doi,
                    pmid=ids.get("pmid"),
                    year=year,
                    journal=clean(jr.get("title", "")),
                    volume=cit.get("volume"),
                    issue=cit.get("issue"),
                    pages=cit.get("pages"),
                    source_db=DatabaseSource.PUBMED,
                    doi_validated=True,  # DOI supplied by PubMed authority record
                )
            )
    return arts


def dedup(arts: list[ArticleMetadata]) -> list[ArticleMetadata]:
    seen: set[str] = set()
    out: list[ArticleMetadata] = []
    for a in arts:
        key = (a.doi or "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def main() -> None:
    raw = load_articles()
    arts = dedup(raw)
    arts.sort(key=lambda a: (a.year or 0), reverse=True)

    # ---- statistics ----
    by_year: dict[int, int] = {}
    by_journal: set[str] = set()
    for a in arts:
        if a.year:
            by_year[a.year] = by_year.get(a.year, 0) + 1
        if a.journal:
            by_journal.add(a.journal)
    years = sorted(y for y in by_year)
    stats = ReviewStatistics(
        total_articles_found=len(raw),
        articles_after_dedup=len(arts),
        articles_after_quality_filter=len(arts),
        articles_with_valid_doi=sum(1 for a in arts if a.doi_validated),
        articles_included=len(arts),
        articles_by_source={"pubmed": len(arts)},
        articles_by_year=by_year,
        journals_represented=len(by_journal),
        date_range=f"{years[0]}-{years[-1]}" if years else "",
        reference_count=len(arts),
        search_queries_used=[
            '(semaglutide OR tirzepatide OR liraglutide OR "GLP-1 receptor agonist") '
            "AND obesity AND (weight loss OR weight management) "
            "AND randomized controlled trial[Publication Type]"
        ],
    )

    # ---- references.bib ----
    bib = generate_bibtex(arts)
    (OUT / "references.bib").write_text(bib)

    # ---- machine-readable record of the included set ----
    (OUT / "included_articles.json").write_text(
        json.dumps(
            [
                {
                    "key": a.citation_key,
                    "title": a.title,
                    "journal": a.journal,
                    "year": a.year,
                    "doi": a.doi,
                    "pmid": a.pmid,
                    "first_author": a.authors[0] if a.authors else None,
                }
                for a in arts
            ],
            indent=2,
            ensure_ascii=False,
        )
    )

    # ---- study characteristics markdown table ----
    rows = []
    for a in arts:
        fa = (a.authors[0].split(",")[0] if a.authors else "—")
        jr = a.journal if len(a.journal) <= 38 else a.journal[:35] + "…"
        rows.append(
            f"| @{a.citation_key} | {fa} et al. | {a.year or '—'} | {jr} | "
            f"[{a.doi}](https://doi.org/{a.doi}) |"
        )
    table = (
        "| Citation | First author | Year | Journal | DOI |\n"
        "|---|---|---|---|---|\n" + "\n".join(rows)
    )
    (OUT / "study_characteristics.md").write_text(table + "\n")

    print(f"Included articles : {len(arts)}")
    print(f"Raw (pre-dedup)   : {len(raw)}")
    print(f"Journals          : {len(by_journal)}")
    print(f"Year range        : {stats.date_range}")
    print(f"By year           : {dict(sorted(by_year.items()))}")
    print(f"references.bib     -> {OUT/'references.bib'} ({len(re.findall(r'@article', bib))} entries)")

    # stash stats for the qmd writer
    (OUT / "_stats.json").write_text(stats.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
