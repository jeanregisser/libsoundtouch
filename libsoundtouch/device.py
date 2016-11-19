"""Bose Soundtouch Device."""

# pylint: disable=too-many-public-methods,too-many-instance-attributes

import logging
from xml.dom import minidom

import requests

_LOGGER = logging.getLogger(__name__)

KEY_PLAY = 'PLAY'
KEY_MUTE = 'MUTE'
KEY_PAUSE = 'PAUSE'
KEY_PLAY_PAUSE = 'PLAY_PAUSE'
KEY_NEXT_TRACK = 'NEXT_TRACK'
KEY_PREVIOUS_TRACK = 'PREV_TRACK'
KEY_POWER = 'POWER'
KEY_VOLUME_UP = 'VOLUME_UP'
KEY_VOLUME_DOWN = 'VOLUME_DOWN'
KEY_SHUFFLE_ON = 'SHUFFLE_ON'
KEY_SHUFFLE_OFF = 'SHUFFLE_OFF'
KEY_REPEAT_ONE = 'REPEAT_ONE'
KEY_REPEAT_ALL = 'REPEAT_ALL'
KEY_REPEAT_OFF = 'REPEAT_OFF'

STATE_STANDBY = 'STANDBY'


def _get_dom_attribute(xml_dom, attribute, default_value=None):
    if attribute in xml_dom.attributes:
        return xml_dom.attributes[attribute].value
    else:
        return default_value


def _get_dom_element_attribute(xml_dom, element, attribute,
                               default_value=None):
    element = _get_dom_element(xml_dom, element)
    if element is not None:
        if attribute in element.attributes:
            return element.attributes[attribute].value
        else:
            return None
    else:
        return default_value


def _get_dom_elements(xml_dom, element):
    return xml_dom.getElementsByTagName(element)


def _get_dom_element(xml_dom, element):
    elements = _get_dom_elements(xml_dom, element)
    if len(elements) > 0:
        return elements[0]
    else:
        return None


def _get_dom_element_value(xml_dom, element, default_value=None):
    element = _get_dom_element(xml_dom, element)
    if element is not None and element.firstChild is not None:
        return element.firstChild.nodeValue.strip()
    else:
        return default_value


