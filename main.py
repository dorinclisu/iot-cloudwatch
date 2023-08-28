import asyncio
import collections
import logging
import os
import pickle
import signal
from datetime import datetime
from typing import Deque

import boto3
import botocore.exceptions
from mypy_boto3_cloudwatch.type_defs import MetricDatumTypeDef
from pydantic import BaseModel, BaseSettings

import pzem0xx
import shelly
from network import test_connection


logging.getLogger().setLevel(os.getenv('LOG_LEVEL', 'INFO'))
logging.getLogger('botocore').setLevel(logging.WARNING)


class Env(BaseSettings):
    aws_access_key_id:     str
    aws_secret_access_key: str
    aws_default_region:    str

    aws_metric_namespace: str

    aws_metric_name_network: str

    internet_host:        str
    internet_timeout:     int = 5

    site_id:              str
    site_devices:   list[str] = []
    net_timeout:          int = 1

    aws_metric_name_voltage: str
    aws_metric_name_current: str
    aws_metric_name_energy:  str
    aws_metric_name_switch:  str
    aws_metric_name_relay:   str

    pzem_devices: dict[str, int] = {}
    shelly_devices:    list[str] = []

env = Env()  # type: ignore [call-arg]
cw = boto3.client('cloudwatch')
###############################################################################

class DeviceStatus(BaseModel):
    name:   str
    ping: float

class MeterDeviceStatus(BaseModel):
    name: str
    voltage: float
    current: float
    energy_1h: int | None = None

class SwitchDeviceStatus(BaseModel):
    name: str
    value: int

class RelayDeviceStatus(BaseModel):
    name: str
    value: int

class SiteStatus(BaseModel):
    id:                           str
    timestamp:               datetime
    internet_ping:              float
    #devices_working_percentage: float = -1
    devices:              list[DeviceStatus] = []
    meter_devices:   list[MeterDeviceStatus] = []
    switch_devices: list[SwitchDeviceStatus] = []
    relay_devices:   list[RelayDeviceStatus] = []



async def pzem_measure(address: int, timeout: float=1) -> pzem0xx.DCMeasurement | None:
    def measure() -> pzem0xx.DCMeasurement:
        pzem = pzem0xx.PZEM0XX(address)
        return pzem.get_measurement()

    loop = asyncio.get_running_loop()
    try:
        measurement = await loop.run_in_executor(None, measure)
        await asyncio.sleep(0.1)
        return measurement
    except:
        logging.warning(f'Handled exception for PZEM device {address}', exc_info=True)
        return None


async def check_devices(timeout: float=1) -> SiteStatus:
    status = SiteStatus(
        id=env.site_id,
        timestamp=datetime.utcnow(),
        internet_ping=await test_connection(env.internet_host, timeout=env.internet_timeout)
    )

    logging.info('Checking devices status ...')

    tasks: list[asyncio.Task[float]] = []

    for device_name in env.site_devices:
        task = asyncio.create_task(test_connection(uri=device_name, timeout=timeout))
        tasks.append(task)

    pings: list[float] = await asyncio.gather(*tasks)

    for ping, device_name in zip(pings, env.site_devices):
        device = DeviceStatus(
            name=device_name,
            ping=ping
        )
        status.devices.append(device)

    logging.info('Checking electrical devices status ...')

    for name, address in env.pzem_devices.items():
        measurement = await pzem_measure(address, timeout=timeout)
        if measurement:
            meter_device = MeterDeviceStatus(
                name=name,
                voltage=measurement['voltage'],
                current=measurement['current']
            )
            status.meter_devices.append(meter_device)

    for host in env.shelly_devices:
        shelly_status = await shelly.get_status(host)
        if shelly_status:
            for shelly_switch in shelly_status['inputs']:
                status.switch_devices.append(SwitchDeviceStatus(
                    name = f'{shelly_status["name"]}/ch{shelly_switch["id"]}',
                    value = int(shelly_switch['state'])
                ))
            for shelly_relay in shelly_status['relays']:
                status.relay_devices.append(RelayDeviceStatus(
                    name = f'{shelly_status["name"]}/ch{shelly_relay["id"]}',
                    value = int(shelly_relay['output'])
                ))

    return status


