import asyncio
import sys
from typing import TypedDict

import httpx


class ShellyInput(TypedDict):
    id:    int
    name:  str
    state: bool

class ShellyRelaySwitch(TypedDict):
    id:     int
    name:   str
    output: bool
    apower: float
    pf:     float

class ShellyStatus(TypedDict):
    name:    str
    inputs:  list[ShellyInput]
    relays:  list[ShellyRelaySwitch]


async def get_status(host: str) -> ShellyStatus | None:
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.get(f'http://{host}/rpc/Shelly.GetConfig')
        except httpx.TransportError:
            return None
    resp_config = response.json()

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.get(f'http://{host}/rpc/Shelly.GetStatus')
        except httpx.TransportError:
            return None
    resp_status = response.json()

    status: ShellyStatus = {
        'name': resp_config['wifi']['ap']['ssid'],
        'inputs': [],
        'relays': []
    }
    for channel in range(16):
        input_key = f'input:{channel}'
        switch_key = f'switch:{channel}'

        raw_input = resp_status.get(input_key)
        if not raw_input:
            break
        raw_input_config = resp_config[input_key]

        raw_switch = resp_status[switch_key]
        raw_switch_config = resp_config[switch_key]

        status['inputs'].append({
            'id': raw_input['id'] + 1,
            'name': raw_input_config['name'],
            'state': raw_input['state']
        })
        status['relays'].append({
            'id': raw_switch['id'] + 1,
            'name': raw_switch_config['name'],
            'output': raw_switch['output'],
            'apower': raw_switch['apower'],
            'pf': raw_switch['pf']
        })

    return status

    f'http://{host}/rpc/Input.GetConfig?id=0'  # {"id":0, "name":null, "type":"switch", "invert":true}

    f'http://{host}/rpc/Switch.GetStatus?id=0'  # {"id":0,"state":false}

    f'http://{host}/rpc/Switch.GetConfig?id=0'  # {"id":0, "name":"Pompa 1","in_mode":"detached","initial_state":"off", "auto_on":false, "auto_on_delay":60.00, "auto_off":false, "auto_off_delay": 60.00,"power_limit":20,"voltage_limit":280,"current_limit":16.000}

    f'http://{host}/rpc/Switch.GetStatus?id=0'  # {"id":0, "source":"WS_in", "output":false, "apower":0.0, "voltage":231.7, "current":0.000, "pf":0.00, "aenergy":{"total":123.664,"by_minute":[0.000,0.000,0.000],"minute_ts":1691257210},"temperature":{"tC":44.3, "tF":111.8}}

    f'http://{host}/rpc/Shelly.GetDeviceInfo'  # {"name":null,"id":"shellypro4pm-ec62609ff1f8","mac":"EC62609FF1F8","model":"SPSW-104PE16EU","gen":2,"fw_id":"20220830-132254/0.11.0-gfa1bc37","ver":"0.11.0","app":"Pro4PM","auth_en":false,"auth_domain":null}


async def main(host: str) -> None:
    print(await get_status(host))


if __name__ == '__main__':
    host = sys.argv[1]
    asyncio.run(main(host))
