Name:           linux-app-manager
Version:        0.1.1
Release:        1%{?dist}
Summary:        VIN-LinuxManager safe cross-source Linux software manager
License:        GPL-3.0-or-later
URL:            https://github.com/techmigosglobal/LinuxAppManager
Source0:        https://github.com/techmigosglobal/LinuxAppManager/releases/download/v%{version}/%{name}-%{version}.tar.gz
ExclusiveArch:  x86_64
BuildRequires:  gcc
BuildRequires:  glibc-devel
BuildRequires:  cargo >= 1.90
BuildRequires:  rust >= 1.90
BuildRequires:  elfutils
BuildRequires:  python3-gobject
BuildRequires:  gtk4
BuildRequires:  libadwaita
Requires:       python3
Requires:       python3-gobject
Requires:       gobject-introspection
# The Python frontend loads GI dynamically, so ELF autodeps cannot infer these.
# ToolbarView was introduced in libadwaita 1.4; older runtimes cannot launch it.
Requires:       gtk4 >= 4.0
Requires:       libadwaita >= 1.4
Requires:       polkit

%description
VIN-LinuxManager inventories desktop applications and packages from common
Linux software sources and shows a reviewed removal transaction before change.

%prep
%autosetup

%build
cargo build --release --locked --offline --bin lam

%check
cargo test --all-targets --locked --offline

%install
install -d %{buildroot}%{_licensedir}/%{name}
cp -a LICENSE THIRD_PARTY_LICENSES %{buildroot}%{_licensedir}/%{name}/
python3 scripts/hardlink-license-files.py %{buildroot}%{_licensedir}/%{name}
install -D -m 0755 target/release/lam %{buildroot}%{_prefix}/lib/linux-app-manager/lam
install -D -m 0755 gui/app.py %{buildroot}%{_prefix}/lib/linux-app-manager/app.py
install -D -m 0755 packaging/linux-app-manager %{buildroot}%{_bindir}/linux-app-manager
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.desktop %{buildroot}%{_datadir}/applications/io.github.techmigosglobal.LinuxAppManager.desktop
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml %{buildroot}%{_datadir}/metainfo/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.techmigosglobal.LinuxAppManager.svg
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/io.github.techmigosglobal.LinuxAppManager.png

%files
%license %{_licensedir}/%{name}
%doc README.md
%{_bindir}/linux-app-manager
%{_prefix}/lib/linux-app-manager/lam
%{_prefix}/lib/linux-app-manager/app.py
%{_datadir}/applications/io.github.techmigosglobal.LinuxAppManager.desktop
%{_datadir}/metainfo/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.techmigosglobal.LinuxAppManager.svg
%{_datadir}/icons/hicolor/512x512/apps/io.github.techmigosglobal.LinuxAppManager.png

%changelog
* Mon Oct 19 2026 VIN-LinuxManager maintainers <Vin-Linux-App-Manager@techmigos.com> - 0.1.1-1
- Build locked vendored sources offline and include license and documentation

* Mon Oct 05 2026 VIN-LinuxManager maintainers <Vin-Linux-App-Manager@techmigos.com> - 0.1.0-1
- Initial productionization track
