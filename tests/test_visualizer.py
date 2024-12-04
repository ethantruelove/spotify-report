from unittest import TestCase, mock
from unittest.mock import MagicMock

from app import visualizer as v

case = TestCase()
case.maxDiff = None


@mock.patch("app.visualizer.plt")
@mock.patch("app.visualizer.io")
def test_freq(mock_io, mock_plt):
    mock_io.BytesIO.return_value = None
    mock_plt.subplots.return_value = (MagicMock(), MagicMock())
    actual = v.freq(data=["track1", "track2"], top=1)

    case.assertEqual(None, actual)
