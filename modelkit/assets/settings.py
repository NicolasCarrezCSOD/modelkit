import os
import re
from typing import Optional, Union

import pydantic
from pydantic import BaseModel, BaseSettings, root_validator, validator

from modelkit.assets.drivers.gcs import GCSDriverSettings
from modelkit.assets.drivers.local import LocalDriverSettings
from modelkit.assets.drivers.s3 import S3DriverSettings
from modelkit.assets.errors import InvalidAssetSpecError

SUPPORTED_STORAGE_PROVIDERS = {"s3", "s3ssm", "gcs", "local"}


class DriverSettings(BaseSettings):
    storage_provider: Optional[str] = None
    settings: Optional[
        Union[GCSDriverSettings, S3DriverSettings, LocalDriverSettings]
    ] = None

    @root_validator(pre=True)
    @classmethod
    def dispatch_settings(cls, fields):
        storage_provider = fields.pop("storage_provider", None) or os.getenv(
            "STORAGE_PROVIDER", "gcs"
        )
        if storage_provider not in SUPPORTED_STORAGE_PROVIDERS:
            raise ValueError(f"Unkown storage provider `{storage_provider}`.")
        if storage_provider == "gcs":
            settings = GCSDriverSettings(**fields)
        if storage_provider in ("s3", "s3ssm"):
            settings = S3DriverSettings(**fields)
        if storage_provider == "local":
            settings = LocalDriverSettings(**fields)
        return {"storage_provider": storage_provider, "settings": settings}


NAME_RE = r"[a-z0-9]([a-z0-9\-\_\.]*[a-z0-9])?"


class AssetsManagerSettings(BaseSettings):
    driver_settings: Optional[DriverSettings] = None

    working_dir: pydantic.DirectoryPath = pydantic.Field(None, env="WORKING_DIR")
    timeout_s: float = pydantic.Field(5 * 60, env="ASSETSMANAGER_TIMEOUT_S")
    assetsmanager_prefix: str = pydantic.Field("assets-v3", env="ASSETS_PREFIX")

    @validator("driver_settings", always=True)
    @classmethod
    def default_driver_settings(cls, v):
        return v or DriverSettings()

    @validator("working_dir")
    @classmethod
    def is_env_field_provided(v, field):
        if not v:
            raise ValueError(
                f"env var {field.field_info.extra['env']} must be provided"
            )
        return v

    class Config:
        env_prefix = ""
        case_sensitive = True
        extra = "forbid"


VERSION_SPEC_RE = r"(?P<major_version>[0-9]+)(\.(?P<minor_version>[0-9]+))?"

ASSET_NAME_RE = r"[a-z0-9]([a-z0-9\-\_\.\/]*[a-z0-9])?"

REMOTE_ASSET_RE = (
    f"^(?P<name>{ASSET_NAME_RE})"
    rf"(:{VERSION_SPEC_RE})?(\[(?P<sub_part>(\/?{ASSET_NAME_RE})+)\])?$"
)


class AssetSpec(BaseModel):
    name: str
    major_version: Optional[str]
    minor_version: Optional[str]
    sub_part: Optional[str]

    @validator("name")
    @classmethod
    def is_name_valid(cls, v):
        if not re.fullmatch(ASSET_NAME_RE, v or ""):
            raise ValueError(
                f"Invalid name `{v}`, can only contain [a-z], [0-9], [/], [-] or [_]"
            )
        return v

    @validator("major_version")
    @classmethod
    def is_version_valid(cls, v):
        if v:
            if not re.fullmatch("^[0-9]+$", v):
                raise ValueError(f"Invalid asset version `{v}`")
        return v

    @validator("minor_version")
    @classmethod
    def has_major_version(cls, v, values):
        if v:
            if not values.get("major_version"):
                raise ValueError(
                    "Cannot specify a minor version without a major version."
                )
        return v

    @staticmethod
    def from_string(s):
        m = re.match(REMOTE_ASSET_RE, s)
        if not m:
            raise InvalidAssetSpecError(s)
        return AssetSpec(**m.groupdict())

    class Config:
        extra = "forbid"
