"""CareerPilot AI — run with: streamlit run app.py."""
import copy
import html
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from ai_service import CoachError, UsageLimiter, generate, make_context
from documents import DocumentError, clean_text, extract_text
from formatting import escape_text

load_dotenv()
st.set_page_config(page_title='CareerPilot AI', page_icon='✦', layout='wide', initial_sidebar_state='auto')

HOME, PROFILE, RESUME, ROADMAP, INTERVIEW = 'Home', 'Profile & Documents', 'Resume Analyzer', 'Career Roadmap', 'Interview Coach'
NAV_ICONS = {HOME: ':material/home:', PROFILE: ':material/person:', RESUME: ':material/description:',
             ROADMAP: ':material/route:', INTERVIEW: ':material/forum:'}
TOOLS = (RESUME, ROADMAP, INTERVIEW)
TONES = {'Strong': 'good', 'Moderate': 'warn', 'Limited': 'low',
         'High': 'low', 'Medium': 'warn', 'Low': 'neutral',
         'Not documented': 'info', 'Partially demonstrated': 'warn', 'Student-reported gap': 'low',
         'Behavioral': 'violet', 'Technical': 'info'}
PROFILE_FIELDS = ('role', 'industry', 'education', 'goals', 'additional', 'resume', 'job')
FEEDBACK_DIMENSIONS = ('relevance', 'clarity', 'specificity', 'structure', 'completeness', 'conceptual_correctness')
SAMPLE_PROFILE = dict(
    role='Data analyst intern', industry='Retail',
    education='Graduate student in business analytics',
    goals='Summer internship; about 5 hours of study time per week',
    additional='I have not learned Tableau yet.',
    resume='Graduate student in business analytics. Built a Python project analyzing retail sales with pandas. '
           'Used SQL joins in coursework. Presented findings to classmates.',
    job='Data analyst internship: Python, pandas, SQL joins, Tableau dashboards, and clear communication. '
        'Work with retail sales data.')
BRAND = ('<div class="cp-brand"><div class="cp-logo">✦</div><div><div class="cp-name">CareerPilot</div>'
         '<div class="cp-tag">Your next chapter, with direction</div></div></div>')


# ----------------------------------------------------------------------------- configuration

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


def stylesheet():
    return '<style>' + (Path(__file__).parent / 'styles.css').read_text(encoding='utf-8') + '</style>'


# ----------------------------------------------------------------------------- session state

def initialize():
    defaults = {'profile': {}, 'resume_result': None, 'roadmap_result': None, 'interview': None,
                'calls': [], 'page': HOME, 'upload_epoch': 0, 'notice': None}
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


def reset_results():
    st.session_state.resume_result = None
    st.session_state.roadmap_result = None
    st.session_state.interview = None
    for key in list(st.session_state.keys()):
        if key.startswith('answer_'):
            del st.session_state[key]


def go(page):
    st.session_state.page = page


def load_sample_profile():
    for name in PROFILE_FIELDS:
        st.session_state['field_' + name] = SAMPLE_PROFILE[name]
    st.session_state.notice = ('info', 'Sample data loaded into the form. Review it, then save your profile.', 'form')


def ingest_upload(kind):
    """Extract an uploaded resume/job file in memory and place the text in the matching form field."""
    file = st.session_state.get(f'{kind}_upload_{st.session_state.upload_epoch}')
    if file is None:
        return
    try:
        text = extract_text(file.getvalue(), file.name)
    except DocumentError as exc:
        st.session_state.notice = ('error', str(exc), 'upload')
        return
    st.session_state['field_' + kind] = text
    st.session_state.notice = ('success', f'Extracted {len(text):,} characters from {escape_text(file.name)}. '
                                          'Review the text below, then save your profile.', 'upload')


def show_notice(slot):
    """Show a one-time message queued by a callback or a rerun, in the part of the page it belongs to."""
    notice = st.session_state.get('notice')
    if notice and notice[2] == slot:
        st.session_state.notice = None
        {'success': st.success, 'error': st.error, 'info': st.info}[notice[0]](notice[1])


def readiness(profile):
    return dict(key=bool(st.session_state.get('user_api_key', '').strip()),
                role=bool(profile.get('role')), resume=bool(profile.get('resume')), job=bool(profile.get('job')),
                background=bool(profile.get('resume') or profile.get('education') or profile.get('additional')))


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


# ----------------------------------------------------------------------------- rendering helpers
# Model and document text is untrusted: Markdown output goes through escape_text, HTML output through html.escape.

