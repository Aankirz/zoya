from __future__ import annotations

import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
CACHE = DIST / "cache"
APP_NAME = "Zoya"
BUNDLE_ID = "app.zoya.Zoya"
MIN_MACOS = "14.0"
PYTHON_VERSION = "3.12.13"
PYTHON_TAG = "python3.12"
EXCLUDED_PACKAGES = {"torch", "networkx"}
PYTHON_TRIM = (
    "lib/{py}/test",
    "lib/{py}/idlelib",
    "lib/{py}/tkinter",
    "lib/{py}/turtledemo",
    "lib/{py}/ensurepip",
    "lib/{py}/site-packages",
)
SIGNING_IDENTITY = "Zoya Self-Signed Code Signing"
SIGNING_KEYCHAIN = Path.home() / "Library/Keychains/zoya-signing.keychain-db"
SIGNING_PASSWORD_SERVICE = "Zoya signing keychain"
SIGN_BATCH = 200
MACHO_MAGICS = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}

AGENT_BROWSER_VERSION = "0.38.1"
AGENT_BROWSER_URL = (
    f"https://registry.npmjs.org/agent-browser/-/agent-browser-{AGENT_BROWSER_VERSION}.tgz"
)
AGENT_BROWSER_SHA256 = "89a7df4761ff335e4dd5367e4cf04cecb9ba4e2cc130a0220f798d188414dc6c"
AGENT_BROWSER_MEMBER = "package/bin/agent-browser-darwin-arm64"
SPARKLE_VERSION = "2.10.0"
SPARKLE_URL = (
    "https://github.com/sparkle-project/Sparkle/releases/download/"
    f"{SPARKLE_VERSION}/Sparkle-{SPARKLE_VERSION}.tar.xz"
)
SPARKLE_SHA256 = "c2bf58aa8387266ac179357b1415d6f2635f044da8be41042af32425dae6da0c"
SPARKLE_PUBLIC_ED_KEY = "8vpkcJictd2mTgJ6p923Z0Z8cB5HCYeYa9BptkN2bUE="
FEED_URL = "https://zoya.app/appcast.xml"
UPDATE_CHECK_INTERVAL_S = 86400
ICON_LARGE = REPO / "packaging/icon/zoya.svg"
ICON_SMALL = REPO / "packaging/icon/zoya-small.svg"
ICON_POINTS = (16, 32, 128, 256, 512)
ICON_SMALL_MAX_PT = 32

MICROPHONE_USAGE = (
    "Zoya listens for your voice, so you can ask for anything without touching the Mac. "
    "What you say is turned into text on this Mac."
)
APPLE_EVENTS_USAGE = (
    "Zoya controls apps like Notes and Music when you ask her to, "
    "so you never have to find the buttons yourself."
)


