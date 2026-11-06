"""Mocked transport tests exercise real validation; they are not live AI tests."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import httpx
import pytest
from openai import AuthenticationError, RateLimitError, APIConnectionError
from ai_service import generate, UsageLimiter, CoachError, make_context
from models import Question

PROFILE = {'role': 'Data analyst', 'resume': 'Studied SQL and Python.', 'job': 'SQL internship.'}


def run(client):
    with patch('ai_service.OpenAI', return_value=client):
        return generate('question', PROFILE, 'test-only-key', 'gpt-4.1-mini', UsageLimiter(), {'type': 'Technical'})


def client_with_response(parsed, status='completed'):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.parse.return_value = SimpleNamespace(status=status, output_parsed=parsed)
    return client


def test_valid_schema_and_private_request():
    client = client_with_response(Question(question='Explain a SQL join.', kind='Technical'))
    assert run(client)['kind'] == 'Technical'
    args = client.responses.parse.call_args.kwargs
    assert args['store'] is False
    assert 'UNTRUSTED DATA' in args['input'][0]['content']
    assert args['text_format'] is Question


@pytest.mark.parametrize('parsed,status', [(None, 'completed'), (None, 'incomplete'), ({'question': 'x', 'kind': 'invalid'}, 'completed')])
def test_bad_output(parsed, status):
    with pytest.raises(CoachError):
        run(client_with_response(parsed, status))


def test_missing_key_does_not_call_provider():
    with patch('ai_service.OpenAI') as client:
        with pytest.raises(CoachError, match='No API key'):
            generate('question', PROFILE, '', 'gpt-4.1-mini', UsageLimiter(), {'type': 'Technical'})
        client.assert_not_called()


@pytest.mark.parametrize('error,expected', [
    (AuthenticationError('sensitive', response=httpx.Response(401, request=httpx.Request('POST', 'https://api.openai.com')), body=None), 'rejected'),
    (RateLimitError('sensitive', response=httpx.Response(429, request=httpx.Request('POST', 'https://api.openai.com')), body=None), 'allowance'),
    (APIConnectionError(request=httpx.Request('POST', 'https://api.openai.com')), 'could not be reached'),
    (RuntimeError('sensitive private content'), 'could not be completed'),
])
def test_provider_errors_are_safe(error, expected):
    client = client_with_response(None)
    client.responses.parse.side_effect = error
    with pytest.raises(CoachError, match=expected) as exc:
        run(client)
    assert 'sensitive' not in str(exc.value)


def test_profile_grounding():
    context = make_context(PROFILE)
    assert context['resume']['sections'][0]['id'] == 'R1'
    assert context['job_description']['sections'][0]['id'] == 'J1'
