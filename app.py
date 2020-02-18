import os
import asyncio
import json
import yaml
import time
import shutil

import aiofiles
from aiohttp import web
from functools import partial, wraps


routes = web.RouteTableDef()


class CmdError(Exception):
    pass


class NameSpaceError(Exception):
    pass


async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    # print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        return stdout.decode()
    if proc.returncode != 0:
        raise CmdError(stderr.decode())


async def dummy_run(cmd): return cmd


def get_temp_path():
    # timestamp = decimal.Decimal(time.time() * 1000000)
    timestamp = str(time.time())
    return f'/tmp/{timestamp}'
    # return f'/tmp/{timestamp}'


async def write_values_yaml(values):
    values_yaml = f'{get_temp_path()}.yaml'
    async with aiofiles.open(values_yaml, mode='w') as f:
        await f.write(yaml.dump(values))
    return values_yaml


def get_helm_cmd(command, values_yaml):
    cmd = (
        f'kubectl create ns {command["namespace"]} || true && '
        f'helm upgrade -i --wait --cleanup-on-fail --force '
        f'--namespace {command["namespace"]} '
        f'{command["release"]} {command["chart"]}'
    )
    cmd += values_yaml and f' -f {values_yaml}' or ''
    return cmd


async def run_helm(command, values_yaml):
    return await run(get_helm_cmd(command, values_yaml))


def convert_to_path(remote):
    remote = remote.replace('//', '')
    remote = remote.replace('/', '-')
    return remote


async def checkout_repo(repo, branch=None, sha=None):
    temp_path = f'{get_temp_path()}.git'
    if not branch:
        branch = 'master'
    print(await run(f'git clone --depth=1 -b {branch} {repo} {temp_path}'))
    return temp_path


def wrap(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, pfunc)
    return wrapper


rmtree = wrap(shutil.rmtree)
remove = wrap(os.remove)


async def cleanup(values_yaml, repo):
    if values_yaml:
        await remove(values_yaml)
    if repo:
        await rmtree(repo)


@routes.post('/')
async def helm(request):
    error = None
    values_yaml = None
    repo = None
    try:
        command = await request.json()
        if command["namespace"] in request.app['prohibited_namespaces']:
            raise NameSpaceError("This namespace is not allowed")
        if command.get('chart') and command.get('repo'):
            raise CmdError('Can not use both "chart" and "repo"')
        if (command.get('chart')
            and (
                command.get('branch')
                or command.get('sha')
                or command.get('path'))):
            raise CmdError('Can not use both "chart" and "branch/sha/path"')

        if command.get('repo'):
            repo = command["chart"] = await checkout_repo(
                command.get('repo'), command.get('branch'), command.get('sha')
            )
            command['chart'] = os.path.join(
                command["chart"], command.get('path', ''))
        values_yaml = command.get('values') and await write_values_yaml(command['values'])
        # TODO: save cloned repos and then fetch
        # TODO: strip all bad symbols from input for security
        result = await run_helm(command, values_yaml)
        return web.json_response({"status": "ok", "result": result})

    except json.decoder.JSONDecodeError:
        error = "JSONDecodeError"
    except (CmdError, NameSpaceError) as e:
        error = str(e)

    finally:
        await cleanup(values_yaml, repo)
    return web.json_response({"status": "error", "result": error})


async def app_factory():
    app = web.Application()
    app.add_routes(routes)

    app['prohibited_namespaces'] = ['kube-system']
    app['prohibited_namespaces'].extend(os.environ.get(
        'PROHIBITED_NAMESPACES', '').replace(' ', '').split(','))
    return app


if __name__ == '__main__':
    # run = dummy_run
    web.run_app(app_factory(), port=80)
