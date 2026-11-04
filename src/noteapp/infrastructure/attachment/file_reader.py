"""Local filesystem reader for user-chosen images, with a size guard before reading."""

import os
import stat

from noteapp.domain.errors import ImageTooLarge, ValidationError
from noteapp.domain.policies.attachment_policy import MAX_IMAGE_BYTES


class LocalImageFileReader:
    def read(self, path: str) -> tuple[bytes, str]:
        if not isinstance(path, str) or not path:
            raise ValidationError("An image file path is required.")
        try:
            if not stat.S_ISREG(os.stat(path).st_mode):
                raise ValidationError("The selected item is not a regular file.")
            if os.stat(path).st_size > MAX_IMAGE_BYTES:
                raise ImageTooLarge("Images larger than 10 MiB are not accepted.")
            with open(path, "rb") as handle:
                data = handle.read(MAX_IMAGE_BYTES + 1)
        except OSError:
            raise ValidationError("The selected file could not be read.") from None
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageTooLarge("Images larger than 10 MiB are not accepted.")
        return data, os.path.basename(path)
