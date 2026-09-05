from aim.sdk import Repo, Text
from aim.storage.context import Context
from tests.base import TestBase


class TestSequenceStepLookup(TestBase):
    def test_metric_has_exact_step(self):
        run = self.create_run(system_tracking_interval=None)
        run_hash = run.hash
        run.track(1.0, name='metric', step=1)
        run.track(3.0, name='metric', step=3)
        run.close()

        metric = Repo.default_repo().get_run(run_hash).get_metric('metric', Context({}))

        self.assertTrue(metric.has_step(1))
        self.assertFalse(metric.has_step(2))
        self.assertTrue(metric.has_step(3))

    def test_v1_sequence_has_exact_step(self):
        run = self.create_run(system_tracking_interval=None)
        run_hash = run.hash
        run.track(Text('one'), name='text', step=1)
        run.track(Text('three'), name='text', step=3)
        run.close()

        texts = Repo.default_repo().get_run(run_hash).get_text_sequence('text', Context({}))

        self.assertTrue(texts.has_step(1))
        self.assertFalse(texts.has_step(2))
        self.assertTrue(texts.has_step(3))
