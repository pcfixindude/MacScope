from __future__ import annotations

"""Local knowledge catalog for common components. No network fetches."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    display_name: str
    bundle_id_patterns: tuple[str, ...] = ()
    launch_label_patterns: tuple[str, ...] = ()
    publisher: str = ""
    description: str = ""
    homepage: str = ""
    documentation: str = ""
    removal_notes: str = ""
    safety_notes: str = ""


CATALOG: list[CatalogEntry] = [
    CatalogEntry("Apple system component", ("com.apple.",), ("com.apple.",), "Apple", "Built-in macOS component.", "https://support.apple.com", "", "Do not remove.", "Management actions are disabled."),
    CatalogEntry("Homebrew", (), ("homebrew.", "sh.brew."), "Homebrew", "macOS package manager.", "https://brew.sh", "https://docs.brew.sh", "Use brew uninstall.", "Prefer brew for package lifecycle."),
    CatalogEntry("Docker Desktop", ("com.docker.",), ("com.docker.",), "Docker Inc.", "Container runtime for Mac.", "https://www.docker.com", "", "Use Docker Desktop uninstall or brew uninstall --cask docker.", "Helpers provide privileged networking."),
    CatalogEntry("Google Chrome", ("com.google.Chrome",), ("com.google.Chrome",), "Google", "Web browser.", "https://www.google.com/chrome/", "", "Move app to Trash; review Google support folders.", ""),
    CatalogEntry("Microsoft Office", ("com.microsoft.",), ("com.microsoft.",), "Microsoft", "Microsoft productivity apps.", "https://www.microsoft.com", "", "Use Microsoft uninstaller when available.", ""),
    CatalogEntry("Dropbox", ("com.getdropbox.", "com.dropbox."), ("com.dropbox.",), "Dropbox", "Cloud file sync.", "https://www.dropbox.com", "", "Quit Dropbox then remove app and login item.", ""),
    CatalogEntry("Adobe", ("com.adobe.",), ("com.adobe.",), "Adobe", "Adobe creative applications.", "https://www.adobe.com", "", "Use Adobe Creative Cloud uninstaller.", ""),
    CatalogEntry("Zoom", ("us.zoom.",), ("us.zoom.",), "Zoom", "Video meetings.", "https://zoom.us", "", "Remove Zoom.app and related login items.", ""),
    CatalogEntry("Spotify", ("com.spotify.",), ("com.spotify.",), "Spotify", "Music streaming.", "https://www.spotify.com", "", "Move Spotify.app to Trash.", ""),
    CatalogEntry("Cursor", ("com.todesktop.", "com.cursor."), ("com.cursor.",), "Anysphere", "AI code editor.", "https://cursor.com", "", "Move Cursor.app to Trash; review Application Support.", ""),
    CatalogEntry("Visual Studio Code", ("com.microsoft.VSCode",), ("com.microsoft.VSCode",), "Microsoft", "Code editor.", "https://code.visualstudio.com", "", "Move VS Code to Trash.", ""),
    CatalogEntry("LM Studio", ("com.eleutherai.lmstudio", "ai.elementlabs.lmstudio"), (), "Element Labs", "Local LLM desktop app.", "https://lmstudio.ai", "", "Remove app and models under configured model roots.", ""),
    CatalogEntry("Ollama", ("com.ollama.",), ("com.ollama.",), "Ollama", "Local model runner.", "https://ollama.com", "", "Remove app and ~/.ollama models carefully.", ""),
    CatalogEntry("Python", (), (), "Python Software Foundation", "Python language runtimes and environments.", "https://www.python.org", "", "Remove unused venvs; protect active interpreters.", ""),
    CatalogEntry("Node.js", (), (), "OpenJS", "JavaScript runtime and npm ecosystem.", "https://nodejs.org", "", "Remove node_modules or global packages deliberately.", ""),
    CatalogEntry("Streamlit", (), (), "Snowflake", "Python app framework often used locally.", "https://streamlit.io", "", "Stop Streamlit processes; remove project venvs if unused.", ""),
    CatalogEntry("PostgreSQL", (), ("homebrew.mxcl.postgresql",), "PostgreSQL", "Relational database.", "https://www.postgresql.org", "", "Stop brew service before uninstall.", ""),
    CatalogEntry("MySQL", (), ("homebrew.mxcl.mysql",), "Oracle/MySQL", "Relational database.", "https://www.mysql.com", "", "Stop brew service before uninstall.", ""),
    CatalogEntry("Redis", (), ("homebrew.mxcl.redis",), "Redis Ltd.", "In-memory data store.", "https://redis.io", "", "Stop brew service before uninstall.", ""),
    CatalogEntry("nginx", (), ("homebrew.mxcl.nginx",), "F5/nginx", "Web server.", "https://nginx.org", "", "Stop brew service before uninstall.", ""),
    CatalogEntry("VirtualBox", ("org.virtualbox.",), ("org.virtualbox.",), "Oracle", "Virtual machines.", "https://www.virtualbox.org", "", "Use VirtualBox uninstaller.", ""),
    CatalogEntry("OBS Studio", ("com.obsproject.",), ("com.obsproject.",), "OBS Project", "Streaming and recording.", "https://obsproject.com", "", "Move OBS.app to Trash.", ""),
    CatalogEntry("Whisper tools", (), (), "", "Local speech-to-text tooling (Whisper/WhisperKit/MacWhisper).", "", "", "Remove unused models carefully.", ""),
]


def lookup_catalog(bundle_id: str | None = None, label: str | None = None, name: str | None = None) -> CatalogEntry | None:
    bid = (bundle_id or "").lower()
    lab = (label or "").lower()
    nm = (name or "").lower()
    for entry in CATALOG:
        for pattern in entry.bundle_id_patterns:
            if bid.startswith(pattern.lower()):
                return entry
        for pattern in entry.launch_label_patterns:
            if lab.startswith(pattern.lower()) or pattern.lower() in lab:
                return entry
        if entry.display_name.lower() in nm:
            return entry
    return None
