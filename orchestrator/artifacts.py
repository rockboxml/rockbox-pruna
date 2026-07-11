"""
Content-addressed artifact store.

Skills produce bytes; the store hashes them, writes them under ``ARTIFACT_DIR``,
and hands back a lightweight :class:`MediaArtifact` reference. Remote skills (e.g.
Runway) need reference images by URL, so :meth:`ArtifactStore.public_url` exposes
a fetchable URL when ``PUBLIC_BASE_URL`` is configured.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid

from . import config
from .models import MediaArtifact, MediaType

_EXT = {
    MediaType.IMAGE: "png",
    MediaType.VIDEO: "mp4",
    MediaType.AUDIO: "mp3",
    MediaType.TEXT: "txt",
}

_DEFAULT_MIME = {
    MediaType.IMAGE: "image/png",
    MediaType.VIDEO: "video/mp4",
    MediaType.AUDIO: "audio/mpeg",
    MediaType.TEXT: "text/plain",
}


class ArtifactStore:
    """Local-filesystem artifact store. Pluggable S3/GCS later, same interface."""

    def __init__(self, root: str | None = None, public_base_url: str | None = None):
        self.root = root or config.ARTIFACT_DIR
        self.public_base_url = (
            public_base_url if public_base_url is not None else config.PUBLIC_BASE_URL
        )
        os.makedirs(self.root, exist_ok=True)

    # -- writing -----------------------------------------------------------
    def put_bytes(
        self,
        data: bytes,
        media_type: MediaType,
        *,
        mime: str | None = None,
        meta: dict | None = None,
        produced_by: str | None = None,
        entity_id: str | None = None,
    ) -> MediaArtifact:
        digest = hashlib.sha256(data).hexdigest()
        ext = _EXT.get(media_type, "bin")
        path = os.path.join(self.root, f"{digest}.{ext}")
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(data)
        return MediaArtifact(
            id=digest,
            media_type=media_type,
            uri=f"file://{path}",
            mime=mime or _DEFAULT_MIME.get(media_type),
            meta=meta or {},
            produced_by=produced_by,
            entity_id=entity_id,
        )

    def put_data_url(
        self,
        data_url: str,
        media_type: MediaType,
        **kwargs,
    ) -> MediaArtifact:
        """Decode a ``data:<mime>;base64,<payload>`` URL (e.g. server.py's PNG)."""
        mime, payload = _split_data_url(data_url)
        data = base64.b64decode(payload)
        kwargs.setdefault("mime", mime)
        return self.put_bytes(data, media_type, **kwargs)

    # -- reading -----------------------------------------------------------
    def path_for(self, artifact: MediaArtifact) -> str | None:
        if artifact.uri.startswith("file://"):
            return artifact.uri[len("file://") :]
        return None

    def open(self, artifact: MediaArtifact) -> bytes:
        path = self.path_for(artifact)
        if path is None:
            raise ValueError(f"artifact {artifact.id} is not local: {artifact.uri}")
        with open(path, "rb") as fh:
            return fh.read()

    def as_data_url(self, artifact: MediaArtifact) -> str:
        data = self.open(artifact)
        mime = artifact.mime or _DEFAULT_MIME.get(artifact.media_type, "application/octet-stream")
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"

    def url_path(self, artifact: MediaArtifact) -> str:
        """The relative URL this orchestrator serves the artifact at.

        Single source of truth for the ``/artifacts/<id>.<ext>`` mapping, reused by
        the runtime/API/UI so they agree on the extension. Already-remote
        artifacts (https://) are returned verbatim.
        """
        if artifact.uri.startswith(("http://", "https://")):
            return artifact.uri
        ext = _EXT.get(artifact.media_type, "bin")
        return f"/artifacts/{artifact.id}.{ext}"

    def payload(self, artifact: MediaArtifact) -> dict:
        """JSON-safe artifact dict + a ``url`` the browser can load it from."""
        d = artifact.model_dump(mode="json")
        d["url"] = self.url_path(artifact)
        return d

    def public_url(self, artifact: MediaArtifact) -> str:
        """An absolute URL a remote service can fetch. Requires ``PUBLIC_BASE_URL``.

        Already-remote artifacts (https://) are returned as-is.
        """
        if artifact.uri.startswith(("http://", "https://")):
            return artifact.uri
        if not self.public_base_url:
            raise RuntimeError(
                "PUBLIC_BASE_URL is not set; cannot expose a fetchable URL for "
                f"artifact {artifact.id}. Required for remote skills (e.g. Runway)."
            )
        return f"{self.public_base_url}{self.url_path(artifact)}"


def _split_data_url(data_url: str) -> tuple[str | None, str]:
    if not data_url.startswith("data:"):
        # Treat as a bare base64 payload.
        return None, data_url
    header, _, payload = data_url[len("data:") :].partition(",")
    mime = header.split(";", 1)[0] or None
    return mime, payload


def new_artifact_id() -> str:
    return uuid.uuid4().hex
