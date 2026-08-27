GOLDEN_DATASET = [
    {
        "question": "How many vacation days does an employee accrue annually if they were hired in 2017?",
        "reference_answer": "24 days per year (Legacy PTO, 2 days per month) — 2017 predates the January 2019 cutoff.",
        "correct_chunk_ids": [4],
    },
    {
        "question": "What percentage of base salary is the annual performance bonus, and when is it paid?",
        "reference_answer": "Up to 10% of base salary, paid each March.",
        "correct_chunk_ids": [3],
    },
    {
        "question": "Are part-time employees eligible for the annual bonus?",
        "reference_answer": "No — explicitly excluded, along with contract employees, under any circumstances.",
        "correct_chunk_ids": [3],
    },
    {
        "question": "Can someone on an active Performance Improvement Plan be considered for a mid-year promotion?",
        "reference_answer": "No — excluded from both the bonus and mid-year promotion consideration until the PIP is closed.",
        "correct_chunk_ids": [11],
    },
    {
        "question": "If an employee was hired in 2017 and is currently on an active PIP, how many time-off days do they get this year, and can they expect a bonus?",
        "reference_answer": "24 days per year (legacy PTO), and no bonus while the PIP is active.",
        "correct_chunk_ids": [4, 11],
    },
    {
        "question": "What does FTO stand for, and how many days does it provide compared to the legacy plan?",
        "reference_answer": "Flexible Time Off; 18 days per year (1.5/month) vs. 24 days per year (2/month) under legacy PTO.",
        "correct_chunk_ids": [3, 4],
    },
    {
        "question": "What percentage does Meridian match for 401(k) contributions?",
        "reference_answer": "4%, dollar-for-dollar, up to base salary.",
        "correct_chunk_ids": [7],
    },
    {
        "question": "What does EAP actually stand for?",
        "reference_answer": "Employee Assistance Program.",
        "correct_chunk_ids": [12],
    },
    {
        "question": "When are performance reviews held, and how often should informal check-ins happen?",
        "reference_answer": "Formal reviews annually each October; informal check-ins recommended quarterly.",
        "correct_chunk_ids": [11],
    },
    {
        "question": "Is the Expense Review Committee involved in performance reviews?",
        "reference_answer": "No — these are unrelated, coincidentally sharing the word 'review.' The Expense Review Committee evaluates expenses over $2,000; performance reviews are a separate annual process.",
        "correct_chunk_ids": [10, 11],
    },
    {
        "question": "How many consecutive days can an employee work abroad before needing approval, and who approves longer stays?",
        "reference_answer": "20 consecutive days without extra tax documentation; longer requires prior written approval from both People Operations and Legal.",
        "correct_chunk_ids": [9],
    },
    {
        "question": "In the event of a workplace death, how many bereavement days are affected employees entitled to, and is this automatic?",
        "reference_answer": "10 paid days (extended from the standard 5), and no — not automatic through standard leave systems; People Operations coordinates directly.",
        "correct_chunk_ids": [12, 13],
    },
    {
        "question": "When does the Expense Review Committee meet?",
        "reference_answer": "The first Monday of each month.",
        "correct_chunk_ids": [10],
    },
]