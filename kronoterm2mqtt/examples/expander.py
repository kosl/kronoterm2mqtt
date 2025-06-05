from kronoterm2mqtt.pyetera_uart_bridge import EteraUartBridge
import asyncio


async def main():
    etera = EteraUartBridge('/dev/ttyUSB1')

    async def etera_reset():
        print('Device just reset...')
        await etera.ready()
        print('Device is ready')

    etera.set_device_reset_handler(etera_reset)

    async def example_motors():
        direction = True
        await etera.ready()

        await etera.move_motor(0, EteraUartBridge.Direction.CLOCKWISE, 120 * 1000)  # clockwise for 120 seconds

        while True:
            moves = []
            try:
                for i in range(4):
                    moves.append(
                        etera.move_motor(
                            i,
                            (
                                EteraUartBridge.Direction.CLOCKWISE
                                if direction
                                else EteraUartBridge.Direction.COUNTER_CLOCKWISE
                            ),
                            1000,
                        )
                    )
                await asyncio.gather(*moves)
            except EteraUartBridge.DeviceException as e:
                print('Motor move error', e)
                await asyncio.sleep(1)
            finally:
                direction = not direction

    async def example_relays():
        state = True
        await etera.ready()

        while True:
            relays = []
            try:
                for i in range(8):
                    relays.append(etera.set_relay(i, state))
                await asyncio.gather(*relays)
            except EteraUartBridge.DeviceException as e:
                print('Relay switch error', e)
                await asyncio.sleep(1)
            finally:
                state = not state
                await asyncio.sleep(1)

    async def example_temp():
        await etera.ready()
        print(f'Sensors {await etera.get_sensors()}')
        while True:
            try:
                temps = await etera.get_temperatures()
                print(temps)
            except EteraUartBridge.DeviceException as e:
                print('Get temp error', e)
            finally:
                await asyncio.sleep(1)

    await asyncio.gather(
        example_motors(),
        example_relays(),
        example_temp(),
        etera.run_forever()
    )

asyncio.run(main())
