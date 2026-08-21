# Microsoft Store release path

Privacy Gate uses an MSIX package for Microsoft Store distribution. The existing
Inno Setup EXE remains a separate GitHub/direct-download option. The Store is the
recommended customer path because Microsoft signs an accepted MSIX and delivers
subsequent updates.

## One-time account and product setup

1. Open <https://storedeveloper.microsoft.com/> and select **Get started for free**.
2. Complete identity verification and open **Apps & games** in Partner Center.
3. Select **New product > MSIX or PWA app**.
4. Reserve **AI PM LAB Privacy Gate**.
5. Open **Product management > Product identity**.
6. Copy exactly: **Package/Identity/Name**, **Publisher**, and
   **Publisher display name**.

Do not invent or shorten these values. The MSIX manifest must match Partner Center.

## Build the Store package

```powershell
.\scripts\build_windows.ps1
.\scripts\build_msix.ps1 `
  -PackageIdentityName 'VALUE_FROM_PARTNER_CENTER' `
  -Publisher 'VALUE_FROM_PARTNER_CENTER' `
  -PublisherDisplayName 'VALUE_FROM_PARTNER_CENTER'
```

The package is written to `release/`. It is intentionally not signed locally:
upload it to the matching Partner Center product, where Microsoft signs an
accepted Store package. An unsigned MSIX is not a customer download.

## Submission fields

- Set pricing to **Free**.
- Suggested category: **Business** or **Productivity**.
- Website: <https://privacygate.propertydex.xyz/>.
- Use the published Privacy Policy and product support email.
- Upload screenshots from a clean customer build.
- Certification note: core protection is local-only; optional MCP uses outbound
  connectivity and exposes only already-protected Library content.
- Upload the generated x64 MSIX under **Packages** and resolve every validation
  message before certification.

## Website and Terminal after publication

Use the Store Product ID supplied by Partner Center in the website button:

```text
ms-windows-store://pdp/?ProductId=STORE_PRODUCT_ID
```

Customer installation from Terminal:

```powershell
winget install --id STORE_PRODUCT_ID --source msstore --accept-package-agreements --accept-source-agreements
```

Verify the public listing before publishing that command:

```powershell
winget show --id STORE_PRODUCT_ID --source msstore
```

Store updates replace application binaries while Privacy Gate Library data remains
under the user's local application-data directory.
