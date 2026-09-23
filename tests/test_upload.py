import json
import typing as t
from pathlib import Path

import pytest
from click.testing import CliRunner

import ts_obom
import ts_obom.cli.scan  # noqa: F401  registers the scan command, as start() does
import ts_obom.cli.upload  # noqa: F401  registers the upload command
from ts_obom.api import TrustSourceAPI
from ts_obom.cli import cli

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def obom_document(tmp_path):
    out = tmp_path / 'obom.cdx.json'
    runner = CliRunner()
    runner.invoke(cli, ['--config', str(tmp_path / 'config'), 'scan', '-f', 'cyclonedx',
                        '-o', str(out), str(FIXTURES / 'cloudformation')],
                  catch_exceptions=False)
    return out


def _upload(tmp_path, path, *args):
    runner = CliRunner()
    return runner.invoke(cli, ['--config', str(tmp_path / 'config'), 'upload',
                               '--api-key', 'test-key', '--project-name', 'Orderdesk',
                               *args, str(path)],
                         catch_exceptions=False)


class _Recorder:
    """Stands in for TrustSourceAPI.import_obom and remembers the call."""

    params: t.Optional[dict]

    def __init__(self, response=None, error=None):
        self.response = response or {'ok': True, 'id': 'x1', 'scope': 'project',
                                     'projectId': 'p1'}
        self.error = error
        self.params = None
        self.path = None

    def __call__(self, obom_path, params):
        self.path = obom_path
        self.params = params
        if self.error:
            raise self.error
        return self.response


def test_upload_sends_scope_and_provenance_as_query_params(tmp_path, obom_document, monkeypatch):
    recorder = _Recorder({'ok': True, 'id': 'x1', 'scope': 'module',
                          'projectId': 'p1', 'moduleId': 'm1'})
    monkeypatch.setattr(TrustSourceAPI, 'import_obom', recorder)

    result = _upload(tmp_path, obom_document, '--module-name', 'backend')

    assert result.exit_code == 0, result.output
    assert recorder.params == {
        'moduleName': 'backend',
        'projectName': 'Orderdesk',
        'toolName': 'ts-obom',
        'toolVersion': ts_obom.__version__,
    }
    assert 'm1' in result.output


def test_upload_without_a_module_is_project_scope(tmp_path, obom_document, monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(TrustSourceAPI, 'import_obom', recorder)

    result = _upload(tmp_path, obom_document)

    assert result.exit_code == 0, result.output
    assert recorder.params is not None and 'moduleName' not in recorder.params
    assert 'project scope' in result.output


def test_upload_rejects_the_native_format_before_sending(tmp_path, monkeypatch):
    """The ts-scan trap: scanning in one format and transferring in the other.
    It has to fail locally, naming the flag that fixes it."""
    monkeypatch.setattr(TrustSourceAPI, 'import_obom',
                        _Recorder(error=AssertionError('must not be called')))

    native = tmp_path / 'obom.json'
    runner = CliRunner()
    runner.invoke(cli, ['--config', str(tmp_path / 'config'), 'scan', '-o', str(native),
                        str(FIXTURES / 'cloudformation')], catch_exceptions=False)

    result = _upload(tmp_path, native)

    assert result.exit_code == 2
    assert '-f cyclonedx' in result.output


def test_upload_rejects_a_bom_without_the_marker(tmp_path, obom_document, monkeypatch):
    monkeypatch.setattr(TrustSourceAPI, 'import_obom',
                        _Recorder(error=AssertionError('must not be called')))

    document = json.loads(obom_document.read_text())
    document['metadata']['properties'] = []
    unmarked = tmp_path / 'unmarked.json'
    unmarked.write_text(json.dumps(document))

    result = _upload(tmp_path, unmarked)

    assert result.exit_code == 2
    assert 'trustsource:bomType' in result.output


def test_upload_surfaces_the_platforms_own_rejection(tmp_path, obom_document, monkeypatch):
    error = TrustSourceAPI.Error(json.dumps({
        'error': 'Bad Request', 'description': 'Invalid properties',
        'messages': ['obom.specVersion is required'],
    }), status_code=400)
    monkeypatch.setattr(TrustSourceAPI, 'import_obom', _Recorder(error=error))

    result = _upload(tmp_path, obom_document)

    assert result.exit_code == 1
    assert 'Invalid properties' in result.output
    assert 'obom.specVersion is required' in result.output


def test_error_explains_a_missing_feature_licence(tmp_path, obom_document, monkeypatch):
    error = TrustSourceAPI.Error(json.dumps('OBOM feature is not enabled for this company'),
                                 status_code=403)
    monkeypatch.setattr(TrustSourceAPI, 'import_obom', _Recorder(error=error))

    result = _upload(tmp_path, obom_document)

    assert result.exit_code == 1
    assert 'not enabled' in result.output


def test_api_keeps_the_version_in_the_base_url(monkeypatch):
    """House convention: the version is part of the base URL, method paths are
    version-free, and the key travels as the x-api-key header."""
    seen = {}

    def fake_post(url, json=None, data=None, headers=None, params=None):
        seen['url'] = url
        seen['headers'] = headers

        class _Response:
            status_code = 201

            def __bool__(self):
                return True

            @staticmethod
            def json():
                return {'ok': True}

        return _Response()

    monkeypatch.setattr('ts_obom.api.requests.post', fake_post)

    api = TrustSourceAPI('https://api.trustsource.io/v2', 'the-key')
    api.import_obom(FIXTURES / 'cloudformation' / 'template.yaml', {'projectName': 'P'})

    assert seen['url'] == 'https://api.trustsource.io/v2/core/imports/scan/obom'
    assert seen['headers']['x-api-key'] == 'the-key'
