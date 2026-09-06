import pytest

from aim.ext.transport.config import AIM_SERVER_MOUNTED_REPO_PATH
from aim.ext.transport.handlers import get_lock
from aim.ext.transport.heartbeat import HeartbeatWatcher
from aim.ext.transport.shared_run import SharedRunSessionRegistry, get_shared_run
from aim.ext.transport.tracking import TrackingRouter
from aim.sdk import Repo, Run
from aim.sdk.errors import RunLockingError
from aim.sdk.run import BasicRun


@pytest.fixture
def mounted_repo(tmp_path, monkeypatch):
    repo = Repo.from_path(str(tmp_path), init=True)
    monkeypatch.setenv(AIM_SERVER_MOUNTED_REPO_PATH, repo.path)
    SharedRunSessionRegistry.clear()
    TrackingRouter.resource_pool.clear()
    yield repo
    TrackingRouter.resource_pool.clear()
    SharedRunSessionRegistry.clear()
    repo.close()


def test_reference_counting_idempotent_release_and_reopen(mounted_repo):
    first = SharedRunSessionRegistry.acquire(None, 'writer-1')
    run_hash = first.hash
    second = SharedRunSessionRegistry.acquire(run_hash, 'writer-2')

    session = SharedRunSessionRegistry._sessions[(mounted_repo.path, run_hash)]
    assert session.leases == {'writer-1', 'writer-2'}
    assert session.run.end_time is None

    first.release()
    first.release()
    assert session.leases == {'writer-2'}
    assert session.run.end_time is None

    second.release()
    assert (mounted_repo.path, run_hash) not in SharedRunSessionRegistry._sessions
    assert Run(run_hash, repo=mounted_repo, read_only=True).end_time is not None

    reopened = SharedRunSessionRegistry.acquire(run_hash, 'writer-3')
    assert reopened.hash == run_hash
    assert SharedRunSessionRegistry._sessions[(mounted_repo.path, run_hash)].run.end_time is None
    reopened.release()
    assert Run(run_hash, repo=mounted_repo, read_only=True).end_time is not None


def test_mixed_exclusive_and_shared_writers_are_rejected(mounted_repo):
    shared = SharedRunSessionRegistry.acquire(None, 'shared')
    with pytest.raises(RunLockingError):
        get_lock(run_hash=shared.hash)
    shared.release()

    exclusive = BasicRun(shared.hash, repo=mounted_repo)
    with pytest.raises(RunLockingError):
        SharedRunSessionRegistry.acquire(shared.hash, 'shared-after-exclusive')
    exclusive.close()


def test_multi_writer_requires_writable_remote_repo(mounted_repo):
    with pytest.raises(ValueError, match='writable remote'):
        Run(
            repo=mounted_repo,
            multi_writer=True,
            system_tracking_interval=None,
            capture_terminal_logs=False,
        )


def test_dead_client_cleanup_releases_last_writer(mounted_repo):
    resource = get_shared_run(lease_id='crashed-writer')
    run_hash = resource.ref.hash
    TrackingRouter.resource_pool['handler'] = ('dead-client', resource)

    HeartbeatWatcher({})._release_client_resources('dead-client')

    assert 'handler' not in TrackingRouter.resource_pool
    assert (mounted_repo.path, run_hash) not in SharedRunSessionRegistry._sessions
    assert Run(run_hash, repo=mounted_repo, read_only=True).end_time is not None


def test_heartbeat_cleanup_tolerates_concurrent_disconnect():
    class DisconnectingHeartbeatPool(dict):
        def keys(self):
            keys = list(super().keys())
            self.clear()
            return keys

    watcher = HeartbeatWatcher(DisconnectingHeartbeatPool(client=0), keep_alive_time=0)

    watcher._release_expired_clients()
