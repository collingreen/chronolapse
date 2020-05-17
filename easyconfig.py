"""
EasyConfig

Simple configuration management. Originally created for the Chronolapse project.

Author: Collin Green
"""

import json


class EasyConfig(object):
    """
    Object to manage configuration changes, including automatically
    saving persisting changes and updating UI.

    All config should be in a section, then key->value.

    Example:
        config = EasyConfig(filepath, defaults={'main': {'option': value} })
    """

    def __init__(self, filepath, defaults={}):
        self._filepath = filepath
        self._config = defaults
        self._callbacks = {}

    def get(self, section, key, default=None):
        """
        Returns the value at section[key] or the default if not found.
        """
        if section not in self._config:
            return default
        if key not in self._config[section]:
            return default
        return self._config[section][key]

    def add_listener(self, section, key, callback, fire_now=True):
        """
        Adds a callback for whenever the given key changes. Callback
        is called with the new value at self._config[section][key].
        """
        # add section to callbacks if necessary
        if section not in self._callbacks:
            self._callbacks[section] = {}

        # add key to section if necessary
        if key not in self._callbacks[section]:
            self._callbacks[section][key] = []

        # add callback
        if callback not in self._callbacks[section][key]:
            self._callbacks[section][key].append(callback)

        # fire callback if fire_now is True
        if fire_now:
            if section in self._config and key in self._config[section]:
                callback(self._config[section][key])

    def update(self, section, key, value, notify=True, batch=False):
        """
        Sets the value for the given section and key.
        Notifies any listeners bound to the same section and key.
        """
        # add section if necessary
        if section not in self._config:
            self._config[section] = {}

        # set value at key
        self._config[section][key] = value

        # notifies any listeners bound to this key
        if notify:
            if section in self._callbacks and key in self._callbacks[section]:
                for callback in self._callbacks[section][key]:
                    callback(value)

        # writes the updated config
        if not batch:
            self.persist()

    def updateBatch(self, section, config, notify=True, persist=True):
        for key, value in config.items():
            self.update(section, key, value, notify=notify, batch=True)

        if persist:
            self.persist()

    def persist(self):
        """
        Writes the config to self._filepath using self._encode. Does
        ZERO exception handling.
        """
        with open(self._filepath, 'w+') as f:
            f.write(self._encode())

    def _encode(self):
        """
        Called by persist to encode the configuration file contents.
        Subclasses should overwrite this to get custom functionality or to
        support persisting information that json.dumps cannot handle.
        """
        return json.dumps(self._config)

    def load(self, update_existing_config=True, notify_all=True):
        """
        Reads the config from self._filepath using standard json.loads. Does
        ZERO exception handling.
        If update_existing_config is True, the loaded config file will update
        the existing config dictionary. If False, the existing config will
        be completely replaced.

        If notify_all is True, callbacks are called for each key.
        """
        with open(self._filepath, 'r') as f:
            config_contents = f.read()
            new_config = {}
            if len(config_contents):
                try:
                    new_config = self._decode(config_contents)
                except:pass

            # if update_existing_config, update instead of replace
            if update_existing_config:
                for section in new_config.keys():
                    if section in self._config:
                        self._config[section].update(new_config[section])
                    else:
                        self._config[section] = new_config[section]

            # directly replace all the config with the loaded config contents
            else:
                self._config = new_config

        # call every callback if applicable
        if notify_all:
            self.notify_all()

    def _decode(self, content):
        """
        Called by load to decode the configuration file contents. Subclasses
        should overwrite this to get custom functionality or to support
        perstisting information that json.loads cannot handle.
        """
        return json.loads(content)

    def notify_all(self):
        """
        Calls every callback for its target key if available.
        """
        for section, keydict in self._callbacks.items():
            for key, callbacks in keydict.items():
                if section in self._config and key in self._config[section]:
                    value = self._config[section][key]
                    for callback in callbacks:
                        callback(value)

    def __str__(self):
        return str(self._config)