def run(*command: str | Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, expected: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / url.rsplit("/", 1)[-1]
    if not target.exists() or sha256(target) != expected:
        with urllib.request.urlopen(url, timeout=300) as source, target.open("wb") as out:
            shutil.copyfileobj(source, out)
    actual = sha256(target)
    if actual != expected:
        target.unlink()
        sys.exit(f"Checksum mismatch for {url}: {actual}")
    return target


def version() -> str:
    pinned = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"]
    return os.environ.get("ZOYA_VERSION", pinned)


def source_python() -> Path:
    run("uv", "python", "install", PYTHON_VERSION)
    found = run("uv", "python", "find", PYTHON_VERSION, capture_output=True, text=True)
    return Path(found.stdout.strip()).resolve().parent.parent


def copy_python(source: Path, resources: Path) -> Path:
    target = resources / "python"
    shutil.copytree(source / "lib", target / "lib", symlinks=True)
    for pattern in PYTHON_TRIM:
        shutil.rmtree(target / pattern.format(py=PYTHON_TAG), ignore_errors=True)
    for leftover in target.joinpath("lib").glob("*tcl*"):
        shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()
    for leftover in target.joinpath("lib").glob("*tk*"):
        shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()
    for tk_module in target.glob(f"lib/{PYTHON_TAG}/lib-dynload/_tkinter*"):
        tk_module.unlink()
    return target


def install_packages(source: Path, python_home: Path) -> None:
    exported = run(
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout
    wanted = [
        line
        for line in exported.splitlines()
        if line and not line.startswith(("#", " ")) and line.split("==")[0] not in EXCLUDED_PACKAGES
    ]
    CACHE.mkdir(parents=True, exist_ok=True)
    requirements = CACHE / "requirements.txt"
    requirements.write_text("\n".join(wanted) + "\n")
    site = python_home / "lib" / PYTHON_TAG / "site-packages"
    run(
        "uv",
        "pip",
        "install",
        "--quiet",
        "--no-deps",
        "--python",
        source / "bin" / PYTHON_TAG,
        "--target",
        site,
        "-r",
        requirements,
    )
    shutil.rmtree(site / "bin", ignore_errors=True)


def copy_app_sources(resources: Path) -> None:
    listed = run(
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "zoya",
        "sounds",
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout
    for name in listed.splitlines():
        source = REPO / name
        if not source.is_file():
            continue
        target = resources / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def add_helpers(macos: Path) -> None:
    from zoya.config import MEMORY_SERVER_SHA256, MEMORY_SERVER_URL

    shutil.copy2(fetch(MEMORY_SERVER_URL, MEMORY_SERVER_SHA256), macos / "supermemory-server")
    with tarfile.open(fetch(AGENT_BROWSER_URL, AGENT_BROWSER_SHA256)) as archive:
        member = archive.extractfile(AGENT_BROWSER_MEMBER)
        (macos / "agent-browser").write_bytes(member.read())
    for helper in ("supermemory-server", "agent-browser"):
        (macos / helper).chmod(0o755)


def add_sparkle(contents: Path) -> None:
    unpacked = CACHE / f"sparkle-{SPARKLE_VERSION}"
    if not unpacked.exists():
        unpacked.mkdir()
        run("tar", "-xf", fetch(SPARKLE_URL, SPARKLE_SHA256), "-C", unpacked)
    frameworks = contents / "Frameworks"
    frameworks.mkdir()
    run("ditto", unpacked / "Sparkle.framework", frameworks / "Sparkle.framework")


def render_png(svg: Path, pixels: int, target: Path) -> None:
    import AppKit

    image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(svg))
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        None, pixels, pixels, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
    )
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(
        AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    )
    image.drawInRect_fromRect_operation_fraction_(
        ((0, 0), (pixels, pixels)), AppKit.NSZeroRect, AppKit.NSCompositingOperationCopy, 1.0
    )
    AppKit.NSGraphicsContext.restoreGraphicsState()
    png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None)
    png.writeToFile_atomically_(str(target), True)


def add_icon(resources: Path) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        iconset = Path(scratch) / f"{APP_NAME}.iconset"
        iconset.mkdir()
        for points in ICON_POINTS:
            source = ICON_SMALL if points <= ICON_SMALL_MAX_PT else ICON_LARGE
            for scale, suffix in ((1, ""), (2, "@2x")):
                name = f"icon_{points}x{points}{suffix}.png"
                render_png(source, points * scale, iconset / name)
        run("iconutil", "-c", "icns", iconset, "-o", resources / f"{APP_NAME}.icns")


def write_info_plist(contents: Path, app_version: str) -> None:
    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": app_version,
        "CFBundleVersion": app_version,
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": MIN_MACOS,
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": MICROPHONE_USAGE,
        "NSAppleEventsUsageDescription": APPLE_EVENTS_USAGE,
        "SUFeedURL": FEED_URL,
        "SUPublicEDKey": SPARKLE_PUBLIC_ED_KEY,
        "SUEnableAutomaticChecks": True,
        "SUScheduledCheckInterval": UPDATE_CHECK_INTERVAL_S,
    }
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(info, handle)
    (contents / "PkgInfo").write_text("APPL????")


def compile_launcher(source: Path, python_home: Path, macos: Path) -> None:
    library = python_home / "lib" / f"lib{PYTHON_TAG}.dylib"
    run("install_name_tool", "-id", f"@rpath/lib{PYTHON_TAG}.dylib", library)
    launcher = macos / APP_NAME
    run(
        "clang",
        "-O2",
        "-arch",
        "arm64",
        f"-mmacosx-version-min={MIN_MACOS}",
        "-I",
        source / "include" / PYTHON_TAG,
        REPO / "packaging" / "launcher.c",
        "-L",
        python_home / "lib",
        f"-l{PYTHON_TAG}",
        "-Wl,-rpath,@executable_path/../Resources/python/lib",
        "-o",
        launcher,
    )
    old = source / "lib" / f"lib{PYTHON_TAG}.dylib"
    run("install_name_tool", "-change", old, f"@rpath/lib{PYTHON_TAG}.dylib", launcher)


