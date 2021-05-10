import glob
import os
import shutil

import pydantic
from pydantic import BaseSettings

from modelkit.assets import errors
from modelkit.assets.log import logger


class LocalDriverSettings(BaseSettings):
    bucket: pydantic.DirectoryPath = pydantic.Field(..., env="ASSETS_BUCKET_NAME")

    class Config:
        extra = "forbid"


class LocalStorageDriver:
    def __init__(self, settings: LocalDriverSettings = None):
        if not settings:
            settings = LocalDriverSettings()
        self.bucket = settings.bucket

    def iterate_objects(self, bucket, prefix=None):
        bucket_path = os.path.join(self.bucket, bucket)
        if not os.path.isdir(bucket_path):
            raise errors.ContainerDoesNotExistError(self, bucket)
        for filename in glob.iglob(
            os.path.join(bucket_path, os.path.join("**", "*")), recursive=True
        ):
            if os.path.isfile(filename):
                yield os.path.relpath(filename, bucket_path)

    def upload_object(self, file_path, bucket, object_name):
        object_path = os.path.join(self.bucket, bucket, *object_name.split("/"))
        object_dir, _ = os.path.split(object_path)

        # delete whatever is locally at the position of the object
        if os.path.isfile(object_path):
            os.remove(object_path)
        if os.path.isdir(object_path):
            shutil.rmtree(object_path)
        if os.path.isfile(object_dir):
            os.remove(object_dir)
        os.makedirs(object_dir, exist_ok=True)

        with open(file_path, "rb") as fsrc:
            with open(object_path, "xb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

    def download_object(self, bucket_name, object_name, destination_path):
        object_path = os.path.join(self.bucket, bucket_name, object_name)
        if not os.path.isfile(object_path):
            logger.error(
                "Object not found.", bucket=bucket_name, object_name=object_name
            )
            raise errors.ObjectDoesNotExistError(
                driver=self, bucket=bucket_name, object_name=object_name
            )

        with open(object_path, "rb") as fsrc:
            with open(destination_path, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

    def delete_object(self, bucket, object_name):
        object_path = os.path.join(self.bucket, bucket, *object_name.split("/"))
        if os.path.exists(object_path):
            os.remove(object_path)

    def exists(self, bucket, object_name):
        return os.path.isfile(
            os.path.join(self.bucket, bucket, *object_name.split("/"))
        )

    def __repr__(self):
        return f"<LocalStorageDriver bucket={self.bucket}>"
