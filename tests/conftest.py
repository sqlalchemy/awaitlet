from __future__ import annotations

from functools import partial
from typing import List

import pytest
from pytest import Function
from pytest import Item

from awaitlet.util import testing


testing.async_test = async_test = pytest.mark.async_test


def pytest_collection_modifyitems(session, config, items: List[Item]):
    for item in items:
        if isinstance(item, Function) and item.get_closest_marker(
            "async_test"
        ):
            item.orig_obj = fn = item.obj
            item.obj = partial(testing.run_coroutine_function, fn)
