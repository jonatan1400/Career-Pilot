"""CareerPilot AI — run with: streamlit run app.py."""
import copy
import os
from formatting import escape_text
import time
import streamlit as st
from dotenv import load_dotenv
from ai_service import CoachError, UsageLimiter, generate, make_context
from documents import DocumentError, clean_text, extract_text

load_dotenv()
st.set_page_config(page_title='CareerPilot AI', page_icon='✦', layout='wide')


def setting(name, default=''):
    if os.environ.get(name):
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


def positive_integer(name, default):
    try:
        return max(1, int(setting(name, str(default))))
    except (ValueError, TypeError):
        return default


@st.cache_resource
def shared_limiter(limit):
    return UsageLimiter(limit)


def initialize():
    defaults = {'profile': {}, 'resume_result': None, 'roadmap_result': None,
                'interview': None, 'calls': [], 'page': 'Home', 'upload_epoch': 0}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session():
    # Preserve only anonymous rate-limit timestamps; remove all student content/widgets.
    calls = st.session_state.get('calls', [])
    epoch = st.session_state.get('upload_epoch', 0) + 1
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state['calls'] = calls
    st.session_state['upload_epoch'] = epoch


def call_ai(kind, profile, extra=None):
    if not st.session_state.get('user_api_key', '').strip():
        st.error('Enter your OpenAI API key in the sidebar to use live coaching.')
        return None
    now = time.monotonic()
    calls = [t for t in st.session_state.calls if now - t < 3600]
    st.session_state.calls = calls
    if len(calls) >= positive_integer('SESSION_HOURLY_LIMIT', 25):
        st.warning('You have reached the hourly practice limit. Please return later.')
        return None
    if calls and now - calls[-1] < 3:
        st.warning('Please wait a few seconds before your next AI request.')
        return None
    calls.append(now)
    try:
        with st.spinner('Your coach is working…'):
            return generate(kind, profile, st.session_state.user_api_key.strip(), setting('OPENAI_MODEL', 'gpt-4.1-mini'),
                            shared_limiter(positive_integer('GLOBAL_HOURLY_LIMIT', 100)), extra)
    except CoachError as exc:
        st.error(str(exc))
        return None


def prose(text):
    # Render document/model text without allowing Markdown links or remote images.
    st.markdown(escape_text(text), unsafe_allow_html=False)


def bullets(items):
    for item in items:
        prose('• ' + item)


def show_resume(result):
    st.subheader(result['alignment'] + ' alignment')
    prose(result['summary'])
    st.caption('Qualitative coaching assessment. This is not an ATS score or hiring prediction.')
    st.subheader('Your demonstrated strengths')
    for item in result['strengths']:
        with st.container(border=True):
            prose(item['qualification'])
            st.caption('Resume evidence')
            prose(item['resume_evidence'])
            st.caption('Job evidence')
            prose(item['job_evidence'])
    st.subheader('Missing or underrepresented qualifications')
    for gap in result['gaps']:
        with st.container(border=True):
            prose(gap['qualification'] + ' · ' + gap['status'])
            prose(gap['explanation'])
            prose('Next step: ' + gap['next_step'])
    st.subheader('Improve your bullet points')
    for rewrite in result['rewrites']:
        with st.container(border=True):
            st.caption('CURRENT')
            prose(rewrite['original'])
            st.caption('SUGGESTED — verify every detail before using')
            prose(rewrite['suggested'])
            st.caption(escape_text(rewrite['reason']))
    st.subheader('Keywords to consider where accurate')
    bullets(result['appropriate_keywords'])
    st.subheader('Your next priorities')
    bullets(result['priorities'])
    st.info(escape_text(result['limitations']))


