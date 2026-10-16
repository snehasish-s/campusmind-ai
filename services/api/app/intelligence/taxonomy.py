"""Versioned controlled taxonomy. Mention detection indicates claims, never proficiency."""

import re

TAXONOMY_VERSION = "2026-10-v1"
SKILLS = {
    "Python": {
        "aliases": ["python", "python3"],
        "prerequisites": ["Programming fundamentals"],
        "resource": "https://docs.python.org/3/tutorial/",
        "title": "Python tutorial",
    },
    "SQL": {
        "aliases": ["sql", "structured query language"],
        "prerequisites": ["Database fundamentals"],
        "resource": "https://www.postgresql.org/docs/current/tutorial.html",
        "title": "PostgreSQL SQL tutorial",
    },
    "SQL Server": {
        "aliases": ["sql server", "mssql", "t-sql", "transact-sql"],
        "prerequisites": ["SQL"],
        "resource": "https://learn.microsoft.com/en-us/sql/t-sql/tutorial-writing-transact-sql-statements",
        "title": "Transact-SQL tutorial",
    },
    "C#": {
        "aliases": ["c#", "c sharp", "csharp"],
        "prerequisites": ["Programming fundamentals"],
        "resource": "https://learn.microsoft.com/en-us/dotnet/csharp/tour-of-csharp/",
        "title": "Tour of C#",
    },
    ".NET": {
        "aliases": [".net", "dotnet", "asp.net", "asp.net core"],
        "prerequisites": ["C#"],
        "resource": "https://learn.microsoft.com/en-us/dotnet/core/introduction",
        "title": ".NET introduction",
    },
    "Java": {
        "aliases": ["java"],
        "prerequisites": ["Programming fundamentals"],
        "resource": "https://dev.java/learn/",
        "title": "Learn Java",
    },
    "JavaScript": {
        "aliases": ["javascript", "ecmascript"],
        "prerequisites": ["Programming fundamentals"],
        "resource": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
        "title": "MDN JavaScript guide",
    },
    "TypeScript": {
        "aliases": ["typescript"],
        "prerequisites": ["JavaScript"],
        "resource": "https://www.typescriptlang.org/docs/handbook/intro.html",
        "title": "TypeScript handbook",
    },
    "React": {
        "aliases": ["react", "reactjs", "react.js"],
        "prerequisites": ["JavaScript"],
        "resource": "https://react.dev/learn",
        "title": "Learn React",
    },
    "DSA": {
        "aliases": ["dsa", "data structures", "algorithms"],
        "prerequisites": ["Programming fundamentals"],
        "resource": "https://opendsa-server.cs.vt.edu/",
        "title": "OpenDSA learning materials",
    },
    "Git": {"aliases": ["git", "version control"], "prerequisites": [], "resource": "https://git-scm.com/book/en/v2", "title": "Pro Git"},
    "Programming fundamentals": {
        "aliases": ["programming fundamentals", "programming basics"],
        "prerequisites": [],
        "resource": "https://cs50.harvard.edu/x/",
        "title": "CS50 OpenCourseWare",
    },
    "Database fundamentals": {
        "aliases": ["database fundamentals", "dbms", "relational database"],
        "prerequisites": [],
        "resource": "https://www.postgresql.org/docs/current/tutorial-concepts.html",
        "title": "Relational database concepts",
    },
    "Aptitude": {
        "aliases": ["aptitude", "quantitative reasoning"],
        "prerequisites": [],
        "resource": "https://www.khanacademy.org/math",
        "title": "Khan Academy mathematics",
    },
}


def normalize(value):
    text = value.strip().casefold()
    for canonical, info in SKILLS.items():
        if text == canonical.casefold() or text in info["aliases"]:
            return canonical
    return None


def claimed_skills(text):
    results = []
    for name, info in SKILLS.items():
        for alias in sorted(info["aliases"], key=len, reverse=True):
            match = re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", text, flags=re.I)
            if not match:
                continue
            start, end = max(0, text.rfind("\n", 0, match.start()) + 1), text.find("\n", match.end())
            end = len(text) if end < 0 else end
            quote = text[start:end][:600].strip()
            negated = bool(re.search(r"\b(no|not|never|without|learning|beginner|aspiring)\b", quote, re.I))
            results.append(
                {
                    "skill": name,
                    "quote": quote,
                    "confidence": 0.55 if negated else 0.85,
                    "ambiguous": negated,
                    "evidence_type": "resume_claim",
                    "explanation": "Exact taxonomy mention; proficiency is not established.",
                }
            )
            break
    return results


def resources():
    return [
        {
            "skill": name,
            "title": info["title"],
            "url": info["resource"],
            "prerequisites": info["prerequisites"],
            "cost": "Free learning content; optional certificates may cost extra",
            "catalog_version": TAXONOMY_VERSION,
        }
        for name, info in SKILLS.items()
    ]
