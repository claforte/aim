import time

import numpy as np

from aim.sdk import Image, Run, Video
from aim.storage.context import Context
from aim.storage.hashing import hash_auto
from tests.base import TestBase


class TestRunHistoricalReplacement(TestBase):
    def test_metric_replacement_rebuilds_metadata_and_preserves_tail(self):
        run = Run(system_tracking_interval=None, capture_terminal_logs=False)
        for step, value in enumerate((10.0, 5.0, 1.0, 7.0, 6.0)):
            run.track(value, name='metric', step=step, epoch=step)

        metric = run.get_metric('metric', Context({}))
        old_timestamp = metric.timestamps[hash_auto(2)]
        time.sleep(0.001)
        run.track(4.0, name='metric', step=0, epoch=10)
        run.track(8.0, name='metric', step=2, epoch=12)
        run.track(3.0, name='metric', step=4, epoch=14)

        trace = run.meta_run_tree['traces', Context({}).idx, 'metric']
        self.assertEqual(0, trace['first_step'])
        self.assertEqual(4.0, trace['first'])
        self.assertEqual(4, trace['last_step'])
        self.assertEqual(3.0, trace['last'])
        self.assertEqual(3.0, trace['min'])
        self.assertEqual(8.0, trace['max'])

        metric = run.get_metric('metric', Context({}))
        steps, columns = metric.data.items_list()
        self.assertListEqual([0, 1, 2, 3, 4], steps)
        self.assertListEqual([4.0, 5.0, 8.0, 7.0, 3.0], columns[0])
        self.assertEqual(12, metric.epochs[hash_auto(2)])
        self.assertGreater(metric.timestamps[hash_auto(2)], old_timestamp)

        run.track(11.0, name='metric')
        self.assertListEqual([0, 1, 2, 3, 4, 5], run.get_metric('metric', Context({})).data.items_list()[0])

    def test_image_and_video_replacement_preserves_later_steps(self):
        run = Run(system_tracking_interval=None, capture_terminal_logs=False)
        pixels = np.zeros((2, 2, 3), dtype=np.uint8)

        run.track(Image(pixels, caption='old first'), name='images', step=0)
        run.track(Image(pixels, caption='future tail'), name='images', step=2)
        run.track(Image(pixels, caption='new first'), name='images', step=0)

        images = run.get_image_sequence('images', Context({})).data.items_list()
        self.assertListEqual([0, 2], images[0])
        self.assertListEqual(['new first', 'future tail'], [image.caption for image in images[1][0]])

        run.track(Video(data=b'old', format='mp4', caption='old'), name='videos', step=4)
        run.track(Video(data=b'new', format='mp4', caption='new'), name='videos', step=4)
        run.track(Video(data=b'tail', format='mp4', caption='tail'), name='videos', step=5)

        videos = run.get_video_sequence('videos', Context({})).data.items_list()
        self.assertListEqual([4, 5], videos[0])
        self.assertListEqual(['new', 'tail'], [video.caption for video in videos[1][0]])

    def test_replacing_longest_media_record_updates_record_size(self):
        run = Run(system_tracking_interval=None, capture_terminal_logs=False)
        image = Image(np.zeros((1, 1, 3), dtype=np.uint8))
        run.track([image, image, image], name='batch', step=0)
        run.track([image, image], name='batch', step=1)
        run.track([image], name='batch', step=0)

        trace = run.meta_run_tree['traces', Context({}).idx, 'batch']
        self.assertEqual(2, trace['record_max_length'])
        self.assertEqual(1, len(trace['first']))
        self.assertEqual(2, len(trace['last']))