def show_roadmap(result):
    st.subheader(escape_text(result['objective']))
    st.caption('Assessment basis: ' + result['basis'])
    st.subheader('Skills you can build on')
    bullets(result['relevant_skills'])
    st.subheader('Skills to develop')
    for item in result['skills_to_develop']:
        with st.container(border=True):
            prose(item['priority'] + ' priority · ' + item['skill'])
            prose(item['rationale'])
            prose('Practice: ' + item['activity'])
            st.caption(escape_text('Success measure: ' + item['success_measure']))
    st.subheader('Projects & learning activities')
    bullets(result['projects_and_learning'])
    st.subheader('Your 90-day plan')
    for milestone in result['milestones']:
        with st.container(border=True):
            st.caption(milestone['period'])
            prose(milestone['goal'])
            bullets(milestone['actions'])
            prose('Deliverable: ' + milestone['deliverable'])
    with st.expander('Planning assumptions'):
        bullets(result['assumptions'])


def show_feedback(feedback):
    st.caption('COACH FEEDBACK')
    for dimension in ('relevance', 'clarity', 'specificity', 'structure', 'completeness', 'conceptual_correctness'):
        prose(dimension.replace('_', ' ').capitalize() + ': ' + feedback[dimension])
    prose('What worked')
    bullets(feedback['strengths'])
    prose('Try next time')
    bullets(feedback['improvements'])
    with st.expander('Example stronger response'):
        st.caption('Adapt this to your own experience. Bracketed placeholders need your real details.')
        prose(feedback['stronger_response'])