def precompile(source: Path, contents: Path) -> None:
    resources = contents / "Resources"
    run(
        source / "bin" / PYTHON_TAG,
        "-m",
        "compileall",
        "-q",
        "-j",
        "0",
        "--invalidation-mode",
        "unchecked-hash",
        resources / "app",
        resources / "python" / "lib" / PYTHON_TAG,
    )


def refused_launches(marker: Path) -> list[list[str]]:
    code = f"open({str(marker)!r}, 'w').write('ran')"
    script = marker.with_suffix(".py")
    script.write_text(code)
    return [
        ["-c", code],
        ["-i", "-c", code],
        ["-", code],
        [str(script)],
        ["-m", "zoya"],
        ["-m", "zoya.main", "--help"],
        ["-m", "compileall", str(marker.parent)],
        ["-I", "-m", "zoya.overlay"],
        ["-m"],
    ]


def check_refusals(app: Path) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        marker = Path(folder) / "ran"
        for arguments in refused_launches(marker):
            result = subprocess.run(
                [str(app / "Contents" / "MacOS" / APP_NAME), *arguments],
                input=f"open({str(marker)!r}, 'w').write('ran')\n",
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0 or marker.exists():
                sys.exit(f"The launcher ran {arguments}; it must refuse it.")


def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file() or path.suffix in (".class", ".py", ".pyc"):
        return False
    with path.open("rb") as handle:
        return handle.read(4) in MACHO_MAGICS


def unlock_signing_keychain() -> None:
    if not SIGNING_KEYCHAIN.exists():
        sys.exit("No signing keychain. Run packaging/make_signing_certificate.sh once on this Mac.")
    password = run(
        "security",
        "find-generic-password",
        "-s",
        SIGNING_PASSWORD_SERVICE,
        "-w",
        capture_output=True,
        text=True,
    ).stdout.strip()
    run("security", "unlock-keychain", "-p", password, SIGNING_KEYCHAIN)


def sign(*paths: Path, identifier: str = "") -> None:
    command = ["codesign", "--force", "--timestamp=none", "--keychain", str(SIGNING_KEYCHAIN)]
    command += ["--sign", SIGNING_IDENTITY]
    if identifier:
        command += ["--identifier", identifier]
    for start in range(0, len(paths), SIGN_BATCH):
        run(*command, *paths[start : start + SIGN_BATCH], capture_output=True)


def sign_sparkle(framework: Path) -> None:
    current = framework / "Versions" / "B"
    sign(*sorted((current / "XPCServices").glob("*.xpc")))
    sign(current / "Autoupdate")
    sign(current / "Updater.app")
    sign(framework)


def sign_bundle(app: Path) -> None:
    contents = app / "Contents"
    loose = [
        path
        for path in contents.rglob("*")
        if "Sparkle.framework" not in path.parts and is_macho(path)
    ]
    loose = [path for path in loose if path != contents / "MacOS" / APP_NAME]
    sign(*sorted(loose, key=lambda path: len(path.parts), reverse=True))
    sign_sparkle(contents / "Frameworks" / "Sparkle.framework")
    sign(app, identifier=BUNDLE_ID)
    run("codesign", "--verify", "--deep", "--strict", app)


def build() -> Path:
    app_version = version()
    app = DIST / f"{APP_NAME}.app"
    shutil.rmtree(app, ignore_errors=True)
    contents = app / "Contents"
    macos = contents / "MacOS"
    macos.mkdir(parents=True)
    source = source_python()
    python_home = copy_python(source, contents / "Resources")
    install_packages(source, python_home)
    copy_app_sources(contents / "Resources")
    add_helpers(macos)
    add_sparkle(contents)
    add_icon(contents / "Resources")
    write_info_plist(contents, app_version)
    compile_launcher(source, python_home, macos)
    precompile(source, contents)
    unlock_signing_keychain()
    sign_bundle(app)
    check_refusals(app)
    archive = DIST / f"{APP_NAME}-{app_version}.zip"
    archive.unlink(missing_ok=True)
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, archive)
    return archive


if __name__ == "__main__":
    print(build())
