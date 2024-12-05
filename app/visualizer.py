import io
from enum import Enum
from typing import List

from matplotlib import pyplot as plt


class MediaType(str, Enum):
    tracks = "tracks"
    artists = "artists"
    albums = "albums"


def freq(data: List[str], top: int = 10) -> io.BytesIO:
    """
    Generate a bar graph image in memory and return the buffer.

    Args:
        data (List[str]): List of names to plot as the x axis
        top (int, optional): The number of names to take. Defaults to 10.

    Returns:
        io.BytesIO: The buffer for the image
    """
    fig, ax = plt.subplots()
    shortened_names = [d[0] if len(d[0]) < 15 else d[0][:13] + "..." for d in data]
    ax.bar(shortened_names, [d[1] for d in data])
    plt.xticks(rotation=45)

    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png", bbox_inches="tight")
    plt.close(fig)

    return img_buf
