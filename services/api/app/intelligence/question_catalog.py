"""Curated synthetic practice prompts; officer approval is still mandatory."""

QUESTIONS = [
    {
        "prompt": "Which SQL clause filters individual rows before grouping?",
        "topic": "SQL",
        "options": ["WHERE", "HAVING", "ORDER BY"],
        "correct": [0],
        "explanation": "WHERE filters rows before GROUP BY; HAVING filters groups.",
    },
    {
        "prompt": "Which SQL join keeps every row from the left table?",
        "topic": "SQL",
        "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN"],
        "correct": [1],
        "explanation": "LEFT JOIN keeps unmatched left rows, supplying NULL for missing right values.",
    },
    {
        "prompt": "Which values are immutable in Python?",
        "topic": "Python",
        "kind": "multiple",
        "options": ["tuple", "list", "str"],
        "correct": [0, 2],
        "explanation": "Tuples and strings are immutable; lists can be modified.",
    },
    {
        "prompt": "What is the output of len([1, 2, 3]) in Python?",
        "topic": "Python",
        "options": ["2", "3", "4"],
        "correct": [1],
        "explanation": "len returns the number of elements, here three.",
    },
    {
        "prompt": "Which C# keyword declares a class?",
        "topic": "C#",
        "options": ["class", "def", "structclass"],
        "correct": [0],
        "explanation": "The class keyword declares a reference type.",
    },
    {
        "prompt": "Which C# type represents a boolean value?",
        "topic": "C#",
        "options": ["bool", "boolean32", "bitstring"],
        "correct": [0],
        "explanation": "bool represents true or false.",
    },
    {
        "prompt": "A quantity rises from 80 to 100. What is the percentage increase?",
        "topic": "Aptitude",
        "options": ["20%", "25%", "80%"],
        "correct": [1],
        "explanation": "The increase is 20; 20/80 × 100 = 25%.",
    },
    {
        "prompt": "Which data structure uses first-in-first-out ordering?",
        "topic": "DSA",
        "options": ["Stack", "Queue", "Set"],
        "correct": [1],
        "explanation": "A queue removes the earliest enqueued item first.",
    },
    {
        "prompt": "Write a function that returns the first non-repeating character. Explain complexity. Test cases: aabbc → c; aabb → none.",
        "topic": "DSA",
        "kind": "code",
        "explanation": "Manual rubric: handles duplicates and empty input; describes time and space complexity. No code is executed.",
    },
    {
        "prompt": "Explain how an index can improve a SQL query and describe a trade-off.",
        "topic": "SQL",
        "kind": "short",
        "explanation": "Manual rubric: explain faster lookup plus storage and write-maintenance costs.",
    },
]
