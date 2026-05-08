# Windows Guide

Python (PowerShell)
1. Install Python 3.9+ and ensure it is on PATH.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies and authenticate:

```powershell
pip install -r requirements.txt
ytmusicapi browser
```

4. Run the tool:

```powershell
python main.py
```

Docker (PowerShell)

```powershell
docker build -t spotify2ytmusic .
docker run -it --rm `
  -v ${PWD}\.env:/app/.env `
  -v ${PWD}\browser.json:/app/browser.json `
  -v ${PWD}\match_cache.db:/app/match_cache.db `
  spotify2ytmusic --help
```

Notes
- If your headers file lives elsewhere, pass --headers "C:\path\to\browser.json".
- If execution policy blocks activation, use the temporary policy shown above.
- Spotify may require Premium for the app owner to access saved tracks and playlists.