class SoundTouchDevice:
    """Bose SoundTouch Device."""

    def __init__(self, host, port=8090):
        """Create a new Soundtouch device.

        :param host: Host of the device
        :param port: Port of the device. Default 8090

        """
        self._host = host
        self._port = port
        self.__init_config()
        self._status = None
        self._volume = None
        self._zone_status = None
        self._presets = []

    def __init_config(self):
        response = requests.get(
            "http://" + self._host + ":" + str(self._port) + "/info")
        dom = minidom.parseString(response.text)
        self._config = Config(dom)

    def refresh_status(self):
        """Refresh status state."""
        response = requests.get(
            "http://" + self._host + ":" + str(self._port) + "/now_playing")
        dom = minidom.parseString(response.text)
        self._status = Status(dom)

    def refresh_volume(self):
        """Refresh volume state."""
        response = requests.get(
            "http://" + self._host + ":" + str(self._port) + "/volume")
        dom = minidom.parseString(response.text)
        self._volume = Volume(dom)

    def refresh_presets(self):
        """Refresh presets."""
        response = requests.get(
            "http://" + self._host + ":" + str(self._port) + "/presets")
        dom = minidom.parseString(response.text)
        self._presets = []
        for preset in _get_dom_elements(dom, "preset"):
            self._presets.append(Preset(preset))

    def refresh_zone_status(self):
        """Refresh Zone Status."""
        response = requests.get(
            "http://" + self._host + ":" + str(self._port) + "/getZone")
        dom = minidom.parseString(response.text)
        # self._zone_status = None
        if len(_get_dom_elements(dom, "member")) != 0:
            self._zone_status = ZoneStatus(dom)

    def select_preset(self, preset):
        """Play selected preset.

        :param preset Selected preset.
        """
        requests.post(
            'http://' + self._host + ":" + str(self._port) + '/select',
            preset.source_xml)

    def _create_zone(self, slaves):
        if len(slaves) <= 0:
            raise NoSlavesException()
        request_body = '<zone master="%s" senderIPAddress="%s">' % (
            self.config.device_id, self.config.device_ip
        )
        for slave in slaves:
            request_body += '<member ipaddress="%s">%s</member>' % (
                slave.config.device_ip, slave.config.device_id)
        request_body += '</zone>'
        return request_body

    def _get_zone_request_body(self, slaves):
        if len(slaves) <= 0:
            raise NoSlavesException()
        request_body = '<zone master="%s">' % self.config.device_id
        for slave in slaves:
            request_body += '<member ipaddress="%s">%s</member>' % (
                slave.config.device_ip, slave.config.device_id)
        request_body += '</zone>'
        return request_body

    def create_zone(self, slaves):
        """Create a zone (multi-room) on a master and play on specified slaves.

        :param slaves: List of slaves. Can not be empty

        """
        request_body = self._create_zone(slaves)
        _LOGGER.info("Creating multi-room zone with master device %s",
                     self.config.name)
        requests.post("http://" + self.host + ":" + str(
            self.port) + "/setZone",
                      request_body)

    def add_zone_slave(self, slaves):
        """
        Add slave(s) to and existing zone (multi-room).

        Zone must already exist and slaves array can not be empty.

        :param slaves: List of slaves. Can not be empty
        """
        self.refresh_zone_status()
        if self.zone_status is None:
            raise NoExistingZoneException()
        request_body = self._get_zone_request_body(slaves)
        _LOGGER.info("Adding slaves to multi-room zone with master device %s",
                     self.config.name)
        requests.post(
            "http://" + self.host + ":" + str(
                self.port) + "/addZoneSlave",
            request_body)

    def remove_zone_slave(self, slaves):
        """
        Remove slave(s) from and existing zone (multi-room).

        Zone must already exist and slaves list can not be empty.
        Note: If removing last slave, the zone will be deleted and you'll have
        to create a new one. You will not be able to add a new slave anymore.

        :param slaves: List of slaves to remove

        """
        self.refresh_zone_status()
        if self.zone_status is None:
            raise NoExistingZoneException()
        request_body = self._get_zone_request_body(slaves)
        _LOGGER.info("Removing slaves from multi-room zone with master " +
                     "device %s", self.config.name)
        requests.post(
            "http://" + self.host + ":" + str(
                self.port) + "/removeZoneSlave", request_body)

    def _send_key(self, key):
        action = '/key'
        press = '<key state="press" sender="Gabbo">%s</key>' % key
        release = '<key state="release" sender="Gabbo">%s</key>' % key
        requests.post('http://' + self._host + ":" +
                      str(self._port) + action, press)
        requests.post('http://' + self._host + ":" +
                      str(self._port) + action, release)

    @property
    def host(self):
        """Host of the device."""
        return self._host

    @property
    def port(self):
        """API port of the device."""
        return self._port

    @property
    def config(self):
        """Get config object."""
        return self._config

    @property
    def status(self):
        """Get status object."""
        return self._status

    @property
    def volume(self):
        """Get volume object."""
        return self._volume

    @property
    def zone_status(self):
        """Get Zone Status."""
        return self._zone_status

    @property
    def presets(self):
        """Presets."""
        return self._presets

    def set_volume(self, level):
        """Set volume level: from 0 to 100."""
        action = '/volume'
        volume = '<volume>%s</volume>' % level
        requests.post('http://' + self._host + ":" + str(self._port) + action,
                      volume)
        self.refresh_volume()

    def mute(self):
        """Mute/Un-mute volume."""
        self._send_key(KEY_MUTE)
        self.refresh_volume()

    def volume_up(self):
        """Volume up."""
        self._send_key(KEY_VOLUME_UP)
        self.refresh_volume()

    def volume_down(self):
        """Volume down."""
        self._send_key(KEY_VOLUME_DOWN)
        self.refresh_volume()

    def next_track(self):
        """Switch to next track."""
        self._send_key(KEY_NEXT_TRACK)

    def previous_track(self):
        """Switch to previous track."""
        self._send_key(KEY_PREVIOUS_TRACK)

    def pause(self):
        """Pause."""
        self._send_key(KEY_PAUSE)
        self.refresh_status()

    def play(self):
        """Play."""
        self._send_key(KEY_PLAY)
        self.refresh_status()

    def play_pause(self):
        """Toggle play status."""
        self._send_key(KEY_PLAY_PAUSE)
        self.refresh_status()

    def repeat_off(self):
        """Turn off repeat."""
        self._send_key(KEY_REPEAT_OFF)
        self.refresh_status()

    def repeat_one(self):
        """Repeat one. Doesn't work."""
        self._send_key(KEY_REPEAT_ONE)
        self.refresh_status()

    def repeat_all(self):
        """Repeat all."""
        self._send_key(KEY_REPEAT_ALL)
        self.refresh_status()

    def shuffle(self, shuffle):
        """Shuffle on/off.

        :param shuffle: Boolean on/off
        """
        if shuffle:
            self._send_key(KEY_SHUFFLE_ON)
        else:
            self._send_key(KEY_SHUFFLE_OFF)
        self.refresh_status()

    def power_on(self):
        """Power on device."""
        self.refresh_status()
        if self.status.source == STATE_STANDBY:
            self._send_key(KEY_POWER)

    def power_off(self):
        """Power off device."""
        self.refresh_status()
        if self.status.source != STATE_STANDBY:
            self._send_key(KEY_POWER)


