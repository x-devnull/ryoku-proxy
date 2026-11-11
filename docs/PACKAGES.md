# Package publishing and repository signing

Two Arch installation methods coexist: signed pacman repository updates and
manual release packages. Debian packages are additional manual downloads;
this project does not publish an APT repository.

## Maintainer: enable the signed repository

The workflow is implemented but the repository is not usable until a dedicated
signing key is configured and the first signed deployment succeeds. Do not
reuse a personal identity key. Keep an offline backup of the repository key
and its revocation certificate, outside this source tree.

For a new dedicated key, run this in your normal host terminal:

```sh
bash tools/setup-repository.sh
```

It asks for a passphrase without echo, generates a signing-only Ed25519 key
(valid for two years) under `~/.local/share/ryoku-proxy-signing`, and transfers
private material directly to GitHub Secrets. An existing directory is never
overwritten. Back up the key and revocation certificate offline. This command
requires working GitHub CLI authentication and GPG on the host.

Alternatively, generate and configure a dedicated key manually:

```sh
gpg --quick-generate-key 'Ryoku Proxy package signing' ed25519 sign 2y
gpg --list-secret-keys --keyid-format long --with-fingerprint
```

Take the complete primary fingerprint from that output:

```sh
bash tools/configure-signing.sh YOUR_FULL_FINGERPRINT
# Only if the private key has a passphrase: gh prompts without echoing it.
gh secret set REPO_SIGNING_PASSPHRASE --repo x-devnull/ryoku-proxy
```

The script transfers the armored private key directly to the GitHub secret
`REPO_SIGNING_KEY` and records the public fingerprint in the repository variable
`REPO_SIGNING_FINGERPRINT`. It never writes the private key into Git, artifacts
or command arguments. Only a trusted maintainer should configure these values.

Publish the intended source commit/tag first. Release jobs build the exact triggering commit. For this packaging-only update,
run the workflow manually on main: revision 1.0.0-2 is attached to the existing
v1.0 release, alongside the original 1.0.0-1 package. The existing v1.0 tag is
not moved. The revised source archive uses a distinct -r2 filename. For future
updates, increment the package/release version and update the versioned recipe,
metadata and documentation together. Do not
replace a signed package with different bytes under the same version.

Run **Publish ED 1.0 release**. It tests the application, builds Arch and Debian
packages, inspects Debian metadata and attaches packages and SHA256SUMS to the
release. **Publish signed pacman repository** runs after a successful release,
imports the dedicated key into a temporary GnuPG home, signs the Arch packages
and database, verifies signatures and uploads `pacman-repository.tar.gz` to a
rolling prerelease named `pacman-repository`. It also attaches Arch detached
signatures to v1.0. Missing signing configuration fails this workflow; manual
release packages remain available.

**Deploy landing to GitHub Pages** then combines the English landing with the
signed bundle. Future landing-only deployments retrieve the existing bundle,
so they do not erase the package repository. Errors downloading an existing
repository stop deployment. Before the first repository exists, only the
landing is deployed. Repository aliases are regular files, suitable for Pages.

Publish the full public key fingerprint in a separately verified channel before
users trust it. The repository publishes the public key at
`https://x-devnull.github.io/ryoku-proxy/repo/ryoku-proxy.asc` and its fingerprint
at `.../repo/FINGERPRINT`; neither URL substitutes for independent verification.
Never document `SigLevel = Never` or `TrustAll`.

The current rolling repository contains the revision 1.0.0-2 Arch package from v1.0; it does
not mirror sing-box or any third-party dependencies. Users need trusted
repositories supplying those dependencies. It is not a downgrade/rollback
archive. A future release must extend the version handling before publication.

## Manual packages and local builds

```sh
python tools/source_archive.py
# In an empty build directory, copy the generated source archive, PKGBUILD
# and ryoku-proxy.install; then run makepkg as a normal user.
makepkg -si
```

Build Debian without root using Python and binutils (`ar`):

```sh
python tools/build_deb.py
```

The Debian archive uses root-owned payload entries and executable lifecycle
scripts. It does not start services or grant passwordless access. Removal
checks active Kill Switch state before deleting the helper; upgrading does not
run that removal guard. User profiles and sing-box configuration are preserved.

Target Debian 13 with distro PySide6 QtWidgets, Qt Wayland/SVG, polkit, systemd
and sing-box >=1.14. If the distro does not supply a suitable sing-box package,
use its [official package-manager instructions](https://sing-box.sagernet.org/installation/package-manager/)
first. Older Debian/Ubuntu releases without the declared PySide6 packages are
not supported by this package. Live Debian networking and a clean-system
installation have not been validated. CI inspects the archive with dpkg-deb;
local tests inspect control/payload contents and removal/upgrade behavior.
There is no claim of Flathub, AUR, official distro or APT repository publication.

## Verification

Distribution tests exercise Debian payload ownership/modes, safe Pages bundle
extraction, landing-only deployment, and a signed test repository using an
ephemeral test key. The signing test is mandatory in Arch CI. A restricted local
environment unable to run gpg-agent reports that test as skipped rather than
claiming signature verification. Test keys are never used for production.


## GitHub connection errors during setup

`connection reset by peer` means the API connection was closed before account
verification completed. It does not identify a wrong account. The setup now
retries read-only account checks three times and stops before creating a key
if verification still fails. An actual different account is reported only after
GitHub returns its login successfully.

Run `gh api user --jq .login` in the same terminal. If it fails, check your
network and proxy/VPN path to api.github.com first. Reauthentication is relevant
for a real HTTP 401 response, not a connection reset alone. Once it prints
`x-devnull`, rerun `bash tools/setup-repository.sh`. At this initial failure,
no key directory was created by the script; do not remove existing signing keys.
