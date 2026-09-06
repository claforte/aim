import threading

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

from aim.ext.transport.config import AIM_SERVER_MOUNTED_REPO_PATH
from aim.sdk.errors import RunLockingError
from aim.sdk.lock_manager import LockingVersion


@dataclass
class SharedRunSession:
    run: object
    leases: Set[str] = field(default_factory=set)
    lock: threading.RLock = field(default_factory=threading.RLock)


class SharedRunSessionRegistry:
    """Server-side registry for runs opened by multiple remote writers."""

    _sessions: Dict[Tuple[str, str], SharedRunSession] = {}
    _lock = threading.RLock()

    @classmethod
    def _repo(cls):
        import os

        from aim.sdk.repo import Repo

        repo_path = os.environ.get(AIM_SERVER_MOUNTED_REPO_PATH)
        return Repo.from_path(repo_path) if repo_path else Repo.default_repo()

    @classmethod
    def acquire(
        cls,
        run_hash: Optional[str],
        lease_id: str,
        experiment: Optional[str] = None,
    ) -> 'SharedRunLease':
        from aim.sdk.run import BasicRun

        if not lease_id:
            raise ValueError('A shared run lease_id is required.')
        repo = cls._repo()
        with cls._lock:
            session = None
            key = None
            if run_hash is not None:
                key = (repo.path, run_hash)
                session = cls._sessions.get(key)

            if session is None:
                if run_hash is not None:
                    lock_info = repo._lock_manager.get_run_lock_info(run_hash)
                    lock_path = repo._lock_manager.locks_path / repo._lock_manager.softlock_fname(run_hash)
                    stalled = lock_info.locked and lock_info.version == LockingVersion.NEW
                    if stalled:
                        try:
                            stalled = repo._lock_manager.is_stalled_lock(lock_path)
                        except FileNotFoundError:
                            # The exclusive writer released between inspection
                            # and reading its lock metadata.
                            stalled = True
                    if lock_info.locked and not stalled:
                        raise RunLockingError(
                            f"Cannot start a shared session for Run '{run_hash}': an exclusive writer is active."
                        )
                # Never force an existing lock here. An exclusive writer must be
                # rejected even if a shared client requested force_resume.
                run = BasicRun(run_hash, repo=repo, experiment=experiment, force_resume=False)
                key = (repo.path, run.hash)
                session = SharedRunSession(run=run)
                cls._sessions[key] = session
            elif experiment is not None:
                # Acquiring a lease is serialized with metadata writes too.
                with session.lock:
                    session.run.experiment = experiment

            session.leases.add(lease_id)
            return SharedRunLease(cls, key, lease_id, session)

    @classmethod
    def release(cls, key: Tuple[str, str], lease_id: str) -> None:
        with cls._lock:
            session = cls._sessions.get(key)
            if session is None or lease_id not in session.leases:
                return
            session.leases.remove(lease_id)
            if not session.leases:
                del cls._sessions[key]
                # Keep acquisition of this hash excluded until its physical
                # lock has been released and end_time has been committed.
                with session.lock:
                    session.run.close()

    @classmethod
    def clear(cls) -> None:
        """Close all sessions. Intended for server shutdown and tests."""
        with cls._lock:
            sessions = list(cls._sessions.values())
            cls._sessions.clear()
        for session in sessions:
            with session.lock:
                session.run.close()

    @classmethod
    def has_session(cls, repo_path: str, run_hash: str) -> bool:
        with cls._lock:
            return (repo_path, run_hash) in cls._sessions


class SharedRunLease:
    """A client lease exposing serialized operations on a canonical Run."""

    def __init__(self, registry, key, lease_id, session):
        self._registry = registry
        self._key = key
        self._lease_id = lease_id
        self._session = session
        self._released = False

    @property
    def hash(self):
        return self._session.run.hash

    def track(self, value, name=None, step=None, epoch=None, context=None):
        with self._session.lock:
            self._session.run.track(value, name=name, step=step, epoch=epoch, context=context)

    def set_item(self, key, value):
        with self._session.lock:
            self._session.run[key] = value

    def set(self, key, value, strict=True):
        with self._session.lock:
            self._session.run.set(key, value, strict=strict)

    def del_item(self, key):
        with self._session.lock:
            del self._session.run[key]

    def set_property(self, name, value):
        with self._session.lock:
            setattr(self._session.run, name, value)

    def add_tag(self, value):
        with self._session.lock:
            return self._session.run.add_tag(value)

    def remove_tag(self, value):
        with self._session.lock:
            return self._session.run.remove_tag(value)

    def set_artifacts_uri(self, uri):
        with self._session.lock:
            self._session.run.set_artifacts_uri(uri)

    def report_progress(self, expect_next_in=0, block=False):
        with self._session.lock:
            self._session.run.report_progress(expect_next_in=expect_next_in, block=block)

    def report_successful_finish(self, block=True):
        with self._session.lock:
            self._session.run.report_successful_finish(block=block)

    def check_in(self, flag_name=None, block=False):
        with self._session.lock:
            self._session.run._checkins.check_in(flag_name=flag_name, block=block)

    def release(self):
        if self._released:
            return
        self._released = True
        self._registry.release(self._key, self._lease_id)


def get_shared_run(run_hash=None, lease_id=None, experiment=None, **kwargs):
    # Imported here to avoid a handlers -> sdk.run -> repo -> transport cycle.
    from aim.ext.transport.handlers import ResourceRef

    lease = SharedRunSessionRegistry.acquire(run_hash, lease_id, experiment)
    return ResourceRef(lease, SharedRunLease.release)
