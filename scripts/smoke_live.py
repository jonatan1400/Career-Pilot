"""Opt-in real API smoke test. Makes 7 billable requests, with no student PII."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from ai_service import generate, UsageLimiter

load_dotenv()
key = os.environ.get('OPENAI_API_KEY', '')
if not key:
    sys.exit('Set OPENAI_API_KEY in your environment or local .env before running this live test.')
profile = {
    'role': 'Data analyst intern', 'industry': 'Retail',
    'education': 'Graduate student in business analytics', 'goals': 'Internship; 5 hours per week',
    'additional': 'I have not learned Tableau yet.',
    'resume': 'Graduate student in business analytics. Built a Python project analyzing retail sales with pandas. Used SQL joins in coursework. Presented findings to classmates.',
    'job': 'Data analyst internship: Python, pandas, SQL joins, Tableau dashboards, and clear communication. Work with retail sales data.'
}
limiter = UsageLimiter(10)
def call(kind, extra=None):
    result = generate(kind, profile, key, os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'), limiter, extra)
    print(kind + ': valid live response')
    return result

analysis = call('resume')
assert analysis['alignment'] in ['Strong', 'Moderate', 'Limited']
roadmap = call('roadmap')
assert len(roadmap['milestones']) == 3
turns = []
for answer in [
    'In my retail sales project I needed to explain trends to classmates. I used a simple chart and explained how I cleaned the data. They understood my approach; I did not collect a formal evaluation.',
    'An inner join returns rows with matching keys in both tables. A left join keeps all rows from the left table and fills missing right-side values with nulls.'
]:
    question = call('question', {'type': 'Mixed', 'previous_questions': [t['question'] for t in turns]})
    feedback = call('feedback', {'question': question, 'answer': answer})
    turns.append(dict(question=question, answer=answer, feedback=feedback))
call('summary', {'completed_turns': turns})
print('Live API smoke test complete. Review real UI outputs separately for coaching quality.')
