from __future__ import annotations

from pathlib import Path

from inventory import Item
from protection import is_protected_path
from utils import codesign_team_info, dir_size_bytes, logger, read_plist


class ApplicationsCollector:
    name = "Applications"

    roots = [
        (Path("/Applications"), "Applications folder"),
        (Path.home() / "Applications", "User Applications folder"),
        (Path("/System/Applications"), "System Applications"),
        (Path("/System/Library/CoreServices"), "Core Services"),
    ]

    def collect(self) -> list[Item]:
        items: list[Item] = []
        seen: set[str] = set()
        for root, source in self.roots:
            if not root.exists():
                continue
            try:
                apps = sorted(root.glob("*.app"))
            except OSError as exc:
                logger.warning("Cannot list %s: %s", root, exc)
                continue
            for app in apps:
                key = str(app)
                if key in seen:
                    continue
                seen.add(key)
                items.append(self._item_for_app(app, source, root))
        return items

    def _item_for_app(self, app: Path, source: str, root: Path) -> Item:
        data = read_plist(app / "Contents" / "Info.plist")
        name = data.get("CFBundleDisplayName") or data.get("CFBundleName") or app.stem
        bundle_id = str(data.get("CFBundleIdentifier") or "")
        version = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
        build = str(data.get("CFBundleVersion") or "")
        executable_name = data.get("CFBundleExecutable") or ""
        executable_path = None
        if executable_name:
            candidate = app / "Contents" / "MacOS" / executable_name
            executable_path = str(candidate)
        sign = codesign_team_info(app)
        publisher = sign.get("authority")
        protected = is_protected_path(str(app)) or str(root).startswith("/System")
        receipt = (app / "Contents" / "_MASReceipt" / "receipt").exists()
        try:
            st = app.stat()
            mtime = str(st.st_mtime)
            ctime = str(getattr(st, "st_birthtime", st.st_ctime))
        except OSError:
            mtime = ctime = None
        # Size collected during snapshot; keep bounded
        size = None
        if not protected and source != "Core Services":
            try:
                size = float(dir_size_bytes(app, max_files=2000))
            except OSError:
                size = None

        support_hints = []
        if bundle_id:
            support = Path.home() / "Library" / "Application Support" / bundle_id
            prefs = Path.home() / "Library" / "Preferences" / f"{bundle_id}.plist"
            if support.exists():
                support_hints.append(str(support))
            if prefs.exists():
                support_hints.append(str(prefs))

        item = Item(
            category="Applications",
            name=str(name),
            path=str(app),
            status="Installed",
            vendor=publisher or bundle_id,
            version=str(version) if version else None,
            risk="Protected" if protected else "Unknown",
            protected=protected,
            label=bundle_id or None,
            item_type="Application",
            subtype="system" if protected else "third-party",
            executable_path=executable_path,
            publisher=publisher,
            signing_identity=publisher,
            team_identifier=sign.get("team_id"),
            bundle_id=bundle_id or None,
            installation_source="Mac App Store" if receipt else source,
            running_state="Unknown",
            related_application=str(name),
            disk_usage=size,
            install_date=ctime,
            modification_date=mtime,
            build_number=build or None,
            technical_name=bundle_id or app.stem,
            details={
                "bundle_id": bundle_id,
                "executable": executable_name,
                "team_id": sign.get("team_id", ""),
                "app_store_receipt": receipt,
                "related_paths": support_hints,
                "info_plist": str(app / "Contents" / "Info.plist"),
            },
        )
        item.ensure_stable_id()
        return item
