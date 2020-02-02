import os

import pytest
import app


def test_convert_to_path_git():
    path = app.convert_to_path('git@github.com:fluxcd/flux.git')
    assert path == 'git@github.com:fluxcd-flux.git'


def test_convert_to_path_https():
    path = app.convert_to_path('https://github.com/fluxcd/flux.git')
    assert path == 'https:github.com-fluxcd-flux.git'


@pytest.fixture
async def client(aiohttp_client, loop, monkeypatch):
    async def dummy_run(cmd): return cmd

    async def run_helm(command, values_yaml):
        return await dummy_run(app.get_helm_cmd(command, values_yaml))

    monkeypatch.setattr(app, 'run_helm', run_helm)

    original_cleanup = app.cleanup

    async def cleanup(values_yaml, repo):
        await original_cleanup(values_yaml, repo)
        if values_yaml:
            assert not os.path.exists(values_yaml)
        if repo:
            assert not os.path.exists(repo)

    monkeypatch.setattr(app, 'cleanup', cleanup)

    return await aiohttp_client(await app.app_factory())


async def test_app_functional_1(client):
    resp = await client.post('/', json={
        "release": "flux",
        "repo": "git@github.com:fluxcd/flux.git",
        "namespace": "default",
        "values": {
            "mysqlRootPassword": "hello"
        }
    })
    assert resp.status == 200
    resp_json = await resp.json()
    print(resp_json)
    assert resp_json['status'] == 'ok'
    assert resp_json['result']


async def test_app_functional_2(client):
    resp = await client.post('/', json={
        "release": "flux",
        "repo": "git@github.com:fluxcd/flux.git",
        "namespace": "default"
    })
    assert resp.status == 200
    resp_json = await resp.json()
    assert resp_json['status'] == 'ok'
    assert resp_json['result']