def prose(text):
    st.markdown(escape_text(text), unsafe_allow_html=False)


def safe(text):
    return html.escape(str(text)).replace('\n', '<br>')


def chip(text, tone=None, big=False):
    tone = tone or TONES.get(text, 'neutral')
    return f'<span class="cp-chip cp-{tone}{" cp-big" if big else ""}">{html.escape(str(text))}</span>'


def chips(items, tone='neutral'):
    st.html('<div class="cp-chips">' + ''.join(chip(item, tone) for item in items) + '</div>')


def listing(items, ordered=False):
    if not items:
        st.caption('Nothing listed.')
        return
    tag = 'ol' if ordered else 'ul'
    st.html(f'<{tag} class="cp-list">' + ''.join(f'<li>{safe(item)}</li>' for item in items) + f'</{tag}>')


def label(text):
    st.html(f'<div class="cp-label">{html.escape(text)}</div>')


def card_title(title, *tags):
    st.html('<div class="cp-cardhead"><span class="cp-cardtitle">' + html.escape(title) + '</span>' + ''.join(tags) + '</div>')


def quote(heading, text, tone=''):
    st.html(f'<div class="cp-quote {tone}"><div class="cp-label">{html.escape(heading)}</div>{safe(text)}</div>')


def page_header(eyebrow, title, subtitle):
    st.html(f'<div class="cp-pagehead"><div class="cp-eyebrow">{html.escape(eyebrow)}</div><h1>{html.escape(title)}</h1>'
            f'<p>{html.escape(subtitle)}</p></div>')


def checklist(items, inline=False):
    rows = ''.join(f'<li class="{"done" if ok else ""}"><span class="cp-dot">{"✓" if ok else ""}</span>'
                   f'<span>{html.escape(text)}</span></li>' for ok, text in items)
    return f'<ul class="cp-check{" inline" if inline else ""}">{rows}</ul>'


def requirements_panel(required, optional=(), note=None):
    """Show which saved inputs a tool will use and offer a shortcut back to the profile."""
    complete = all(ok for ok, _ in required)
    with st.container(border=True):
        left, right = st.columns([4, 1.4], vertical_alignment='center')
        with left:
            label('Ready to go' if complete else 'Before you start')
            st.html(checklist(list(required) + [(ok, text + ' (optional)') for ok, text in optional], inline=True))
            if note:
                st.caption(note)
        with right:
            st.button('Edit profile', key='edit_' + st.session_state.page, on_click=go, args=(PROFILE,),
                      icon=':material/edit:', width='stretch')
    return complete


def show_resume(result):
    with st.container(border=True):
        st.html('<div class="cp-cardhead">' + chip(result['alignment'] + ' alignment', TONES[result['alignment']], big=True)
                + '<span class="cp-muted">Qualitative coaching assessment · not an ATS score or hiring prediction</span></div>')
        prose(result['summary'])
    strengths, gaps, rewrites, keywords = st.tabs([
        f':material/verified: Strengths ({len(result["strengths"])})',
        f':material/flag: Gaps ({len(result["gaps"])})',
        f':material/edit_note: Rewrites ({len(result["rewrites"])})',
        ':material/checklist: Keywords & priorities'])
    with strengths:
        if not result['strengths']:
            st.caption('No documented strengths were matched to this vacancy.')
        for item in result['strengths']:
            with st.container(border=True):
                card_title(item['qualification'])
                left, right = st.columns(2)
                with left:
                    quote('From your resume', item['resume_evidence'])
                with right:
                    quote('From the job posting', item['job_evidence'])
    with gaps:
        st.caption('“Not documented” means the resume does not show it, which is not the same as lacking it.')
        if not result['gaps']:
            st.caption('No gaps were identified.')
        for gap in result['gaps']:
            with st.container(border=True):
                card_title(gap['qualification'], chip(gap['status']))
                prose(gap['explanation'])
                quote('Next step', gap['next_step'], 'cp-next')
    with rewrites:
        st.caption('Suggested wording keeps your facts. Verify every detail before using it.')
        if not result['rewrites']:
            st.caption('No rewrites could be verified against your resume text.')
        for rewrite in result['rewrites']:
            with st.container(border=True):
                left, right = st.columns(2)
                with left:
                    quote('Current', rewrite['original'])
                with right:
                    quote('Suggested', rewrite['suggested'], 'cp-better')
                st.caption(escape_text('Why: ' + rewrite['reason']))
    with keywords:
        left, right = st.columns(2)
        with left:
            label('Keywords to consider where accurate')
            chips(result['appropriate_keywords'])
        with right:
            label('Your next priorities')
            listing(result['priorities'], ordered=True)
    st.info(escape_text(result['limitations']), icon=':material/info:')


