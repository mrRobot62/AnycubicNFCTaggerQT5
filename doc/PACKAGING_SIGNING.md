# Packaging, Code Signing, and Notarization

This document covers the post-build process for signing and distributing **AnycubicNFCTaggerQT5** binaries on macOS and Windows.

---

## 1) macOS

### 1.1 Code Signing

If you have an Apple Developer ID certificate installed on your system:

```bash
codesign --deep --force --verify --verbose   --sign "Developer ID Application: Your Name (TEAMID)"   build/AnycubicNFCTaggerQT5.app
```

This embeds your Developer ID signature into the app bundle.

You can verify with:

```bash
codesign --verify --deep --strict --verbose=2 build/AnycubicNFCTaggerQT5.app
```

### 1.2 Notarization (Optional but Recommended)

If you intend to distribute the `.dmg` outside the App Store:

```bash
xcrun notarytool submit dist/AnycubicNFCTaggerQT5.dmg   --apple-id "your@appleid.com"   --team-id "YOURTEAMID"   --password "app-specific-password"   --wait
```

Once notarized, staple the ticket:

```bash
xcrun stapler staple dist/AnycubicNFCTaggerQT5.dmg
```

### 1.3 Verification

Mount the DMG and confirm Gatekeeper validation:

```bash
spctl -a -vv dist/AnycubicNFCTaggerQT5.dmg
```

You should see “source=Notarized Developer ID”.

---

## 2) Windows

### 2.1 Code Signing

Use **signtool** (from Windows SDK):

```powershell
signtool sign /a /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\AnycubicNFCTaggerQT5.exe
```

Verify signature:

```powershell
signtool verify /pa /v dist\AnycubicNFCTaggerQT5.exe
```

### 2.2 Optional MSI Signing

If you produce an `.msi`:

```powershell
signtool sign /a /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\AnycubicNFCTaggerQT5.msi
```

---

## 3) Distribution Recommendations

- Always sign before public distribution to reduce antivirus false positives.
- Keep versioned archives (DMG/EXE/MSI) under a signed release tag.
- Publish hash checksums (`sha256sum`) alongside binaries.

---

**End of Packaging & Signing Guide**
