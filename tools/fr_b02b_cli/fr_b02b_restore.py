"""Internal backup round-trip verification inside the caller's protected Gate.

Never a recovery/repair command. Sources stay unchanged; every target is new and
all partial results stay HOLD. No completed registration or durability claim.
"""

from pathlib import Path
import stat

import fr_b02b_observation as observation
from fr_b02b_a1_adapter import _load_a1_snapshot_bytes
from fr_b02b_protected_store import ProtectedEvidenceStore, StagingError, _validated_files


def validate_stored_files(files, event_id):
    """Rebuild A1/4A/pending links from stored bytes, without accepting a registration."""
    try:
        if set(files) != {"a1_archive.zip", "observation.json", "index.json", "pending_review.json"}:
            raise ValueError("incomplete stored snapshot")
        snapshot = _load_a1_snapshot_bytes(files["a1_archive.zip"])
        record = observation._validate_records(snapshot, files["observation.json"],
                                                files["index.json"], event_id)
        evidence = observation.VerifiedObservation(snapshot, record, files["observation.json"],
                                                    files["index.json"])
        if _validated_files(evidence, files["pending_review.json"]) != files:
            raise ValueError("stored link mismatch")
    except (ValueError, KeyError):
        raise StagingError("stored snapshot/metadata links invalid; HOLD") from None


class BackupRestoreVerifier:
    def __init__(self, target, evidence, pending_bytes, source_roots):
        if not isinstance(target, ProtectedEvidenceStore):
            raise StagingError("restore target is unconfigured; HOLD")
        self.target, self.root = target, target.root
        if (not isinstance(self.root, Path) or not self.root.is_absolute()
                or any(self.root != root and (self.root.is_relative_to(root)
                                              or root.is_relative_to(self.root)) for root in source_roots)):
            raise StagingError("restore container overlaps protected sources; HOLD")
        self.files = _validated_files(evidence, pending_bytes)
        self.event_id = observation._event_id(evidence.record["evidence_id"])
        self.folder = self.root / (".review-restore-" + self.event_id)
        self.identities = {}
        self.prepared = self.created = False
        self.written = set()

    def _pin(self, path):
        info = path.lstat()
        identity = info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)
        if not info.st_ino or identity != self.identities.setdefault(path, identity):
            raise StagingError("restore object identity changed; HOLD")

    def _root(self):
        if self.target.root != self.root:
            raise StagingError("restore target configuration changed; HOLD")
        self.target._checked(self.root, directory=True)
        for path in (*reversed(self.root.parents), self.root):
            self._pin(path)

    def preflight(self):
        self._root()
        try:
            self.folder.lstat()
        except FileNotFoundError:
            self.prepared = True
            return
        raise StagingError("restore target collision; HOLD")

    def _read(self, store, path, expected):
        store._checked(path, directory=False)
        self._pin(path)
        raw = store._read_copy(path, len(expected) + 1)
        if raw != expected or observation.digest(raw) != observation.digest(expected):
            raise StagingError("restore bytes/SHA-256 mismatch; HOLD")
        store._checked(path, directory=False)
        self._pin(path)
        return raw

    def check(self):
        if not self.prepared:
            return
        self._root()
        if not self.created:
            try:
                self.folder.lstat()
            except FileNotFoundError:
                return
            raise StagingError("restore target appeared before exclusive creation; HOLD")
        self.target._checked(self.folder, directory=True)
        self._pin(self.folder)
        if {p.name for p in self.folder.iterdir()} != self.written:
            raise StagingError("unexpected/partial restore file set; HOLD")
        for name in self.written:
            self._read(self.target, self.folder / name, self.files[name])

    def _sources(self, stores, folders):
        copies = []
        for store, folder in zip(stores, folders):
            store._checked(folder, directory=True)
            self._pin(folder)
            if {p.name for p in folder.iterdir()} != set(self.files):
                raise StagingError("incomplete protected source file set; HOLD")
            copies.append({name: self._read(store, folder / name, expected)
                           for name, expected in self.files.items()})
        if len(copies) != 2 or copies[0] != copies[1]:
            raise StagingError("primary/backup restore source mismatch; HOLD")
        return copies[1]  # Restore FROM the freshly read backup, never input defaults.

    def run(self, stores, folders, checkpoint):
        checkpoint()
        backup = self._sources(stores, folders)
        checkpoint()
        self.target._create_staging(self.folder)
        self.created = True
        self.target._checked(self.folder, directory=True)
        self._pin(self.folder)
        for name in self.files:
            checkpoint()
            self._sources(stores, folders)
            self.target._write_file(self.folder / name, backup[name])
            self.written.add(name)
            self.check()
            checkpoint()
        restored = {name: self._read(self.target, self.folder / name, raw)
                    for name, raw in self.files.items()}
        # Rebuild validation input solely from RESTORED bytes and verify the
        # A1/4A/index/local_evidence_id/pending metadata links again.
        validate_stored_files(restored, self.event_id)
        self._sources(stores, folders)
        checkpoint()
        self.check()
        return self.folder