def show_roadmap(result):
    with st.container(border=True):
        card_title(result['objective'], chip('Based on: ' + result['basis'], 'info'))
        left, right = st.columns(2)
        with left:
            label('Skills you can build on')
            chips(result['relevant_skills'], 'good')
        with right:
            label('Projects & learning activities')
            listing(result['projects_and_learning'], ordered=True)
    st.subheader('Skills to develop')
    for item in result['skills_to_develop']:
        with st.container(border=True):
            card_title(item['skill'], chip(item['priority'] + ' priority', TONES[item['priority']]))
            prose(item['rationale'])
            quote('Practice', item['activity'])
            st.caption(escape_text('Success measure: ' + item['success_measure']))
    st.subheader('Your 90-day plan')
    for column, milestone in zip(st.columns(3), result['milestones']):
        with column, st.container(border=True):
            st.html(chip(milestone['period'], 'info'))
            card_title(milestone['goal'])
            listing(milestone['actions'])
            quote('Deliverable', milestone['deliverable'], 'cp-next')
    with st.expander('Planning assumptions', icon=':material/tune:'):
        listing(result['assumptions'])


def show_feedback(feedback):
    label('Coach feedback')
    st.html('<div class="cp-grid">' + ''.join(
        f'<div class="cp-dim"><b>{dimension.replace("_", " ")}</b>{safe(feedback[dimension])}</div>'
        for dimension in FEEDBACK_DIMENSIONS) + '</div>')
    left, right = st.columns(2)
    with left:
        label('What worked')
        listing(feedback['strengths'])
    with right:
        label('Try next time')
        listing(feedback['improvements'])
    with st.expander('Example stronger response', icon=':material/lightbulb:'):
        st.caption('Adapt this to your own experience. Bracketed placeholders need your real details.')
        prose(feedback['stronger_response'])


def show_summary(summary):
    st.subheader('Your practice summary')
    with st.container(border=True):
        prose(summary['overview'])
        for column, (heading, items) in zip(st.columns(3), [('Strengths', summary['strengths']),
                                                             ('Areas to develop', summary['recurring_gaps']),
                                                             ('Practice plan', summary['practice_plan'])]):
            with column:
                label(heading)
                listing(items)


# ----------------------------------------------------------------------------- sidebar

initialize()
st.html(stylesheet())

with st.sidebar:
    st.html(BRAND)
    page = st.radio('Navigate', list(NAV_ICONS), format_func=lambda name: f'{NAV_ICONS[name]} {name}',
                    key='page', label_visibility='collapsed')
    st.html('<div class="cp-section">Your session</div>')
    st.text_input('Your OpenAI API key', type='password', key='user_api_key', max_chars=512, placeholder='sk-…',
                  help='Used only in this session. Never saved to a file or shared with other students.')
    if st.session_state.get('user_api_key', '').strip():
        st.button('Remove my API key', on_click=lambda: st.session_state.update(user_api_key=''),
                  icon=':material/key_off:', width='stretch')
    else:
        st.caption('Required for live coaching. Usage is billed to your own OpenAI project.')
    profile = st.session_state.profile
    ready = readiness(profile)
    st.html(checklist([(ready['key'], 'API key added'), (ready['role'], 'Profile saved'),
                       (ready['resume'], 'Resume saved'), (ready['job'], 'Job description saved')]))
    st.button('Clear all session data', on_click=clear_session, icon=':material/delete_sweep:', width='stretch')
    st.caption('Clears your API key, documents, profile, results, and interview history. Anonymous usage limits remain.')
    with st.expander('Privacy & data handling', icon=':material/shield:'):
        st.caption('Your key is sent securely to this app’s server and used only to authenticate requests to OpenAI. '
                   'API usage is billed to your OpenAI project. A ChatGPT subscription does not include API usage.')
        st.caption('Your API key, documents, and answers stay in this active server session and are sent to OpenAI only '
                   'when you request coaching. No application database or document logging is used. OpenAI processing '
                   'and retention policies apply; store=False is requested. Avoid sensitive identifiers. Clear your '
                   'session when finished.')