def report_metrics(status: SiteStatus) -> None:
    def generate_metric_data(device: DeviceStatus) -> MetricDatumTypeDef:
        return {
            'MetricName': env.aws_metric_name_network,
            'Dimensions': [
                {
                    'Name': 'Device',
                    'Value': f'{status.id}/{device.name}'
                },
            ],
            'Timestamp': status.timestamp,
            'Value': device.ping,
            'Unit': 'Seconds'
        }

    def generate_electric_metrics_data(device: MeterDeviceStatus) -> list[MetricDatumTypeDef]:
        data: list[MetricDatumTypeDef] = [
            {
                'MetricName': env.aws_metric_name_voltage,
                'Dimensions': [
                    {
                        'Name': 'Device',
                        'Value': f'{status.id}/{device.name}'
                    },
                ],
                'Timestamp': status.timestamp,
                'Value': device.voltage,
                'Unit': 'None'
            },
            {
                'MetricName': env.aws_metric_name_current,
                'Dimensions': [
                    {
                        'Name': 'Device',
                        'Value': f'{status.id}/{device.name}'
                    },
                ],
                'Timestamp': status.timestamp,
                'Value': device.current,
                'Unit': 'None'
            },
        ]
        if device.energy_1h:
            data.append(
                {
                    'MetricName': env.aws_metric_name_energy,
                    'Dimensions': [
                        {
                            'Name': 'Device',
                            'Value': f'{status.id}/{device.name}'
                        },
                    ],
                    'Timestamp': status.timestamp,
                    'Value': device.energy_1h,
                    'Unit': 'None'
                }
            )
        return data

    def generate_switch_metrics_data() -> list[MetricDatumTypeDef]:
        data: list[MetricDatumTypeDef] = []
        for switch_device in status.switch_devices:
            data.append({
                'MetricName': env.aws_metric_name_switch,
                'Dimensions': [
                        {
                            'Name': 'Device',
                            'Value': f'{status.id}/{switch_device.name}'
                        },
                    ],
                    'Timestamp': status.timestamp,
                    'Value': switch_device.value,
                    'Unit': 'None'
            })
        return data

    def generate_relay_metrics_data() -> list[MetricDatumTypeDef]:
        data: list[MetricDatumTypeDef] = []
        for relay_device in status.relay_devices:
            data.append({
                'MetricName': env.aws_metric_name_relay,
                'Dimensions': [
                        {
                            'Name': 'Device',
                            'Value': f'{status.id}/{relay_device.name}'
                        },
                    ],
                    'Timestamp': status.timestamp,
                    'Value': relay_device.value,
                    'Unit': 'None'
            })
        return data

    metric_data_channels = [generate_metric_data(device) for device in status.devices]
    electric_metric_data_channels = [metric
        for device in status.meter_devices
        for metric in generate_electric_metrics_data(device)
    ]
    logging.info(f'Sending metric data for {status.timestamp} ...')
    #return
    cw.put_metric_data(
        Namespace=env.aws_metric_namespace,
        MetricData=[
            generate_metric_data(DeviceStatus(name='Internet', ping=status.internet_ping)),
            *metric_data_channels,
            *electric_metric_data_channels,
            *generate_switch_metrics_data(),
            *generate_relay_metrics_data()
        ]
    )


async def main() -> None:
    stop = asyncio.Event()

    def stop_handler(*args):
        logging.info('Received stop signal')
        stop.set()

    async def sleep(t: float):
        try:
            await asyncio.wait_for(stop.wait(), timeout=t)
        except asyncio.TimeoutError:
            pass

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, stop_handler)
    loop.add_signal_handler(signal.SIGTERM, stop_handler)

    period_m = 1
    sleep_s = 1
    backup_file = 'status_queue.pickle'

    try:
        with open(backup_file, 'rb') as f:
            queue_list = pickle.load(f)
            logging.info(f'Loaded status queue from "{backup_file}"')
    except OSError:
        queue_list = []

    queue: Deque[SiteStatus] = collections.deque(queue_list, maxlen=60*24*7)

    last_minute = (datetime.utcnow().minute - period_m) % 60

    while not stop.is_set():
        minute = datetime.utcnow().minute

        if (minute - last_minute) % 60 >= period_m:
            last_minute = minute

            status = await check_devices(env.net_timeout)
            logging.debug(status)
            queue.append(status)

            loop = asyncio.get_running_loop()
            try:
                while len(queue) and not stop.is_set():
                    status_queued = queue[0]
                    await loop.run_in_executor(None, report_metrics, status_queued)
                    queue.popleft()  # only pop if status was reported successfully as metric
                    await asyncio.sleep(0.01)

            except botocore.exceptions.EndpointConnectionError:
                logging.warning('Cannot connect to aws')

        else:
            await sleep(sleep_s)
            #await asyncio.sleep(sleep_s)  # cannot be interrupted by stop event

    with open(backup_file, 'wb') as file:
        logging.info(f'Saving status queue to "{backup_file}"')
        pickle.dump(list(queue), file)


if __name__ == '__main__':
    asyncio.run(main())