class Config:
    """Soundtouch device configuration."""

    def __init__(self, xml_dom):
        """Create a new configuration.

        :param xml_dom: Configuration XML DOM
        """
        self._id = _get_dom_element_attribute(xml_dom, "info", "deviceID")
        self._name = _get_dom_element_value(xml_dom, "name")
        self._type = _get_dom_element_value(xml_dom, "type")
        self._account_uuid = _get_dom_element_value(xml_dom,
                                                    "margeAccountUUID")
        self._module_type = _get_dom_element_value(xml_dom, "moduleType")
        self._variant = _get_dom_element_value(xml_dom, "variant")
        self._variant_mode = _get_dom_element_value(xml_dom, "variantMode")
        self._country_code = _get_dom_element_value(xml_dom, "countryCode")
        self._region_code = _get_dom_element_value(xml_dom, "regionCode")
        self._networks = []
        for network in xml_dom.getElementsByTagName("networkInfo"):
            self._networks.append(Network(network))
        self._components = []
        for components in _get_dom_elements(xml_dom, "components"):
            for component in _get_dom_elements(components, "component"):
                self._components.append(Component(component))

    @property
    def device_id(self):
        """Device ID."""
        return self._id

    @property
    def name(self):
        """Device name."""
        return self._name

    @property
    def type(self):
        """Device type."""
        return self._type

    @property
    def networks(self):
        """Network."""
        return self._networks

    @property
    def components(self):
        """Components."""
        return self._components

    @property
    def account_uuid(self):
        """Account UUID."""
        return self._account_uuid

    @property
    def module_type(self):
        """Module type."""
        return self._module_type

    @property
    def variant(self):
        """Variant."""
        return self._variant

    @property
    def variant_mode(self):
        """Variant mode."""
        return self._variant_mode

    @property
    def country_code(self):
        """Country code."""
        return self._country_code

    @property
    def region_code(self):
        """Region code."""
        return self._region_code

    @property
    def device_ip(self):
        """Ip."""
        network = next(
            (network for network in self._networks if network.type == "SMSC"),
            next((network for network in self._networks), None))
        return network.ip_address if network else None

    @property
    def mac_address(self):
        """Mac address."""
        network = next(
            (network for network in self._networks if network.type == "SMSC"),
            next((network for network in self._networks), None))
        return network.mac_address if network else None


class Network:
    """Soundtouch network configuration."""

    def __init__(self, network_dom):
        """Create a new Network.

        :param network_dom: Network configuration XML DOM
        """
        self._type = network_dom.attributes["type"].value
        self._mac_address = _get_dom_element_value(network_dom, "macAddress")
        self._ip_address = _get_dom_element_value(network_dom, "ipAddress")

    @property
    def type(self):
        """Type."""
        return self._type

    @property
    def mac_address(self):
        """Mac Address."""
        return self._mac_address

    @property
    def ip_address(self):
        """IP Address."""
        return self._ip_address