if page in TOOLS and not ready['key']:
    st.warning('Add your OpenAI API key in the sidebar to enable live coaching. No shared owner key is used.',
               icon=':material/key:')

# ----------------------------------------------------------------------------- pages

if page == HOME:
    page_header('Welcome', 'Build confidence for your next opportunity',
                'CareerPilot turns your experience into a clearer next step: understand your fit for a role, '
                'plan the skills to build, and practice the conversation.')
    left, right = st.columns([3, 2], gap='medium')
    with left:
        with st.container(border=True):
            label('Get started')
            steps = [(ready['key'], 'Add your OpenAI API key', 'In the sidebar. It stays in this session only.'),
                     (ready['role'], 'Save your profile and documents', 'Your target role, background, resume, and a job description.'),
                     (bool(st.session_state.resume_result or st.session_state.roadmap_result or st.session_state.interview),
                      'Choose a tool', 'Each tool reuses the same saved profile.')]
            st.html(''.join(f'<div class="cp-step{" done" if ok else ""}"><div class="cp-stepnum">{"✓" if ok else index}</div>'
                            f'<div><b>{title}</b><span>{detail}</span></div></div>'
                            for index, (ok, title, detail) in enumerate(steps, 1)))
            st.button('Edit my profile' if profile else 'Set up my profile', type='primary', on_click=go, args=(PROFILE,),
                      icon=':material/person:')
    with right:
        with st.container(border=True):
            label('How your data is handled')
            st.caption('Documents are read in memory and kept only in this server session. Nothing is stored in a database '
                       'or log, and your content goes to OpenAI only when you ask for coaching, with store=False requested.')
            st.caption('AI guidance can be imperfect. Review suggestions and verify every resume claim before using it.')
    st.subheader('Choose a tool')
    cards = [
        (RESUME, '01', 'Understand your fit for a vacancy, find evidence gaps, and improve the bullet points you already have.',
         ready['role'] and ready['resume'] and ready['job'], 'Needs a saved resume and job description', st.session_state.resume_result),
        (ROADMAP, '02', 'Build on your current skills with concrete projects and a personalized 30-, 60-, and 90-day plan.',
         ready['role'] and ready['background'], 'Needs a target role and some background', st.session_state.roadmap_result),
        (INTERVIEW, '03', 'Practice one question at a time, get constructive feedback, and refine your answers.',
         True, '', st.session_state.interview)]
    for column, (tool, number, description, usable, requirement, result) in zip(st.columns(3), cards):
        with column, st.container(border=True):
            st.html(f'<div class="cp-toolnum">{number}</div>')
            card_title(tool)
            prose(description)
            if result:
                st.html(chip('Results saved', 'info'))
            elif usable:
                st.html(chip('Ready', 'good'))
            else:
                st.html(chip(requirement, 'neutral'))
            st.button('Open ' + tool, key='open_' + tool, on_click=go, args=(tool,), icon=':material/arrow_forward:', width='stretch')

