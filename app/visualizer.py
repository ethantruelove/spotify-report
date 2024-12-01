import io
from enum import Enum
from typing import List

import numpy as np
from matplotlib import pyplot as plt


class MediaType(str, Enum):
    tracks = "tracks"
    artists = "artists"
    albums = "albums"


def freq(data: List[str], top: int = 10):
    fig, ax = plt.subplots()
    shortened_names = [d[0] if len(d[0]) < 15 else d[0][:13] + "..." for d in data]
    ax.bar(shortened_names, [d[1] for d in data])
    plt.xticks(rotation=45)

    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png", bbox_inches="tight")
    plt.close(fig)

    return img_buf
