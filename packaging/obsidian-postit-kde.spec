Name:           obsidian-postit-kde
Version:        0.1.0
Release:        1%{?dist}
Summary:        KDE tray app to save quick notes into an Obsidian vault

License:        MIT
URL:            https://github.com/sleroy/obsidian-postit-kde
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
Requires:       python3-pyside6
Requires:       python3-keyring
Requires:       python3-httpx

%description
A lightweight KDE system-tray application to capture quick notes and
clipboard contents directly into an Obsidian Markdown vault, without
launching Obsidian.

%prep
%autosetup

%build
%pyproject_wheel

%install
%pyproject_install
install -Dm644 packaging/%{name}.desktop \
    %{buildroot}%{_datadir}/applications/%{name}.desktop
install -Dm644 src/obsidian_postit_kde/resources/icon.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%files
%license LICENSE
%doc README.md DESIGN.md
%{_bindir}/obsidian-postit-kde
%{python3_sitelib}/obsidian_postit_kde/
%{python3_sitelib}/obsidian_postit_kde-%{version}.dist-info/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* Sat Oct 31 2026 sleroy - 0.1.0-1
- Initial package
