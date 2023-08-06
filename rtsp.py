import asyncio
from typing import Optional

import cv2
import numpy as np


def get_rtsp_image(url: str) -> Optional[np.ndarray]:
    video = cv2.VideoCapture(url)
    ok, img = video.read()
    if ok:
        return img
    return None


async def device_is_ok(authority: str, channel: int=1) -> bool:
    """
    Make video request to ip camera / ip dvr / nvr (only hikvision for now) to check if image is available
    """
    url = f'rtsp://{authority}/Streaming/Channels/{channel}02'

    loop = asyncio.get_running_loop()
    img = await loop.run_in_executor(None, get_rtsp_image, url)  #TODO: WARNING - canceling the coroutine will not stop the underlying thread, possibly preventing python to exit until the function returns
    if img is not None:
        return True
    return False


task = asyncio.create_task(device_is_ok('user:pass@host:port', 1))