elif page == PROFILE:
    page_header('Step 1', 'Your profile & documents',
                'Saved once and shared by every tool. Your edits stay in this session until you save or clear it; '
                'saving changed inputs clears previous results and ends the current interview.')
    for name in PROFILE_FIELDS:
        st.session_state.setdefault('field_' + name, profile.get(name, ''))
    if profile:
        st.html('<div class="cp-chips">' + chip('Saved: ' + profile['role'], 'good')
                + chip(f"{len(profile.get('resume', '')):,} resume characters", 'neutral')
                + chip(f"{len(profile.get('job', '')):,} job-description characters", 'neutral') + '</div>')
    with st.container(border=True):
        label('Upload a document (optional)')
        st.caption('Text is extracted in memory and placed in the matching box below for you to review. '
                   'PDF or DOCX · 5 MB · 20 PDF pages maximum. Scanned PDFs need OCR first.')
        left, right = st.columns(2)
        with left:
            st.file_uploader('Resume', type=['pdf', 'docx'], key=f"resume_upload_{st.session_state.upload_epoch}",
                             on_change=ingest_upload, args=('resume',))
        with right:
            st.file_uploader('Job description', type=['pdf', 'docx'], key=f"job_upload_{st.session_state.upload_epoch}",
                             on_change=ingest_upload, args=('job',))
        show_notice('upload')
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.text_input('Desired role or career field *', key='field_role', max_chars=200, persist_state='session',
                          placeholder='e.g. Data analyst intern')
            st.text_input('Current education level / major', key='field_education', max_chars=300, persist_state='session',
                          placeholder='e.g. Junior, Information Systems')
        with right:
            st.text_input('Industry of interest', key='field_industry', max_chars=200, persist_state='session',
                          placeholder='e.g. Healthcare technology')
            st.text_input('Interests, goals, and available study time', key='field_goals', max_chars=1500, persist_state='session',
                          placeholder='e.g. Summer internship; 5 hours per week')
        st.text_area('Additional skills or experience not on your resume', key='field_additional', max_chars=4000,
                     persist_state='session', height=90, placeholder='Coursework, tools, volunteering, or skills you are still learning.')
        st.text_area('Resume or academic/professional background', key='field_resume', height=220, max_chars=40000,
                     persist_state='session', placeholder='Paste your resume text here, or upload a file above.')
        st.text_area('Job or internship description', key='field_job', height=180, max_chars=40000, persist_state='session',
                     placeholder='Optional, but it makes the Resume Analyzer available and every tool more specific.')
        save = st.button('Save profile & documents', type='primary', icon=':material/save:')
    if save:
        values = {name: st.session_state.get('field_' + name, '').strip() for name in PROFILE_FIELDS}
        try:
            if not values['role']:
                raise DocumentError('Enter a target role or career field.')
            if values['resume']:
                values['resume'] = clean_text(values['resume'])
            if values['job']:
                values['job'] = clean_text(values['job'])
            if values != profile:
                st.session_state.profile = values
                reset_results()
            st.session_state.notice = ('success', 'Profile saved. Your information is ready in all three tools.', 'form')
            st.rerun()  # Re-render so the sidebar checklist and saved summary reflect the new profile at once.
        except DocumentError as exc:
            st.error(str(exc))
    show_notice('form')
    st.button('Try with sample data', on_click=load_sample_profile, icon=':material/science:', type='tertiary',
              help='Fills the form with a short fictional student profile so you can try the tools.')
    if profile:
        with st.expander('Review saved text and AI evidence sections', icon=':material/manage_search:'):
            left, right = st.columns(2)
            with left:
                label('Saved resume')
                st.text(profile.get('resume') or 'No resume saved.')
            with right:
                label('Saved job description')
                st.text(profile.get('job') or 'No job description saved.')
            context = make_context(profile)
            if context['resume']['partial'] or context['job_description']['partial']:
                st.warning('Long document: AI uses selected relevant sections. Absence from these excerpts does not '
                           'establish absence from your full document.')
            label('Exactly what the AI receives')
            st.json(context, expanded=False)
        st.button('Continue to the tools', type='primary', on_click=go, args=(RESUME if ready['job'] else ROADMAP,),
                  icon=':material/arrow_forward:')

elif page == RESUME:
    page_header('Tool 01', 'Make your experience easier to see',
                'Compare your saved resume with a specific job description to find evidence, gaps, and better wording.')
    usable = requirements_panel([(ready['role'], 'Target role'), (ready['resume'], 'Resume'), (ready['job'], 'Job description')])
    if st.button('Analyze my resume', type='primary', disabled=not usable, icon=':material/search_insights:'):
        result = call_ai('resume', profile)
        if result:
            st.session_state.resume_result = result
    if st.session_state.resume_result:
        show_resume(st.session_state.resume_result)

elif page == ROADMAP:
    page_header('Tool 02', 'Build the skills for your next step',
                'A personalized 30-, 60-, and 90-day plan that starts from what you already know.')
    note = None if ready['job'] else 'No job description saved: your roadmap will use general role expectations.'
    usable = requirements_panel([(ready['role'], 'Target role'), (ready['background'], 'Resume, education, or additional experience')],
                                [(ready['job'], 'Job description')], note)
    if st.button('Create my 90-day roadmap', type='primary', disabled=not usable, icon=':material/route:'):
        result = call_ai('roadmap', profile)
        if result:
            st.session_state.roadmap_result = result
    if st.session_state.roadmap_result:
        show_roadmap(st.session_state.roadmap_result)

