# POSCUS AI — Sure Shot AI Pro

> Dragon Neural Engine · BIG/SMALL & COLOUR Prediction App

## 🚀 Deploy on Render

1. Upload all files to GitHub
2. Go to [render.com](https://render.com) → New → **Web Service**
3. Connect your GitHub repo
4. Set the following:

| Field | Value |
|-------|-------|
| Environment | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python app.py` |

5. Click **Deploy** ✅

## 📁 Files

| File | Purpose |
|------|---------|
| `index.html` | Main app |
| `app.py` | Flask web server |
| `requirements.txt` | Python dependencies |
| `runtime.txt` | Python version |
| `Dockerfile` | Docker config |
| `Procfile` | Process config |
| `render.yaml` | Render auto-config |
| `*.png` | Platform logos |

## ⚙️ Local Run

```bash
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:5000`
