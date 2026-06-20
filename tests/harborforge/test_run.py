"""Unit tests for harborforge.run._is_single_task."""

from harborforge.run import _is_single_task


class TestIsSingleTask:
    def test_dataset_slash_id_is_single(self):
        assert _is_single_task("daeval/0") is True

    def test_dabstep_slash_id_is_single(self):
        assert _is_single_task("DABStep/123") is True

    def test_deep_path_is_single(self):
        assert _is_single_task("dspredict/house-prices-advanced-regression-techniques") is True

    def test_dataset_name_is_not_single(self):
        assert _is_single_task("daeval") is False

    def test_discovery_is_not_single(self):
        assert _is_single_task("discovery") is False

    def test_empty_string_is_not_single(self):
        assert _is_single_task("") is False
