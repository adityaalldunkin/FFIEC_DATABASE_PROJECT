# Upload Texas CSVs to SharePoint (for maintainers)

Teammates use this folder:

**https://cedarframe-my.sharepoint.com/:f:/g/personal/aditya_alldunkin_com/IgCVLkzsCMRsQqXAsv7Ql-A5AW2lhgQIsUy0pHp0Kv9Vkm4?e=jGFMZX**

## Files to upload

From `ONLY_TEXAS_SINCE_2025/exports/`:

1. `texas_institutions.csv`
2. `texas_filings.csv`
3. `texas_xbrl_facts.csv` (~208 MB — may take several minutes)

**Or** upload one zip:

- `ONLY_TEXAS_SINCE_2025/texas_csv_exports_2025_plus.zip` (all three CSVs)

## Steps (browser)

1. Open the SharePoint link above (sign in with Cedar Frame / Microsoft account if prompted).
2. Click **Upload** → **Files**.
3. Select the three CSV files or the zip from your Mac.
4. Wait until upload completes (especially for `texas_xbrl_facts.csv`).
5. Confirm teammates can open the folder with the same link.

## Steps (Finder — if OneDrive syncs that folder)

```bash
open /Users/adityarajiv/Documents/ffiec-cdr/ONLY_TEXAS_SINCE_2025/exports
open "https://cedarframe-my.sharepoint.com/:f:/g/personal/aditya_alldunkin_com/IgCVLkzsCMRsQqXAsv7Ql-A5AW2lhgQIsUy0pHp0Kv9Vkm4?e=jGFMZX"
```

Drag the four files (3 CSV + optional zip) into the browser window.

## After upload

Commit README changes to GitHub so the SharePoint link is documented in the repo:

```bash
cd /Users/adityarajiv/Documents/ffiec-cdr
git add ONLY_TEXAS_SINCE_2025/README.md README.md ONLY_TEXAS_SINCE_2025/UPLOAD_TO_SHAREPOINT.md
git commit -m "Document SharePoint link for Texas CSV data"
git push origin main
```

Note: CSV data stays off GitHub (too large); SharePoint is the distribution channel for teammates.
