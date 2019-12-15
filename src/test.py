from stconflict import Date

def test_date_dummy():
    """Test dummy."""
    date = Date(2019, 11, 1)
    assert date.yy == 2019
    assert date.mm == 11
    assert date.dd == 1
