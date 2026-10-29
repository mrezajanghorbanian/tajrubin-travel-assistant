"""Bilingual retrieval through the real Markdown loader and QA CLI."""
import json
import subprocess
import sys

import pytest

from app.assistant.demo import main


@pytest.fixture
def bilingual_pack(tmp_path):
    for identifier, city, title, summary in [
        ('fa.museum', 'تهران', 'موزه در تهران', 'راهنمای ساختگی موزه.'),
        ('en.museum', 'Tehran', 'Tehran museum', 'Synthetic museum guide.'),
        ('en.garden', 'Tehran', 'Tehran garden', 'Synthetic garden guide.'),
        ('other.museum', 'Yazd', 'Yazd museum', 'Synthetic other-city guide.'),
    ]:
        metadata = {
            'document_id': identifier, 'country_code': 'IR', 'country_name': 'Iran',
            'city': city, 'category': 'attraction', 'title': title,
            'summary': summary, 'languages': ['fa'] if identifier.startswith('fa.') else ['en'],
            'last_reviewed_at': '2026-10-01',
            'sources': [{'title': 'Synthetic source', 'url': 'https://example.invalid/fixture'}],
        }
        (tmp_path / (identifier + '.md')).write_text(
            '---\n' + json.dumps(metadata, ensure_ascii=False) + '\n---\nSynthetic example only.\n',
            encoding='utf-8',
        )
    return tmp_path


def invoke(pack, query, capsys, *options):
    assert main([
        query, '--knowledge-root', str(pack), '--format', 'json', *options,
    ]) == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(('query', 'city'), [
    ('موزه در تهران', 'تهران'), ('موزه\u200cها در تهران', 'Tehran'),
    ('museum in Tehran', 'تهران'), ('museums in Tehran', 'Tehran'),
])
def test_bilingual_cli_recovers_both_languages_with_provenance(bilingual_pack, capsys, query, city):
    answer = invoke(bilingual_pack, query, capsys, '--city', city, '--country', 'IR', '--bilingual-aliases')
    assert answer['status'] == 'provisional'
    assert answer['needs_verification'] is True
    assert {item['document_id'] for item in answer['evidence']} == {'fa.museum', 'en.museum'}
    for item in answer['evidence']:
        assert item['external_urls'] == ['https://example.invalid/fixture']
        assert item['last_reviewed_at'] == '2026-10-01'
        assert '[' + item['document_id'] + ']' in answer['answer']


@pytest.mark.parametrize(('query', 'options'), [
    ('ساعت بازدید موزه', ['--city', 'تهران']),
    ('museum opening hours', ['--city', 'Tehran']),
    ('موزه باغ', ['--city', 'تهران']),
    ('museum', ['--city', 'Tehrann']),
    ('موزه', ['--city', 'تهران', '--country', 'GB']),
])
def test_bilingual_cli_abstains_without_sufficient_matching_evidence(bilingual_pack, capsys, query, options):
    answer = invoke(bilingual_pack, query, capsys, '--bilingual-aliases', *options)
    assert answer['status'] == 'insufficient_evidence'
    assert answer['evidence'] == []
    assert answer['needs_verification'] is True


def test_bilingual_cli_keeps_default_matching_unchanged(bilingual_pack, capsys):
    answer = invoke(bilingual_pack, 'museum in Tehran', capsys, '--city', 'Tehran')
    assert [item['document_id'] for item in answer['evidence']] == ['en.museum']


def test_bilingual_cli_respects_result_limit(bilingual_pack, capsys):
    answer = invoke(bilingual_pack, 'museum', capsys, '--city', 'تهران', '--bilingual-aliases', '--max-results', '1')
    assert [item['document_id'] for item in answer['evidence']] == ['en.museum']


@pytest.mark.parametrize('city', ['Tehran', 'تهران'])
def test_bilingual_cli_answers_persian_query_from_public_sample(capsys, city):
    assert main(['موزه در تهران', '--city', city, '--country', 'IR', '--bilingual-aliases', '--format', 'json']) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer['status'] == 'provisional'
    assert [item['document_id'] for item in answer['evidence']] == ['ir.tehran.destination']
    assert answer['evidence'][0]['external_urls'] == []
    assert answer['needs_verification'] is True


def test_bilingual_flag_does_not_bypass_request_validation(bilingual_pack, capsys):
    assert main(['موزه', '--knowledge-root', str(bilingual_pack), '--bilingual-aliases', '--max-results', '0']) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'Travel demo input error' in captured.err


def test_bilingual_cli_text_keeps_source_and_verification_notice(bilingual_pack, capsys):
    assert main(['museum', '--knowledge-root', str(bilingual_pack), '--city', 'تهران', '--bilingual-aliases']) == 0
    output = capsys.readouterr().out
    assert '[en.museum]' in output
    assert '[fa.museum]' in output
    assert 'Status: provisional' in output
    assert 'Live prices, opening hours and availability are not verified.' in output


def test_bilingual_cli_runs_as_a_module(bilingual_pack):
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', '-m', 'app.assistant.demo', 'موزه در تهران',
         '--knowledge-root', str(bilingual_pack), '--city', 'تهران', '--country', 'IR',
         '--bilingual-aliases', '--format', 'json'],
        check=True, capture_output=True, encoding='utf-8',
    )
    answer = json.loads(result.stdout)
    assert {item['document_id'] for item in answer['evidence']} == {'fa.museum', 'en.museum'}
    assert answer['status'] == 'provisional'
    assert answer['needs_verification'] is True
