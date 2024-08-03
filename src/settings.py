from typing import Any, Union

import tomlkit


class Settings:
    """
    The a settings class.
    """

    _path: str = "settings.toml"
    with open(_path, "r") as f:
        _settings: dict = tomlkit.parse(f.read())

    @classmethod
    def _load_settings(cls) -> dict:
        """
        Load the settings file.
        This is an internal method and should not be called directly.

        :raises TOMLDecodeError: Raised when the settings is invalid.
        :raises FileNotFoundError: Raised when the file is not found.

        :return: The settings file.
        :rtype: dict
        """
        with open(cls._path, "r") as f:
            return tomlkit.parse(f.read())

    @classmethod
    def get(cls, key: str, default: Any = None) -> Union[str, Any]:
        """
        Get a key from the settings file.

        :param key: The key to get.
        :type key: str
        :param default: The default value if the key is not found.
        :type default: Any, optional

        :return: The value of the key.
        :rtype: str, Any
        """
        return cls._settings.get(key, default)

    @classmethod
    def reload(cls) -> None:
        """
        Reload the settings file.
        """
        cls._settings = cls._load_settings()

    def __getitem__(self, key: str) -> Any:
        """
        Get a key from the settings file.

        :param key: The key to get.
        :type key: str

        :return: The value of the key.
        :rtype: Any
        """
        return self._settings[key]
