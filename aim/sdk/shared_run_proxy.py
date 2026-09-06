import uuid

from typing import TYPE_CHECKING, Optional

from aim.ext.transport.message_utils import pack_args
from aim.ext.transport.remote_resource import RemoteResourceAutoClean
from aim.storage.treeutils import encode_tree


if TYPE_CHECKING:
    from aim.ext.transport.client import Client


class SharedRunProxyAutoClean(RemoteResourceAutoClean):
    PRIORITY = 70


class SharedRunProxy:
    """Remote lease for a server-owned writable run."""

    def __init__(
        self,
        client: 'Client',
        run_hash: Optional[str],
        experiment: Optional[str] = None,
    ):
        self._resources = None
        self._rpc_client = client
        self._queue_id = run_hash or -1
        self._lease_id = str(uuid.uuid4())
        self.init_args = pack_args(
            encode_tree(
                {
                    'run_hash': run_hash,
                    'lease_id': self._lease_id,
                    'experiment': experiment,
                }
            )
        )
        self.resource_type = 'SharedRun'
        self._handler = self._rpc_client.get_resource_handler(self, self.resource_type, args=self.init_args)
        self.hash = self._rpc_client.run_instruction(-1, self._handler, 'hash')
        self._queue_id = self.hash

        self._resources = SharedRunProxyAutoClean(self)
        self._resources.hash = self.hash
        self._resources.rpc_client = client
        self._resources.handler = self._handler

    def _write(self, method, args=()):
        self._rpc_client.run_instruction(self._queue_id, self._handler, method, args, is_write_only=True)

    def track(self, value, name=None, step=None, epoch=None, context=None):
        self._write('track', (value, name, step, epoch, context))

    def set_item(self, key, value):
        self._write('set_item', (key, value))

    def set(self, key, value, strict=True):
        self._write('set', (key, value, strict))

    def del_item(self, key):
        self._write('del_item', (key,))

    def set_property(self, name, value):
        self._write('set_property', (name, value))

    def add_tag(self, value):
        return self._rpc_client.run_instruction(self._queue_id, self._handler, 'add_tag', (value,))

    def remove_tag(self, value):
        return self._rpc_client.run_instruction(self._queue_id, self._handler, 'remove_tag', (value,))

    def set_artifacts_uri(self, uri):
        self._write('set_artifacts_uri', (uri,))

    def report_progress(self, expect_next_in=0, block=False):
        return self._rpc_client.run_instruction(
            self._queue_id, self._handler, 'report_progress', (expect_next_in, block)
        )

    def report_successful_finish(self, block=True):
        return self._rpc_client.run_instruction(self._queue_id, self._handler, 'report_successful_finish', (block,))

    def check_in(self, flag_name=None, block=False):
        return self._rpc_client.run_instruction(self._queue_id, self._handler, 'check_in', (flag_name, block))

    def close(self):
        if self._resources is None:
            return
        self._resources.close()
        self._resources = None
