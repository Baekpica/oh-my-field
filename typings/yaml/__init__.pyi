from typing import IO

type YamlScalar = str | int | float | bool | None
type YamlKey = YamlScalar | tuple[YamlKey, ...]
type YamlValue = YamlScalar | list[YamlValue] | dict[YamlKey, YamlValue]

def safe_load(stream: str | bytes | IO[str] | IO[bytes], /) -> dict[YamlKey, YamlValue] | None: ...
