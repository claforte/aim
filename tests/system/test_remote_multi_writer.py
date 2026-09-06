import multiprocessing
import os
import socket
import subprocess
import sys
import time
import traceback

import numpy as np
import requests

from aim.ext.transport.config import AIM_SERVER_MOUNTED_REPO_PATH
from aim.sdk import Image, Repo, Run, Video
from aim.storage.context import Context


def _trainer(uri, events, results):
    try:
        run = Run(repo=uri, multi_writer=True, system_tracking_interval=None, capture_terminal_logs=False)
        run.track(0.9, name='loss', step=100, context={'subset': 'train'})
        run.track(Image(np.zeros((2, 2, 3), dtype=np.uint8), caption='train'), name='train_image', step=100)
        run.track(Video(data=b'train-video', format='mp4'), name='train_video', step=100)
        run['phase'] = 'training'
        run.repo._client.get_queue().wait_for_finish()
        results.put(('trainer-ready', run.hash))
        events['trainer_close'].wait(20)
        run.close()
        results.put(('trainer-closed', None))
    except Exception:
        results.put(('error', traceback.format_exc()))


def _evaluator(uri, run_hash, worker_id, commands, results):
    try:
        run = Run(
            run_hash,
            repo=uri,
            multi_writer=True,
            system_tracking_interval=None,
            capture_terminal_logs=False,
        )
        run.track(0.8 + worker_id, name=f'accuracy-{worker_id}', step=100, context={'subset': 'eval'})
        run.track(
            Image(np.full((2, 2, 3), worker_id + 1, dtype=np.uint8), caption=f'eval-{worker_id}'),
            name=f'eval_image-{worker_id}',
            step=100,
        )
        run.track(Video(data=f'eval-{worker_id}'.encode(), format='mp4'), name=f'eval_video-{worker_id}', step=100)
        run.repo._client.get_queue().wait_for_finish()
        results.put((f'evaluator-{worker_id}-ready', None))

        while True:
            command, value = commands.get(timeout=20)
            if command == 'race':
                run.track(1.0 if value == 'first' else 2.0, name='race', step=75)
                run['phase'] = value
                run.repo._client.get_queue().wait_for_finish()
                results.put((f'evaluator-{worker_id}-race', None))
            elif command == 'close':
                run.close()
                results.put((f'evaluator-{worker_id}-closed', None))
                return
    except Exception:
        results.put(('error', traceback.format_exc()))


def _free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _next_result(results, expected):
    kind, value = results.get(timeout=30)
    assert kind != 'error', value
    assert kind == expected
    return value


def test_remote_multi_writer_lifecycle_and_historical_replacement(tmp_path):
    repo = Repo.from_path(str(tmp_path), init=True)
    port = _free_port()
    uri = f'aim://127.0.0.1:{port}'
    env = os.environ.copy()
    env[AIM_SERVER_MOUNTED_REPO_PATH] = repo.path
    server = subprocess.Popen(
        [
            sys.executable,
            '-m',
            'uvicorn',
            'aim.ext.transport.run:app',
            '--host',
            '127.0.0.1',
            '--port',
            str(port),
            '--log-level',
            'warning',
        ],
        cwd=os.getcwd(),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ctx = multiprocessing.get_context('spawn')
    manager = ctx.Manager()
    events = manager.dict(trainer_close=manager.Event())
    results = manager.Queue()
    trainer = ctx.Process(target=_trainer, args=(uri, events, results))
    evaluators = []
    commands = []
    remote_repo = None

    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                if requests.get(f'http://127.0.0.1:{port}/status/', timeout=0.5).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            raise AssertionError('tracking server did not start')

        trainer.start()
        run_hash = _next_result(results, 'trainer-ready')
        for worker_id in range(2):
            command_queue = manager.Queue()
            process = ctx.Process(target=_evaluator, args=(uri, run_hash, worker_id, command_queue, results))
            process.start()
            commands.append(command_queue)
            evaluators.append(process)
            _next_result(results, f'evaluator-{worker_id}-ready')

        reader = Run(run_hash, repo=uri, read_only=True)
        remote_repo = reader.repo
        assert reader.active
        assert reader.get_metric('loss', Context({'subset': 'train'})).values.values_list() == [0.9]
        for worker_id in range(2):
            assert reader.get_metric(f'accuracy-{worker_id}', Context({'subset': 'eval'})).values.values_list() == [
                0.8 + worker_id
            ]
            assert reader.get_image_sequence(f'eval_image-{worker_id}', Context({})) is not None
            assert reader.get_video_sequence(f'eval_video-{worker_id}', Context({})) is not None

        events['trainer_close'].set()
        _next_result(results, 'trainer-closed')
        trainer.join(10)
        assert reader.active

        commands[0].put(('race', 'first'))
        _next_result(results, 'evaluator-0-race')
        commands[1].put(('race', 'second'))
        _next_result(results, 'evaluator-1-race')
        assert reader['phase'] == 'second'
        assert reader.get_metric('race', Context({})).values.values_list() == [2.0]

        commands[0].put(('close', None))
        _next_result(results, 'evaluator-0-closed')
        evaluators[0].join(10)
        assert reader.active

        commands[1].put(('close', None))
        _next_result(results, 'evaluator-1-closed')
        evaluators[1].join(10)
        assert not reader.active
        assert reader.end_time is not None

        resumed = Run(
            run_hash,
            repo=uri,
            multi_writer=True,
            system_tracking_interval=None,
            capture_terminal_logs=False,
        )
        assert reader.active
        resumed.track(1.0, name='checkpoint', step=60)
        resumed.track(2.0, name='checkpoint', step=80)
        resumed.track(3.0, name='checkpoint', step=100)
        resumed.track(20.0, name='checkpoint', step=80)
        resumed.track(4.0, name='checkpoint')
        resumed.close()

        checkpoint = reader.get_metric('checkpoint', Context({})).data.items_list()
        assert checkpoint[0] == [60, 80, 100, 101]
        assert checkpoint[1][0] == [1.0, 20.0, 3.0, 4.0]
        assert not reader.active
        reader.close()
    finally:
        for process in [trainer, *evaluators]:
            if process.is_alive():
                process.terminate()
            process.join(5)
        manager.shutdown()
        if remote_repo is not None:
            remote_repo.close()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        repo.close()
