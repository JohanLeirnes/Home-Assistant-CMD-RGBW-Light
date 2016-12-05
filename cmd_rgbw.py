"""
Support for custom shell commands to turn a RGBW Light on/off/color/brightness.
For more details about this platform, please refer to the documentation at
******
"""
import logging
import subprocess

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA,
ENTITY_ID_FORMAT)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, EFFECT_COLORLOOP, EFFECT_WHITE, FLASH_LONG,
    SUPPORT_BRIGHTNESS, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, Light, PLATFORM_SCHEMA)

from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_SWITCHES, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_STATE, CONF_BRIGHTNESS, CONF_RGB,
    CONF_COLOR_TEMP)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'CMD RGBW Light'
DEFAULT_BRIGHTNESS_SCALE = 255

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_ON, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_BRIGHTNESS_STATE): cv.string,
    vol.Optional(CONF_BRIGHTNESS_COMMAND): cv.string,
    vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_RGB_STATE): cv.string,
    vol.Optional(CONF_RGB_COMMAND): cv.string,
    vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
})

RGB_BOUNDARY = 40

WHITE = [255, 255, 255]

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return switches controlled by shell commands."""
    devices = config.get(CONF_SWITCHES, {})
    cmdrgbwlight = []

    for object_id, device_config in devices.items():
        value_template = device_config.get(CONF_STATE_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        cmdrgbwlight.append(
            CommandSwitch(
                hass,
                object_id,
                device_config.get(CONF_NAME),
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF),
                device_config.get(CONF_COMMAND_STATE),
                device.config.get(CONF_BRIGHTNESS_STATE),
                device.config.get(CONF_BRIGHTNESS_COMMAND),
                device.config.get(CONF_BRIGHTNESS_VALUE_TEMPLATE),
                device.config.get(CONF_RGB_STATE),
                device.config.get(CONF_RGB_COMMAND),
                device.config.get(CONF_RGB_VALUE_TEMPLATE),
                device.config.get(CONF_FRIENDLY_NAME, object_id),
                device.config.get(CONF_BRIGHTNESS_SCALE),
                value_template
            )
        )

    if not cmdrgbwlight:
        _LOGGER.error("No switches added")
        return False

    add_devices(cmdrgbwlight)


class CommandSwitch(SwitchDevice):
    """Representation a switch that can be toggled using shell commands."""

    def __init__(self, hass, object_id, friendly_name, command_on,
                 command_off, command_state, value_template, brightness_scale):
        """Initialize the switch."""
        self._hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = friendly_name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template
        self._brightness_scale = brightness_scale
        self._supported_features = 0
        self._supported_features |= (
        topic[CONF_RGB_STATE] is not None and SUPPORT_RGB_COLOR)
        self._supported_features |= (
        topic[CONF_BRIGHTNESS_STATE] is not None and
        SUPPORT_BRIGHTNESS)
        self._color = WHITE

    @staticmethod
    def _switch(command):
        """Execute the actual commands."""
        _LOGGER.info('Running command: %s', command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @staticmethod
    def _query_state_value(command):
        """Execute state command for return value."""
        _LOGGER.info('Running state command: %s', command)

        try:
            return_value = subprocess.check_output(command, shell=True)
            return return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error('Command failed: %s', command)

    @staticmethod
    def _query_state_code(command):
        """Execute state command for return code."""
        _LOGGER.info('Running state command: %s', command)
        return subprocess.call(command, shell=True) == 0

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._color

    @property
    def brightness(self):
        """Return the brightness property."""
        return self._brightness

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._command_state is False

    def _query_state(self):
        """Query for state."""
        if not self._command_state:
            _LOGGER.error('No state command specified')
            return
        if self._value_template:
            return CommandSwitch._query_state_value(self._command_state)
        return CommandSwitch._query_state_code(self._command_state)

    def update(self):
        """Update device state."""
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = self._value_template.render_with_possible_json_value(
                    payload)
            self._state = (payload.lower() == "true")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if (CommandSwitch._switch(self._command_on) and
                not self._command_state):
            self._state = True
            self.schedule_update_ha_state()
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self.schedule_update_ha_state()
        if ATTR_RGB_COLOR in kwargs:
            self._color = kwargs[ATTR_RGB_COLOR]
            self.schedule_update_ha_state()
            # White is a special case.
        if min(self._color) > 256 - RGB_BOUNDARY:
            self._color = WHITE
            self.schedule_update_ha_state()
        if ATTR_EFFECT in kwargs:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
              self.repeating = True
              pipeline.append(COLORLOOP)
            if kwargs[ATTR_EFFECT] == EFFECT_WHITE:
              pipeline.white()
              self._color = WHITE


    def turn_off(self, **kwargs):
        """Turn the device off."""
        if (CommandSwitch._switch(self._command_off) and
                not self._command_state):
            self._state = False
            self.schedule_update_ha_state()
