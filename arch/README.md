The checked-in PKGBUILD.in is a release template, not an installable AUR package.
Generate the concrete recipe only from the exact published offline source asset:

    scripts/render-aur.py /path/linux-app-manager-0.1.1.tar.gz /tmp/aur-release

The renderer computes the real SHA-256 and invokes makepkg --printsrcinfo to
create .SRCINFO. Upload both generated files to AUR after the release asset is
public. The recipe downloads the immutable GitHub release asset and builds its
vendored Cargo dependencies offline. Do not replace the checksum with SKIP.
The current release supports x86_64 only.
