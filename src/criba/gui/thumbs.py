"""Miniaturas de los PDF para QML: ``image://thumb/<ruta codificada>``."""

import logging
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

from criba.render.thumbnail import first_page_png

log = logging.getLogger(__name__)
DEFAULT_WIDTH = 360


class ThumbnailProvider(QQuickImageProvider):
    """Renderiza la primera página de un PDF (en el hilo de imágenes de QML)."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, image_id: str, size: QSize, requested: QSize) -> QImage:
        """Devuelve la miniatura o una imagen vacía si el PDF no abre."""
        path = Path(unquote(image_id.split("?", 1)[0]))
        width = requested.width() if requested.width() > 0 else DEFAULT_WIDTH
        try:
            image = QImage.fromData(first_page_png(path, width))
        except OSError:
            log.info("Sin miniatura para %s", path.name)
            image = QImage()
        if size is not None and not image.isNull():
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image
