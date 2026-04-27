# 🚀 One-Click Launchers

These launcher scripts automatically clean Python cache before running to ensure you always execute the latest code.

## Problem

Python caches compiled code in `__pycache__` folders. When you update the translation system, old cached code can still run, causing issues like:
- Wrong models being used (e.g., `qwen:7b` instead of `padauk-gemma:q8_0`)
- Old bugs persisting after fixes
- Configuration changes not taking effect

## Solution

Use these launchers that **automatically clean cache** before each run!

---

## 📦 Files

| File | Purpose | Usage |
|------|---------|-------|
| `translate.bat` | **Main launcher** - Double-click or run with arguments | `translate.bat --input file.md` |
| `run.bat` | Advanced launcher with detailed output | `run.bat --novel name --chapter 1` |
| `run.py` | Python launcher (cross-platform) | `python run.py --input file.md` |
| `diagnose.py` | Diagnostic tool to check configuration | `python diagnose.py` |

---

## 🪟 Windows Users

### Option 1: Double-Click (Simplest)
1. Double-click `translate.bat`
2. It will show usage instructions

### Option 2: Run with Arguments
```bash
# Translate a single file
translate.bat --input data\input\reverend-insanity\reverend-insanity_0002.md

# Translate specific chapter
translate.bat --novel "reverend-insanity" --chapter 2

# Translate all chapters
translate.bat --novel "reverend-insanity" --all
```

### Option 3: Drag and Drop
1. Find your `.md` file in Windows Explorer
2. Drag it onto `translate.bat`
3. It will automatically translate the file!

---

## 🐧 Linux/Mac Users

```bash
# Make executable and run
chmod +x run.py
python3 run.py --input data/input/novel/chapter.md
```

---

## 🔧 Advanced Usage

### Skip Cache Cleaning (Rarely Needed)
If you want to skip cache cleaning for faster startup:
```bash
python run.py --no-clean --input file.md
```

### Manual Cache Cleaning
```bash
# Windows
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
del /s /q *.pyc

# Linux/Mac
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

---

## 📋 What Gets Cleaned?

Each launcher automatically removes:
- ✅ All `__pycache__` directories
- ✅ All `.pyc` compiled files
- ✅ All `.pyo` optimized files

---

## 🎯 Quick Start

### For English Novels (e.g., Reverend Insanity)
```bash
translate.bat --input data\input\reverend-insanity\reverend-insanity_0002.md
```

**What happens:**
1. 🧹 Cleans Python cache
2. 🔍 Auto-detects English source
3. 🤖 Selects `padauk-gemma:q8_0` model
4. 🔄 Uses `way1` (EN→MM direct)
5. 🚀 Starts translation

### For Chinese Novels (e.g., 古道仙鸿)
```bash
translate.bat --input data\input\古道仙鸿\古道仙鸿_0001.md
```

**What happens:**
1. 🧹 Cleans Python cache
2. 🔍 Auto-detects Chinese source
3. 🤖 Selects `alibayram/hunyuan:7b` for Stage 1
4. 🤖 Selects `padauk-gemma:q8_0` for Stage 2
5. 🔄 Uses `way2` (CN→EN→MM pivot)
6. 🚀 Starts translation

---

## 🔍 Troubleshooting

### "Wrong model still being used"
**Solution:** Use the launchers! They clean cache automatically.

### "Changes not taking effect"
**Solution:** Run `translate.bat` instead of `py -m src.main`

### "Permission denied"
**Solution:** Run Command Prompt as Administrator

---

## 💡 Pro Tips

1. **Always use launchers** - Don't run `py -m src.main` directly
2. **Pin translate.bat to taskbar** - For quick access
3. **Create desktop shortcuts** - Right-click → Send to → Desktop
4. **Use diagnose.py first** - If something seems wrong, run diagnostics

---

## 📊 Comparison

| Method | Cache Cleaning | Auto-Detection | Recommended |
|--------|---------------|----------------|-------------|
| `py -m src.main` | ❌ No | ✅ Yes | ⚠️ Only if you manually clean cache |
| `translate.bat` | ✅ Yes | ✅ Yes | ✅ **Recommended** |
| `run.bat` | ✅ Yes | ✅ Yes | ✅ Detailed output |
| `run.py` | ✅ Yes | ✅ Yes | ✅ Cross-platform |

---

## 🆘 Need Help?

Run diagnostics:
```bash
python diagnose.py
```

Or check the main README: `README.md`