else:
    page_header('Tool 03', 'Practice your next conversation',
                'One question at a time, with constructive feedback after each answer and a summary at the end.')
    interview = st.session_state.interview
    if interview is None:
        left, right = st.columns([3, 2], gap='medium')
        with left, st.container(border=True):
            label('Set up your practice session')
            selected_role = st.text_input('Interview target role', value=profile.get('role', ''), max_chars=200,
                                          placeholder='e.g. Data analyst intern')
            interview_type = st.radio('Question type', ['Behavioral', 'Technical', 'Mixed'], horizontal=True,
                                      help='Mixed alternates behavioral and technical questions, starting with behavioral.')
            question_count = st.select_slider('Number of questions', options=[3, 5, 7], value=3)
            if not ready['job']:
                st.caption('Tip: a saved job description makes the questions more specific to the role.')
            if st.button('Start practice interview', type='primary', disabled=not selected_role.strip(), icon=':material/play_arrow:'):
                snapshot = copy.deepcopy(profile)
                snapshot['role'] = selected_role.strip()
                first = call_ai('question', snapshot, {'type': interview_type, 'previous_questions': []})
                if first:
                    st.session_state.interview = dict(profile=snapshot, type=interview_type, count=question_count,
                                                     turns=[], question=first, ended=False, summary=None)
                    st.rerun()
        with right, st.container(border=True):
            label('How it works')
            listing(['Your coach asks one question at a time, matched to your role and level.',
                     'Answer in your own words. For behavioral questions, the STAR structure helps: situation, task, action, result.',
                     'You get feedback on relevance, clarity, specificity, structure, completeness, and correctness.',
                     'Finish whenever you like to get a summary and a practice plan.'])
    else:
        answered = len(interview['turns'])
        with st.container(border=True):
            st.html('<div class="cp-cardhead"><span class="cp-cardtitle">' + html.escape(interview['profile']['role']) + '</span>'
                    + chip(interview['type'] + ' practice', 'violet' if interview['type'] != 'Technical' else 'info') + '</div>')
            st.progress(answered / interview['count'], text=f"{answered} of {interview['count']} questions answered")
        for index, turn in enumerate(interview['turns']):
            with st.chat_message('assistant', avatar=':material/school:'):
                st.html(f'<div class="cp-cardhead"><span class="cp-qnum">Question {index + 1}</span>{chip(turn["question"]["kind"])}</div>')
                prose(turn['question']['question'])
            with st.chat_message('user'):
                prose(turn['answer'])
            with st.chat_message('assistant', avatar=':material/school:'):
                show_feedback(turn['feedback'])
        if not interview['ended'] and interview['question']:
            with st.chat_message('assistant', avatar=':material/school:'):
                st.html(f'<div class="cp-cardhead"><span class="cp-qnum">Question {answered + 1}</span>{chip(interview["question"]["kind"])}</div>')
                prose(interview['question']['question'])
            with st.form('answer_form', clear_on_submit=False):
                answer = st.text_area('Your answer', max_chars=6000, height=150,
                                      key=f"answer_{answered}_{st.session_state.upload_epoch}",
                                      placeholder='Take your time. Specific examples and outcomes make feedback more useful.')
                submitted = st.form_submit_button('Get feedback', type='primary', icon=':material/rate_review:')
            if submitted:
                if not answer.strip():
                    st.warning('Enter an answer before requesting feedback.')
                else:
                    feedback = call_ai('feedback', interview['profile'], {'question': interview['question'], 'answer': answer.strip()})
                    if feedback:
                        interview['turns'].append(dict(question=interview['question'], answer=answer.strip(), feedback=feedback))
                        interview['question'] = None
                        st.rerun()
        elif not interview['ended'] and answered >= interview['count']:
            st.caption('You have answered every question in this session. Finish to see your summary.')
        with st.container(horizontal=True):
            if not interview['ended'] and not interview['question'] and answered < interview['count']:
                if st.button('Next question', type='primary', icon=':material/arrow_forward:'):
                    question = call_ai('question', interview['profile'],
                                       {'type': interview['type'], 'previous_questions': [t['question'] for t in interview['turns']]})
                    if question:
                        interview['question'] = question
                        st.rerun()
            if not interview['ended'] and interview['turns']:
                if st.button('Finish & summarize practice', icon=':material/summarize:'):
                    result = call_ai('summary', interview['profile'], {'completed_turns': interview['turns']})
                    if result:
                        interview['ended'] = True
                        interview['summary'] = result
                        st.rerun()
            if st.button('Reset interview', type='tertiary', icon=':material/restart_alt:'):
                st.session_state.interview = None
                for key in list(st.session_state.keys()):
                    if key.startswith('answer_'):
                        del st.session_state[key]
                st.rerun()
        if interview['summary']:
            show_summary(interview['summary'])
