"""
Support for get almost any status information from an AVM Fritz!Box router.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fritzbox_status/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS, STATE_UNAVAILABLE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

from requests.exceptions import RequestException

REQUIREMENTS = ['fritzconnection==0.6.5']

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_IP = '169.254.1.1'  # This IP is valid for all FRITZ!Box routers.

ATTR_IS_CONNECTED = 'is_connected'
ATTR_WLAN1_STATE = 'WLAN1_State'
ATTR_WLAN1_SSID = 'WLAN1_SSID'
ATTR_WLAN2_STATE = 'WLAN2_State'
ATTR_WLAN2_SSID = 'WLAN2_SSID'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

STATE_ONLINE = 'online'
STATE_OFFLINE = 'offline'

ICON = 'mdi:web'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the FRITZ!Box status sensors."""
    # pylint: disable=import-error
    import fritzconnection as fconn
    from fritzconnection.fritzconnection import FritzConnectionException

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    fc = fconn.FritzConnection(address=host, user=username, password=password)
    try:
        fstatus = fconn.FritzStatus(fc)
    except (ValueError, TypeError, FritzConnectionException):
        fstatus = None

    if fstatus is None:
        _LOGGER.error("Failed to establish connection to FRITZ!Box: %s", host)
        return 1
    else:
        _LOGGER.info("Successfully connected to FRITZ!Box")

    add_devices([FritzboxStateSensor(fc)], True)


class FritzboxStateSensor(Entity):
    """Implementation of a fritzbox state sensor."""

    def __init__(self, fc):
        """Initialize the sensor."""
        self._name = 'fritz_status'
        self._fc = fc
        self._state = STATE_UNAVAILABLE
        self._is_linked = None
        self._wlan1_state = None
        self._wlan1_ssid = None
        self._wlan2_state = None
        self._wlan2_ssid = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        # Don't return attributes if FritzBox is unreachable
        if self._state == STATE_UNAVAILABLE:
            return {}
        attr = {
            ATTR_IS_CONNECTED: self._is_connected,
            ATTR_WLAN1_STATE: self._wlan1_state,
            ATTR_WLAN1_SSID: self._wlan1_ssid,
            ATTR_WLAN2_STATE: self._wlan2_state,
            ATTR_WLAN2_SSID: self._wlan2_ssid,
        }
        return attr

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Retrieve information from the FritzBox."""
        try:
            self._is_connected = self._fc.call_action('WANPPPConnection', 'GetStatusInfo')['NewConnectionStatus'] == 'Connected'
            self._wlan1_state = self._fc.call_action("WLANConfiguration", "GetInfo")["NewStatus"]
            self._wlan1_ssid = self._fc.call_action("WLANConfiguration", "GetInfo")["NewSSID"]
            self._wlan2_state = self._fc.call_action("WLANConfiguration:2", "GetInfo")["NewStatus"]
            self._wlan2_ssid = self._fc.call_action("WLANConfiguration:2", "GetInfo")["NewSSID"]
            self._state = STATE_ONLINE if self._is_connected else STATE_OFFLINE
        except RequestException as err:
            self._state = STATE_UNAVAILABLE
            _LOGGER.warning("Could not reach FRITZ!Box: %s", err)