class Component:
    """Soundtouch component."""

    def __init__(self, component_dom):
        """Create a new Component.

        :param component_dom: Component XML DOM
        """
        self._category = _get_dom_element_value(component_dom,
                                                "componentCategory")
        self._software_version = _get_dom_element_value(component_dom,
                                                        "softwareVersion")
        self._serial_number = _get_dom_element_value(component_dom,
                                                     "serialNumber")

    @property
    def category(self):
        """Category."""
        return self._category

    @property
    def software_version(self):
        """Software version."""
        return self._software_version

    @property
    def serial_number(self):
        """Serial number."""
        return self._serial_number


class Status:
    """Soundtouch device status."""

    def __init__(self, xml_dom):
        """Create a new device status.

        :param xml_dom: Status XML DOM
        """
        self._source = _get_dom_element_attribute(xml_dom, "nowPlaying",
                                                  "source")
        self._content_item = ContentItem(
            _get_dom_element(xml_dom, "ContentItem"))
        self._track = _get_dom_element_value(xml_dom, "track")
        self._artist = _get_dom_element_value(xml_dom, "artist")
        self._album = _get_dom_element_value(xml_dom, "album")
        image_status = _get_dom_element_attribute(xml_dom, "art",
                                                  "artImageStatus")
        if image_status == "IMAGE_PRESENT":
            self._image = _get_dom_element_value(xml_dom, "art")
        else:
            self._image = None

        duration = _get_dom_element_attribute(xml_dom, "time", "total")
        self._duration = int(duration) if duration is not None else None
        position = _get_dom_element_value(xml_dom, "time")
        self._position = int(position) if position is not None else None
        self._play_status = _get_dom_element_value(xml_dom, "playStatus")
        self._shuffle_setting = _get_dom_element_value(xml_dom,
                                                       "shuffleSetting")
        self._repeat_setting = _get_dom_element_value(xml_dom, "repeatSetting")
        self._stream_type = _get_dom_element_value(xml_dom, "streamType")
        self._track_id = _get_dom_element_value(xml_dom, "trackID")
        self._station_name = _get_dom_element_value(xml_dom, "stationName")
        self._description = _get_dom_element_value(xml_dom, "description")
        self._station_location = _get_dom_element_value(xml_dom,
                                                        "stationLocation")

    @property
    def source(self):
        """Source."""
        return self._source

    @property
    def content_item(self):
        """Content item."""
        return self._content_item

    @property
    def track(self):
        """Track."""
        return self._track

    @property
    def artist(self):
        """Artist."""
        return self._artist

    @property
    def album(self):
        """Album name."""
        return self._album

    @property
    def image(self):
        """Image URL."""
        return self._image

    @property
    def duration(self):
        """Duration."""
        return self._duration

    @property
    def position(self):
        """Position."""
        return self._position

    @property
    def play_status(self):
        """Status."""
        return self._play_status

    @property
    def shuffle_setting(self):
        """Shuffle setting."""
        return self._shuffle_setting

    @property
    def repeat_setting(self):
        """Repeat setting."""
        return self._repeat_setting

    @property
    def stream_type(self):
        """Stream type."""
        return self._stream_type

    @property
    def track_id(self):
        """Track id."""
        return self._track_id

    @property
    def station_name(self):
        """Station name."""
        return self._station_name

    @property
    def description(self):
        """Description."""
        return self._description

    @property
    def station_location(self):
        """Station location."""
        return self._station_location


class ContentItem:
    """Content item."""

    def __init__(self, xml_dom):
        """Create a new content item.

        :param xml_dom: Content item XML DOM
        """
        self._name = _get_dom_element_value(xml_dom, "itemName")
        self._source = _get_dom_attribute(xml_dom, "source")
        self._type = _get_dom_attribute(xml_dom, "type")
        self._location = _get_dom_attribute(xml_dom, "location")
        self._source_account = _get_dom_attribute(xml_dom, "sourceAccount")
        self._is_presetable = _get_dom_attribute(xml_dom,
                                                 "isPresetable") == 'true'

    @property
    def name(self):
        """Name."""
        return self._name

    @property
    def source(self):
        """Source."""
        return self._source

    @property
    def type(self):
        """Type."""
        return self._type

    @property
    def location(self):
        """Location."""
        return self._location

    @property
    def source_account(self):
        """Source account."""
        return self._source_account

    @property
    def is_presetable(self):
        """True if presetable."""
        return self._is_presetable


