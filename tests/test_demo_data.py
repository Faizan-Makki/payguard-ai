from pandas.testing import assert_frame_equal
from payguard.demo_data import make_demo_transactions


def test_demo_reproducible():
    assert_frame_equal(make_demo_transactions(), make_demo_transactions())

