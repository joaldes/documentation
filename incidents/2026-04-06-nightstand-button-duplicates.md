# Nightstand Button Duplicate Messages

**Last Updated**: 2026-04-06
**Related Systems**: Zigbee2MQTT, SmartThings Buttons (IM6001-BTP01), Node-RED

## Summary
Both nightstand buttons (Alec + Meghan) were sending 1-3 duplicate Zigbee messages per single press, causing lights to toggle multiple times. Root cause was degraded Zigbee routing — buttons were communicating directly to the coordinator with near-zero link quality instead of through a nearby router. Fixed by re-pairing both buttons.

## Problem
- Single button press would fire 1, 2, or 3 events in Z2M at ~1.77 second intervals
- This caused Node-RED automations to toggle nightstand lights multiple times per press
- Issue started within the last few weeks — was not always present

## Investigation
- History data showed duplicate events arriving at consistent ~1.77s intervals — characteristic of Zigbee radio retransmission (button not receiving ACKs)
- Z2M network map showed Alec Nightstand Button routing **directly to the coordinator** with LQI of 0 on the parent link (purple line)
- An under-bed accent light (Zigbee router) was nearby but the button wasn't using it
- Z2M debounce was considered but rejected — it delays the first message
- Node-RED dedup was considered as a stopgap but root cause fix was preferred
- Reconfigure via Z2M failed — signal too weak to complete the bind

## Solution
Re-paired both buttons:
1. Removed battery, reinserted to enter pairing mode (alternating red/green LED)
2. Enabled Permit Join in Z2M
3. Paired each button near the coordinator, then returned to nightstand
4. Buttons re-joined the mesh and found proper routing through nearby router
5. Removed any debounce settings that had been tested
6. No changes to Node-RED flow required — restored to original configuration

## Verification
- Press each button — single event fires in Z2M
- Lights respond correctly without double-toggling