class Volume:
    """Volume configuration."""

    def __init__(self, xml_dom):
        """Create a new volume configuration.

        :param xml_dom: Volume configuration XML DOM
        """
        self._actual = int(_get_dom_element_value(xml_dom, "actualvolume"))
        self._target = int(_get_dom_element_value(xml_dom, "targetvolume"))
        self._muted = _get_dom_element_value(xml_dom, "muteenabled") == "true"

    @property
    def actual(self):
        """Actual volume level."""
        return self._actual

    @property
    def target(self):
        """Target volume level."""
        return self._target

    @property
    def muted(self):
        """True if volume is muted."""
        return self._muted


class Preset:
    """Preset."""

    def __init__(self, preset_dom):
        """Create a preset configuration.

        :param preset_dom: Preset configuration XML DOM
        """
        self._name = _get_dom_element_value(preset_dom, "itemName")
        self._id = _get_dom_attribute(preset_dom, "id")
        self._source = _get_dom_element_attribute(preset_dom, "ContentItem",
                                                  "source")
        self._type = _get_dom_element_attribute(preset_dom, "ContentItem",
                                                "type")
        self._location = _get_dom_element_attribute(preset_dom, "ContentItem",
                                                    "location")
        self._source_account = _get_dom_element_attribute(preset_dom,
                                                          "ContentItem",
                                                          "sourceAccount")
        self._is_presetable = \
            _get_dom_element_attribute(preset_dom,
                                       "ContentItem",
                                       "isPresetable") == "true"
        self._source_xml = _get_dom_element(preset_dom, "ContentItem").toxml()

    @property
    def name(self):
        """Name."""
        return self._name

    @property
    def preset_id(self):
        """Id."""
        return self._id

    @property
    def source(self):
        """Source."""
        return self._source

    @property
    def type(self):
        """Type."""
        return self._type

    @property
    def location(self):
        """Location."""
        return self._location

    @property
    def source_account(self):
        """Source account."""
        return self._source_account

    @property
    def is_presetable(self):
        """True if is presetable."""
        return self._is_presetable

    @property
    def source_xml(self):
        """XML source."""
        return self._source_xml


class ZoneStatus:
    """Zone Status."""

    def __init__(self, zone_dom):
        """Create a new Zone status configuration.

        :param zone_dom: Zone status configuration XML DOM
        """
        self._master_id = _get_dom_element_attribute(zone_dom, "zone",
                                                     "master")
        self._master_ip = _get_dom_element_attribute(zone_dom, "zone",
                                                     "senderIPAddress")
        self._is_master = self._master_ip is None
        members = _get_dom_elements(zone_dom, "member")
        self._slaves = []
        for member in members:
            self._slaves.append(ZoneSlave(member))

    @property
    def master_id(self):
        """Master id."""
        return self._master_id

    @property
    def is_master(self):
        """True if current device is the zone master."""
        return self._is_master

    @property
    def master_ip(self):
        """Master ip."""
        return self._master_ip

    @property
    def slaves(self):
        """Zone slaves."""
        return self._slaves


class ZoneSlave:
    """Zone Slave."""

    def __init__(self, member_dom):
        """Create a new Zone slave configuration.

        :param member_dom: Slave XML DOM
        """
        self._ip = _get_dom_attribute(member_dom, "ipaddress")
        self._role = _get_dom_attribute(member_dom, "role")

    @property
    def device_ip(self):
        """Slave ip."""
        return self._ip

    @property
    def role(self):
        """Slave role."""
        return self._role


class SoundtouchException(Exception):
    """Parent Soundtouch Exception."""

    def __init__(self):
        """Soundtouch Exception."""
        super(SoundtouchException, self).__init__()


class NoExistingZoneException(SoundtouchException):
    """Exception while trying to add slave(s) without existing zone."""

    def __init__(self):
        """NoExistingZoneException."""
        super(NoExistingZoneException, self).__init__()


class NoSlavesException(SoundtouchException):
    """Exception while managing multi-room actions without valid slaves."""

    def __init__(self):
        """NoSlavesException."""
        super(NoSlavesException, self).__init__()