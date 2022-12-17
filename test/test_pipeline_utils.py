from unittest import TestCase
from unittest.mock import patch

import yaml

from pipeline_dash.pipeline_utils import collect_jobs_pipeline, find_all_pipeline, PipelineDict


class Test(TestCase):
    def test_find_all_pipeline(self):
        test_dict: PipelineDict = dict()  # type: ignore

        self.assertEqual([], find_all_pipeline(test_dict, lambda name, p: False))

        test_dict = PipelineDict(
            name="root",
            uuid="1",
            children={},
        )
        self.assertEqual([test_dict], find_all_pipeline(test_dict, lambda name, p: p["uuid"] == "1"))

        test_dict = PipelineDict(
            name="root",
            uuid="1",
            recurse=False,
            children={
                "child": (
                    test_child := PipelineDict(
                        name="child",
                        uuid="2",
                        recurse=True,
                        children={},
                    )
                ),
            },
        )
        self.assertEqual([test_child], find_all_pipeline(test_dict, lambda name, p: p["recurse"] == True))

        test_dict = PipelineDict(
            name="root",
            uuid="1",
            recurse=True,
            children={
                "child": (
                    test_child := PipelineDict(
                        name="child",
                        uuid="2",
                        recurse=True,
                        children={},
                    )
                ),
            },
        )
        self.assertEqual([test_dict, test_child], find_all_pipeline(test_dict, lambda name, p: p["recurse"] == True))

    @patch("uuid.uuid4")
    def test_collect_jobs_pipeline(self, uuid_mock):
        self.maxDiff = None
        uuid_mock.return_value = "fakeuuid"

        test_yaml = yaml.safe_load(
            """
            servers:
              "https://test-server":
                pipelines:
                  .lunar:
                    test-job-name:
                      $recurse: true
            """
        )
        self.assertDictEqual(
            PipelineDict(
                name="",
                uuid="fakeuuid",
                children={
                    "lunar": PipelineDict(
                        name="lunar",
                        uuid="fakeuuid",
                        recurse=False,
                        children={
                            "test-job-name": PipelineDict(
                                name="test-job-name",
                                uuid="fakeuuid",
                                server="https://test-server",
                                children={},
                                recurse=True,
                            )
                        },
                    ),
                },
            ),
            collect_jobs_pipeline(test_yaml),
        )
        test_yaml = yaml.safe_load(
            """
            servers:
              "https://test-server":
                pipelines:
                  .lunar:
                    $recurse: true
                    test-job-name:
            """
        )
        self.assertDictEqual(
            PipelineDict(
                name="",
                uuid="fakeuuid",
                children={
                    "lunar": PipelineDict(
                        name="lunar",
                        uuid="fakeuuid",
                        recurse=True,
                        children={
                            "test-job-name": PipelineDict(
                                name="test-job-name",
                                uuid="fakeuuid",
                                server="https://test-server",
                                children={},
                                recurse=True,
                            )
                        },
                    ),
                },
            ),
            collect_jobs_pipeline(test_yaml),
        )
