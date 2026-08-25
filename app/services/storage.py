import hashlib
from pathlib import Path


class LocalDocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes) -> tuple[str, Path]:
        digest = hashlib.sha256(content).hexdigest()
        target = self.root / digest[:2] / f"{digest}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        return digest, target.resolve()
