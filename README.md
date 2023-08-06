# Overview
Connect to IoT devices and send metrics data to cloudwatch for monitoring and alarms. This background application can run on Raspberry PI or other low power SBC.

### Supported metrics
- **NetPing** - network ping of LAN or internet devices (network and power health).
- **SmartSwitch** - state of Shelly smart switch.
- **SmartRelay** - state of Shelly smart relay.
- **MeterVoltage** - voltage value from smart relay or PZEM-017 meter device.
- **MeterCurrent** - current value from smart relay or PZEM-017 meter device.
- **MeterEnergy** - energy value from smart relay or PZEM-017 meter device.

### Applications
- Remote solar system monitoring and security

### Why AWS CloudWatch
While I am personally conscious of vendor lock-in, CloudWatch and other closely integrated aws services (SNS, SQS, Lambda) provide a serverless way to easily visualize data over time and get almost real-time alerts via email or phone SMS. Reliable timely alerting is particularly useful as remote solar systems are vulnerable to theft and damage. With a small personal installation, the cloud costs amount less than $5 monthly.

# Installation
- Create `.env` file with the necessary environment variables.
- Run `docker-compose up -d`.

# TODO
- Re-architect with a plug-in system to easily add device interfaces and custom metrics