initialize()
st.markdown('''<style>
.stApp {background: #f6f8fc;}
.block-container {max-width: 1120px; padding-top: 2rem;}
h1,h2,h3 {color: #142d4e; letter-spacing: -.025em;}
[data-testid="stSidebar"] {background: #eaf0f8;}
[data-testid="stMetric"] {background:white; border:1px solid #dce5ef; padding:1rem; border-radius:12px;}
.stButton button[kind="primary"] {background:#2159b5; border:0;}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.title('✦ CareerPilot')
    st.caption('YOUR NEXT CHAPTER, WITH DIRECTION')
    page = st.radio('Career tools', ['Home', 'Resume Analyzer', 'Career Roadmap', 'Interview Coach'], key='page')
    st.divider()
    st.text_input('Your OpenAI API key', type='password', key='user_api_key', max_chars=512,
                  help='Used only in this session. Never saved to a file or shared with other students.')
    st.caption('Your key is sent securely to this app’s server and used to authenticate requests to OpenAI. API usage is billed to your OpenAI project. A ChatGPT subscription does not include API usage.')
    st.button('Remove my API key', on_click=lambda: st.session_state.update(user_api_key=''))
    st.divider()
    prose('Profile ready' if st.session_state.profile else 'Start with your profile')
    st.caption('Your saved inputs follow you across all three tools during this session.')
    st.button('Clear all session data', on_click=clear_session, use_container_width=True)
    st.caption('Clears your API key, documents, profile, results, and interview history. Anonymous usage limits remain.')

st.title('CareerPilot AI')
prose('Turn your experience into a clearer next step.')
if not st.session_state.get('user_api_key', '').strip():
    st.info('Enter your own OpenAI API key in the sidebar to enable live coaching. No shared owner key is used.')
st.caption('Privacy: your API key, documents, and answers stay in this active server session and are sent to OpenAI only when you request coaching. No application database or document logging is used. OpenAI processing and retention policies apply; store=False is requested. Avoid sensitive identifiers. Clear your session when finished.')

profile = st.session_state.profile
with st.expander('Student profile & documents — shared across every tool', expanded=not bool(profile) or page == 'Home'):
    st.caption('Save changes before using a tool. Saving changed inputs clears previous results and ends the current interview.')
    with st.form('profile_form'):
        col1, col2 = st.columns(2)
        with col1:
            role = st.text_input('Desired role or career field *', value=profile.get('role', ''), max_chars=200)
            industry = st.text_input('Industry of interest', value=profile.get('industry', ''), max_chars=200)
        with col2:
            education = st.text_input('Current education level / major', value=profile.get('education', ''), max_chars=300)
            goals = st.text_input('Interests, goals, and available study time', value=profile.get('goals', ''), max_chars=1500)
        additional = st.text_area('Additional skills or experience not on your resume', value=profile.get('additional', ''), max_chars=4000)
        resume_mode = st.radio('Resume source', ['Use/edit text below', 'Replace with uploaded file'], horizontal=True)
        resume_file = st.file_uploader('Resume PDF or DOCX · 5 MB / 20 PDF pages maximum', type=['pdf', 'docx'], key=f'resume_upload_{st.session_state.upload_epoch}')
        resume = st.text_area('Resume or academic/professional background', value=profile.get('resume', ''), height=170, max_chars=40000)
        job_mode = st.radio('Job description source', ['Use/edit job text below', 'Replace with uploaded job file'], horizontal=True)
        job_file = st.file_uploader('Optional job description PDF or DOCX', type=['pdf', 'docx'], key=f'job_upload_{st.session_state.upload_epoch}')
        job = st.text_area('Job or internship description', value=profile.get('job', ''), height=140, max_chars=40000)
        save = st.form_submit_button('Save profile & documents', type='primary')
    if save:
        try:
            if not role.strip():
                raise DocumentError('Enter a target role or career field.')
            if resume_mode == 'Replace with uploaded file':
                if resume_file is None:
                    raise DocumentError('Upload a resume or choose the text option.')
                resume = extract_text(resume_file.getvalue(), resume_file.name)
            if job_mode == 'Replace with uploaded job file':
                if job_file is None:
                    raise DocumentError('Upload a job description or choose the text option.')
                job = extract_text(job_file.getvalue(), job_file.name)
            if resume.strip():
                resume = clean_text(resume)
            if job.strip():
                job = clean_text(job)
            updated = dict(role=role.strip(), industry=industry.strip(), education=education.strip(),
                           goals=goals.strip(), additional=additional.strip(), resume=resume.strip(), job=job.strip())
            if updated != profile:
                st.session_state.profile = updated
                st.session_state.resume_result = None
                st.session_state.roadmap_result = None
                st.session_state.interview = None
                for key in list(st.session_state.keys()):
                    if key.startswith('answer_'):
                        del st.session_state[key]
            st.success('Profile saved. Your information is ready in all three tools.')
            profile = st.session_state.profile
        except DocumentError as exc:
            st.error(str(exc))
    if profile:
        st.caption(f"Saved: {len(profile.get('resume', '')):,} resume characters · {len(profile.get('job', '')):,} job-description characters")
        with st.expander('Review saved text and AI evidence sections'):
            st.text(profile.get('resume', 'No resume saved.'))
            st.text(profile.get('job', 'No job description saved.'))
            context = make_context(profile)
            if context['resume']['partial'] or context['job_description']['partial']:
                st.warning('Long document: AI uses selected relevant sections. Absence from these excerpts does not establish absence from your full document.')
            st.json(context, expanded=False)

if page == 'Home':
    st.header('Build confidence for your next opportunity')
    prose('Save your background above, then choose a tool from the sidebar. A job description makes your coaching more specific.')
    for title, description in [
        ('01 · Resume Analyzer', 'Understand your fit for a vacancy, find evidence gaps, and improve the bullet points you already have.'),
        ('02 · Career Roadmap', 'Build on your current skills with concrete projects and a personalized 30-, 60-, and 90-day plan.'),
        ('03 · Interview Coach', 'Practice one question at a time, get constructive feedback, and refine your answers.')]:
        with st.container(border=True):
            st.subheader(title)
            prose(description)
    st.caption('AI guidance can be imperfect. Review suggestions and verify every resume claim before using it.')
elif page == 'Resume Analyzer':
    st.header('Make your experience easier to see')
    prose('Compare your saved resume with a specific job description.')
    ready = bool(profile.get('resume') and profile.get('job') and profile.get('role'))
    if not ready:
        st.info('Save a resume, a target role, and a job description above to begin.')
    if st.button('Analyze my resume', type='primary', disabled=not ready):
        result = call_ai('resume', profile)
        if result:
            st.session_state.resume_result = result
    if st.session_state.resume_result:
        show_resume(st.session_state.resume_result)
elif page == 'Career Roadmap':
    st.header('Build the skills for your next step')
    ready = bool(profile.get('role') and (profile.get('resume') or profile.get('additional') or profile.get('education')))
    if not ready:
        st.info('Save your target role and some background: a resume, education, or additional experience.')
    elif not profile.get('job'):
        st.info('No job description saved. Your roadmap will use general role expectations.')
    if st.button('Create my 90-day roadmap', type='primary', disabled=not ready):
        result = call_ai('roadmap', profile)
        if result:
            st.session_state.roadmap_result = result
    if st.session_state.roadmap_result:
        show_roadmap(st.session_state.roadmap_result)
else:
    st.header('Practice your next conversation')
    interview = st.session_state.interview
    if interview is None:
        selected_role = st.text_input('Interview target role', value=profile.get('role', ''), max_chars=200)
        interview_type = st.selectbox('Question type', ['Behavioral', 'Technical', 'Mixed'])
        question_count = st.select_slider('Number of questions', options=[3, 5, 7], value=3)
        if st.button('Start practice interview', type='primary', disabled=not selected_role.strip()):
            snapshot = copy.deepcopy(profile)
            snapshot['role'] = selected_role.strip()
            first = call_ai('question', snapshot, {'type': interview_type, 'previous_questions': []})
            if first:
                st.session_state.interview = dict(profile=snapshot, type=interview_type, count=question_count,
                                                 turns=[], question=first, ended=False, summary=None)
                st.rerun()
    else:
        st.caption(escape_text(interview['profile']['role'] + ' · ' + interview['type'] + ' practice'))
        st.progress(len(interview['turns']) / interview['count'])
        for index, turn in enumerate(interview['turns']):
            with st.chat_message('assistant', avatar='✦'):
                prose(f"Question {index + 1} · {turn['question']['kind']}")
                prose(turn['question']['question'])
            with st.chat_message('user'):
                prose(turn['answer'])
            with st.chat_message('assistant', avatar='✦'):
                show_feedback(turn['feedback'])
        if not interview['ended'] and interview['question']:
            with st.chat_message('assistant', avatar='✦'):
                prose(f"Question {len(interview['turns']) + 1} · {interview['question']['kind']}")
                prose(interview['question']['question'])
            with st.form('answer_form', clear_on_submit=False):
                answer = st.text_area('Your answer', max_chars=6000, height=150, key=f"answer_{len(interview['turns'])}_{st.session_state.upload_epoch}")
                submitted = st.form_submit_button('Get feedback', type='primary')
            if submitted:
                if not answer.strip():
                    st.warning('Enter an answer before requesting feedback.')
                else:
                    feedback = call_ai('feedback', interview['profile'], {'question': interview['question'], 'answer': answer.strip()})
                    if feedback:
                        interview['turns'].append(dict(question=interview['question'], answer=answer.strip(), feedback=feedback))
                        interview['question'] = None
                        st.rerun()
        elif not interview['ended'] and len(interview['turns']) < interview['count']:
            if st.button('Next question', type='primary'):
                question = call_ai('question', interview['profile'], {'type': interview['type'], 'previous_questions': [t['question'] for t in interview['turns']]})
                if question:
                    interview['question'] = question
                    st.rerun()
        if not interview['ended'] and interview['turns']:
            if st.button('Finish & summarize practice'):
                result = call_ai('summary', interview['profile'], {'completed_turns': interview['turns']})
                if result:
                    interview['ended'] = True
                    interview['summary'] = result
                    st.rerun()
        if interview['summary']:
            summary = interview['summary']
            st.subheader('Your practice summary')
            prose(summary['overview'])
            prose('Strengths')
            bullets(summary['strengths'])
            prose('Areas to develop')
            bullets(summary['recurring_gaps'])
            prose('Practice plan')
            bullets(summary['practice_plan'])
        if st.button('Reset interview'):
            st.session_state.interview = None
            for key in list(st.session_state.keys()):
                if key.startswith('answer_'):
                    del st.session_state[key]
            st.rerun()
