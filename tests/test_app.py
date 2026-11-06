"""Streamlit interaction tests; provider calls are mocked, never shown as live output."""
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'app.py'
PROFILE = dict(role='Data analyst', industry='Technology', education='Graduate student', goals='Internship', additional='Python', resume='Python and SQL coursework', job='SQL intern needed')


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_navigation_and_clear(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    app.session_state['profile'] = PROFILE.copy()
    for page in ['Resume Analyzer', 'Career Roadmap', 'Interview Coach', 'Home']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
        assert app.session_state['profile']['resume'] == PROFILE['resume']
    button(app, 'Clear all session data').click().run()
    assert not app.exception
    assert app.session_state['profile'] == {}
    assert not app.session_state['user_api_key']
    assert app.session_state['interview'] is None


def test_missing_resume_disables_analysis():
    app = AppTest.from_file(str(APP)).run()
    app.sidebar.radio[0].set_value('Resume Analyzer').run()
    assert button(app, 'Analyze my resume').disabled


def test_multiple_interview_turns_and_failure(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    question = {'question': 'Explain a SQL join.', 'kind': 'Technical'}
    feedback = {k: 'Test feedback' for k in ['relevance', 'clarity', 'specificity', 'structure', 'completeness', 'conceptual_correctness', 'stronger_response']}
    feedback.update(strengths=['Clear definition'], improvements=['Add an example'])
    from ai_service import CoachError
    with patch('ai_service.generate', return_value=question) as provider:
        app = AppTest.from_file(str(APP)).run()
        app.session_state['user_api_key'] = 'test-only-key'
        app.session_state['profile'] = PROFILE.copy()
        app.sidebar.radio[0].set_value('Interview Coach').run()
        button(app, 'Start practice interview').click().run()
        assert not app.exception
        for _ in range(2):
            app.session_state['calls'] = []
            answer = next(a for a in app.text_area if a.label == 'Your answer')
            answer.set_value('An inner join returns rows matching keys in both tables.')
            provider.side_effect = CoachError('Temporary outage')
            button(app, 'Get feedback').click().run()
            assert app.session_state['interview']['question'] is not None
            assert next(a for a in app.text_area if a.label == 'Your answer').value
            app.session_state['calls'] = []
            provider.side_effect = None
            provider.return_value = feedback
            button(app, 'Get feedback').click().run()
            assert not app.exception
            app.session_state['calls'] = []
            provider.return_value = question
            button(app, 'Next question').click().run()
        assert len(app.session_state['interview']['turns']) == 2


def test_both_analysis_views(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    resume = dict(alignment='Moderate', summary='Relevant coursework.', strengths=[], gaps=[], rewrites=[], appropriate_keywords=['SQL'], priorities=['Document projects'], limitations='Only supplied information was assessed.')
    roadmap = dict(objective='Prepare for analyst internships', basis='Specific job description', relevant_skills=['SQL'], skills_to_develop=[], projects_and_learning=['Build a dashboard'], milestones=[dict(period=p, goal='Practice', actions=['Build and reflect'], deliverable='Portfolio project') for p in ['Days 1–30', 'Days 31–60', 'Days 61–90']], assumptions=['Five hours per week'])
    with patch('ai_service.generate', return_value=resume) as provider:
        app = AppTest.from_file(str(APP)).run()
        app.session_state['user_api_key'] = 'test-only-key'
        app.session_state['profile'] = PROFILE.copy()
        app.sidebar.radio[0].set_value('Resume Analyzer').run()
        button(app, 'Analyze my resume').click().run()
        assert not app.exception
        assert app.session_state['resume_result']['alignment'] == 'Moderate'
        app.session_state['calls'] = []
        provider.return_value = roadmap
        app.sidebar.radio[0].set_value('Career Roadmap').run()
        button(app, 'Create my 90-day roadmap').click().run()
        assert not app.exception
        assert len(app.session_state['roadmap_result']['milestones']) == 3
        app.sidebar.radio[0].set_value('Resume Analyzer').run()
        assert app.session_state['resume_result']['alignment'] == 'Moderate'


def test_key_is_session_only_and_removable(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'owner-key-must-not-be-used')
    app = AppTest.from_file(str(APP)).run()
    assert not app.session_state['user_api_key']
    key_field = next(x for x in app.sidebar.text_input if x.label == 'Your OpenAI API key')
    key_field.set_value('student-test-key').run()
    assert app.session_state['user_api_key'] == 'student-test-key'
    app.sidebar.radio[0].set_value('Career Roadmap').run()
    assert app.session_state['user_api_key'] == 'student-test-key'
    button(app, 'Remove my API key').click().run()
    assert not app.session_state['user_api_key']
    assert not app.exception


def field(app, label):
    return next(x for x in list(app.text_input) + list(app.text_area) if x.label == label)


def test_profile_page_validates_saves_and_persists_drafts():
    app = AppTest.from_file(str(APP)).run()
    app.sidebar.radio[0].set_value('Profile & Documents').run()
    button(app, 'Save profile & documents').click().run()
    assert any('target role' in e.value for e in app.error)
    assert app.session_state['profile'] == {}
    field(app, 'Desired role or career field *').set_value('Data analyst')
    field(app, 'Resume or academic/professional background').set_value('Python and SQL coursework')
    button(app, 'Save profile & documents').click().run()
    assert not app.exception
    assert app.session_state['profile']['role'] == 'Data analyst'
    assert app.session_state['profile']['resume'] == 'Python and SQL coursework'
    assert any('Profile saved' in s.value for s in app.success)
    # Form drafts survive leaving and returning to the page.
    field(app, 'Industry of interest').set_value('Retail').run()
    app.sidebar.radio[0].set_value('Home').run()
    app.sidebar.radio[0].set_value('Profile & Documents').run()
    assert field(app, 'Industry of interest').value == 'Retail'


def test_home_and_tool_buttons_navigate():
    app = AppTest.from_file(str(APP)).run()
    button(app, 'Set up my profile').click().run()
    assert app.session_state['page'] == 'Profile & Documents'
    app.sidebar.radio[0].set_value('Home').run()
    button(app, 'Open Career Roadmap').click().run()
    assert app.session_state['page'] == 'Career Roadmap'
    assert button(app, 'Create my 90-day roadmap').disabled
    button(app, 'Edit profile').click().run()
    assert app.session_state['page'] == 'Profile & Documents'


def test_sample_profile_and_changed_profile_clears_results():
    app = AppTest.from_file(str(APP)).run()
    app.session_state['resume_result'] = dict(alignment='Strong', summary='', strengths=[], gaps=[], rewrites=[],
                                              appropriate_keywords=[], priorities=[], limitations='')
    app.sidebar.radio[0].set_value('Profile & Documents').run()
    button(app, 'Try with sample data').click().run()
    assert app.session_state['field_role'] == 'Data analyst intern'
    assert app.session_state['resume_result'] is not None
    button(app, 'Save profile & documents').click().run()
    assert not app.exception
    assert app.session_state['profile']['role'] == 'Data analyst intern'
    assert app.session_state['profile']['job'].startswith('Data analyst internship')
    assert app.session_state['resume_result'] is None
    app.sidebar.radio[0].set_value('Resume Analyzer').run()
    assert not button(app, 'Analyze my resume').disabled
