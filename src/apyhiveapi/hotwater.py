"""Hive Hotwater Module."""
# pylint: skip-file

from .helper.const import HIVETOHA


class HiveHotwater:
    """Hive Hotwater Code.

    Returns:
        object: Hotwater Object.
    """

    hotwaterType = "Hotwater"

    async def get_mode(self, device: dict):
        """Get hotwater current mode.

        Args:
            device (dict): Device to get the mode for.

        Returns:
            str: Return mode.
        """
        state = None
        final = None

        try:
            data = self.session.data.products[device["hiveID"]]
            state = data["state"]["mode"]
            if state == "BOOST":
                state = data["props"]["previous"]["mode"]
            final = HIVETOHA[self.hotwaterType].get(state, state)
        except KeyError as e:
            await self.session.log.error(e)

        return final

    @staticmethod
    async def get_operation_modes():
        """Get heating list of possible modes.

        Returns:
            list: Return list of operation modes.
        """
        return ["SCHEDULE", "ON", "OFF"]

    async def get_boost(self, device: dict):
        """Get hot water current boost status.

        Args:
            device (dict): Device to get boost status for

        Returns:
            str: Return boost status.
        """
        state = None
        final = None

        try:
            data = self.session.data.products[device["hiveID"]]
            state = data["state"]["boost"]
            final = HIVETOHA["Boost"].get(state, "ON")
        except KeyError as e:
            await self.session.log.error(e)

        return final

    async def get_boost_time(self, device: dict):
        """Get hotwater boost time remaining.

        Args:
            device (dict): Device to get boost time for.

        Returns:
            str: Return time remaining on the boost.
        """
        state = None
        if await self.get_boost(device) == "ON":
            try:
                data = self.session.data.products[device["hiveID"]]
                state = data["state"]["boost"]
            except KeyError as e:
                await self.session.log.error(e)

        return state

    async def get_state(self, device: dict):
        """Get hot water current state.

        Args:
            device (dict): Device to get the state for.

        Returns:
            str: return state of device.
        """
        state = None
        final = None

        try:
            data = self.session.data.products[device["hiveID"]]
            state = data["state"]["status"]
            mode_current = await self.get_mode(device)
            if mode_current == "SCHEDULE":
                if await self.get_boost(device) == "ON":
                    state = "ON"
                else:
                    snan = self.session.helper.get_schedule_nnl(data["state"]["schedule"])
                    state = snan["now"]["value"]["status"]

            final = HIVETOHA[self.hotwaterType].get(state, state)
        except KeyError as e:
            await self.session.log.error(e)

        return final

    async def set_mode(self, device: dict, new_mode: str):
        """Set hot water mode.

        Args:
            device (dict): device to update mode.
            new_mode (str): Mode to set the device to.

        Returns:
            boolean: return True/False if boost was successful.
        """
        final = False

        if device["hiveID"] in self.session.data.products:
            await self.session.hive_refresh_tokens()
            data = self.session.data.products[device["hiveID"]]
            resp = await self.session.api.set_state(
                data["type"], device["hiveID"], mode=new_mode
            )
            if resp["original"] == 200:
                final = True
                await self.session.get_devices()

        return final

    async def set_boost_on(self, device: dict, mins: int):
        """Turn hot water boost on.

        Args:
            device (dict): Deice to boost.
            mins (int): Number of minutes to boost it for.

        Returns:
            boolean: return True/False if boost was successful.
        """
        final = False

        if (
            int(mins) > 0
            and device["hiveID"] in self.session.data.products
            and device["deviceData"]["online"]
        ):
            await self.session.hive_refresh_tokens()
            data = self.session.data.products[device["hiveID"]]
            resp = await self.session.api.set_state(
                data["type"], device["hiveID"], mode="BOOST", boost=mins
            )
            if resp["original"] == 200:
                final = True
                await self.session.get_devices()

        return final

    async def set_boost_off(self, device: dict):
        """Turn hot water boost off.

        Args:
            device (dict): device to set boost off

        Returns:
            boolean: return True/False if boost was successful.
        """
        final = False

        if (
            device["hiveID"] in self.session.data.products
            and await self.get_boost(device) == "ON"
            and device["deviceData"]["online"]
        ):
            await self.session.hive_refresh_tokens()
            data = self.session.data.products[device["hiveID"]]
            prev_mode = data["props"]["previous"]["mode"]
            resp = await self.session.api.set_state(
                data["type"], device["hiveID"], mode=prev_mode
            )
            if resp["original"] == 200:
                await self.session.get_devices()
                final = True

        return final


class WaterHeater(HiveHotwater):
    """Water heater class.

    Args:
        Hotwater (object): Hotwater class.
    """

    def __init__(self, session: object = None):
        """Initialise water heater.

        Args:
            session (object, optional): Session to interact with account. Defaults to None.
        """
        self.session = session

    async def get_water_heater(self, device: dict):
        """Update water heater device.

        Args:
            device (dict): device to update.

        Returns:
            dict: Updated device.
        """
        device["deviceData"].update(
            {"online": await self.session.attr.online_offline(device["device_id"])}
        )

        if device["deviceData"]["online"]:

            dev_data = {}
            self.session.helper.device_recovered(device["device_id"])
            data = self.session.data.devices[device["device_id"]]
            dev_data = {
                "hiveID": device["hiveID"],
                "hiveName": device["hiveName"],
                "hiveType": device["hiveType"],
                "haName": device["haName"],
                "haType": device["haType"],
                "device_id": device["device_id"],
                "device_name": device["device_name"],
                "status": {"current_operation": await self.get_mode(device)},
                "deviceData": data.get("props", None),
                "parentDevice": data.get("parent", None),
                "custom": device.get("custom", None),
                "attributes": await self.session.attr.state_attributes(
                    device["device_id"], device["hiveType"]
                ),
            }

            self.session.devices.update({device["hiveID"]: dev_data})
            return self.session.devices[device["hiveID"]]
        else:
            await self.session.log.error_check(
                device["device_id"], "ERROR", device["deviceData"]["online"]
            )
            return device

    async def get_schedule_now_next_later(self, device: dict):
        """Hive get hotwater schedule now, next and later.

        Args:
            device (dict): device to get schedule for.

        Returns:
            dict: return now, next and later schedule.
        """
        state = None

        try:
            mode_current = await self.get_mode(device)
            if mode_current == "SCHEDULE":
                data = self.session.data.products[device["hiveID"]]
                state = self.session.helper.get_schedule_nnl(data["state"]["schedule"])
        except KeyError as e:
            await self.session.log.error(e)

        return state
