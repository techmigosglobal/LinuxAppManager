Name:           linux-app-manager
Version:        0.1.0
Release:        1%{?dist}
Summary:        VIN-LinuxManager safe cross-source Linux software manager
License:        GPL-3.0-or-later
URL:            https://github.com/techmigosglobal/LinuxAppManager
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  cargo
BuildRequires:  rust >= 1.90
BuildRequires:  elfutils
BuildRequires:  python3-gobject
BuildRequires:  gtk4
BuildRequires:  libadwaita
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit

%description
VIN-LinuxManager inventories desktop applications and packages from common
Linux software sources and shows a reviewed removal transaction before change.

%prep
%autosetup

%build
cargo build --release --locked --bin lam

%install
install -D -m 0755 target/release/lam %{buildroot}%{_prefix}/lib/linux-app-manager/lam
install -D -m 0755 gui/app.py %{buildroot}%{_prefix}/lib/linux-app-manager/app.py
install -D -m 0755 packaging/linux-app-manager %{buildroot}%{_bindir}/linux-app-manager
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.desktop %{buildroot}%{_datadir}/applications/io.github.techmigosglobal.LinuxAppManager.desktop
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml %{buildroot}%{_datadir}/metainfo/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.techmigosglobal.LinuxAppManager.svg
install -D -m 0644 packaging/io.github.techmigosglobal.LinuxAppManager.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/io.github.techmigosglobal.LinuxAppManager.png

%files
%{_bindir}/linux-app-manager
%{_prefix}/lib/linux-app-manager/lam
%{_prefix}/lib/linux-app-manager/app.py
%{_datadir}/applications/io.github.techmigosglobal.LinuxAppManager.desktop
%{_datadir}/metainfo/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.techmigosglobal.LinuxAppManager.svg
%{_datadir}/icons/hicolor/512x512/apps/io.github.techmigosglobal.LinuxAppManager.png

%changelog
* Fri Sep 25 2026 VIN-LinuxManager maintainers - 0.1.0-1
- Initial productionization track
