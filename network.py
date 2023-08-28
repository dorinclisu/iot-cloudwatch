import asyncio
import functools
import logging
import time

import httpx
from pythonping import ping



ping('localhost')  # ensure script has root permissions


async def test_tcp(host: str, port: int, payload: str='') -> bool:
    """
    Make generic tcp request to generic server to check if it's running
    """
    try:
        reader, writer = await asyncio.open_connection(host, port)

        if payload:
            logging.debug(f'Sending to {host}:{port} - {payload!r}')
            writer.write(payload.encode())
            await writer.drain()

            logging.debug(f'Receiving from {host}:{port} ...')
            data = await reader.read(100)
            logging.debug(f'Received from {host}:{port} - {data.decode()!r}')

        writer.close()
        await writer.wait_closed()
        return True
    except:
        logging.debug(f'Handled exception for "{host}"', exc_info=True)
        return False


async def test_connection(uri: str, timeout: float=1) -> float:
    """
    Return time in seconds to make the request (if http) or ping ICMP, return value of timeout or -1 if other connection error.
    """
    if uri.startswith('http://'):
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                t = time.monotonic()
                await client.get(uri)
                return time.monotonic() - t

            except httpx.TimeoutException:
                return timeout

            except httpx.TransportError:
                logging.debug(f'Handled exception for "{uri}"', exc_info=True)
                return -1

    elif '://' in uri:
        raise ValueError('Only ICMP (plain host) or http(s) are supported')

    else:
        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(None, functools.partial(ping, target=uri, count=1, timeout=timeout))

            if not resp.success():
                return timeout

            return float(resp.rtt_max)
        except:
            logging.debug(f'Handled exception for "{uri}"', exc_info=True)
            return -1
