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

### Windows (`.bat` files)
| File | Purpose | Usage |
|------|---------|-------|
| `translate.bat` | **Main launcher** - Double-click or run with arguments | `translate.bat --input file.md` |
| `run.bat` | Advanced launcher with detailed output | `run.bat --novel name --chapter 1` |

### Linux/Mac (`.sh` files)
| File | Purpose | Usage |
|------|---------|-------|
| `translate.sh` | **Main launcher** - One-click translation | `./translate.sh --input file.md` |
| `run.sh` | Advanced launcher with detailed output | `./run.sh --novel name --chapter 1` |
| `clean_cache.sh` | Standalone cache cleaner | `./clean_cache.sh` |

### Cross-Platform (Python)
| File | Purpose | Usage |
|------|---------|-------|
| `run.py` | Python launcher (all platforms) | `python run.py --input file.md` |
| `diagnose.py` | Diagnostic tool | `python diagnose.py` |

---

## 🪟 Windows Users

### Option 1: Double-Click (Simplest)
1. Double-click `translate.bat`
2. It will show usage instructions

### Option 2: Run with Arguments
```cmd
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

## 🐧 Linux Users

### First Time Setup
```bash
# Make scripts executable
chmod +x translate.sh run.sh clean_cache.sh
```

### Run Translation
```bash
# Translate a single file
./translate.sh --input data/input/reverend-insanity/reverend-insanity_0002.md

# Translate specific chapter
./translate.sh --novel "reverend-insanity" --chapter 2

# Translate all chapters
./translate.sh --novel "reverend-insanity" --all
```

### Just Clean Cache
```bash
./clean_cache.sh
```

---

## 🍎 Mac Users

### First Time Setup
```bash
# Make scripts executable
chmod +x translate.sh run.sh clean_cache.sh
```

### Run Translation
```bash
# Translate a single file
./translate.sh --input data/input/reverend-insanity/reverend-insanity_0002.md

# Translate specific chapter
./translate.sh --novel "reverend-insanity" --chapter 2

# Translate all chapters
./translate.sh --novel "reverend-insanity" --all
```

**Note:** If you get "Permission denied", run:
```bash
chmod +x translate.sh
```

---

## 🔧 Advanced Usage

### Skip Cache Cleaning (Rarely Needed)
If you want to skip cache cleaning for faster startup:
```bash
# Windows
python run.py --no-clean --input file.md

# Linux/Mac
python3 run.py --no-clean --input file.md
```

### Manual Cache Cleaning
```bash
# Windows Command Prompt
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
del /s /q *.pyc

# Windows PowerShell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File -Filter "*.pyc" | Remove-Item -Force

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

**Windows:**
```cmd
translate.bat --input data\input\reverend-insanity\reverend-insanity_0002.md
```

**Linux/Mac:**
```bash
./translate.sh --input data/input/reverend-insanity/reverend-insanity_0002.md
```

**What happens:**
1. 🧹 Cleans Python cache
2. 🔍 Auto-detects English source
3. 🤖 Selects `padauk-gemma:q8_0` model
4. 🔄 Uses `way1` (EN→MM direct)
5. 🚀 Starts translation

### For Chinese Novels (e.g., 古道仙鸿)

**Windows:**
```cmd
translate.bat --input data\input\古道仙鸿\古道仙鸿_0001.md
```

**Linux/Mac:**
```bash
./translate.sh --input data/input/古道仙鸿/古道仙鸿_0001.md
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

### "Permission denied" (Linux/Mac)
**Solution:** Make scripts executable
```bash
chmod +x translate.sh run.sh clean_cache.sh
```

### "Wrong model still being used"
**Solution:** Use the launchers! They clean cache automatically.

### "Changes not taking effect"
**Solution:** Run `translate.bat` (Windows) or `./translate.sh` (Linux/Mac) instead of running Python directly

### "Python not found" (Windows)
**Solution:** Make sure Python is installed and in your PATH. Try `py` instead of `python`.

### "python3: command not found" (Linux/Mac)
**Solution:** Try `python` instead of `python3`, or install Python 3.

---

## 💡 Pro Tips

### Windows
1. **Always use launchers** - Don't run `py -m src.main` directly
2. **Pin translate.bat to taskbar** - For quick access
3. **Create desktop shortcuts** - Right-click → Send to → Desktop
4. **Drag and drop files** - Onto translate.bat for instant translation

### Linux/Mac
1. **Create alias** - Add to your `~/.bashrc` or `~/.zshrc`:
   ```bash
   alias translate='~/path/to/novel_translation_project/translate.sh'
   ```
2. **Create symlink** - For system-wide access:
   ```bash
   sudo ln -s ~/path/to/translate.sh /usr/local/bin/translate
   ```
3. **Use tab completion** - After `chmod +x`, bash will tab-complete the script names

---

## 📊 Comparison

| Method | Cache Cleaning | Auto-Detection | Recommended For |
|--------|---------------|----------------|-----------------|
| `py -m src.main` | ❌ No | ✅ Yes | ⚠️ Only if manually clean cache |
| `python3 -m src.main` | ❌ No | ✅ Yes | ⚠️ Only if manually clean cache |
| `translate.bat` | ✅ Yes | ✅ Yes | ✅ **Windows users** |
| `translate.sh` | ✅ Yes | ✅ Yes | ✅ **Linux/Mac users** |
| `run.bat` | ✅ Yes | ✅ Yes | ✅ Windows - detailed output |
| `run.sh` | ✅ Yes | ✅ Yes | ✅ Linux/Mac - detailed output |
| `run.py` | ✅ Yes | ✅ Yes | ✅ All platforms |

---

## 🆘 Need Help?

Run diagnostics:
```bash
# Windows
python diagnose.py

# Linux/Mac
python3 diagnose.py
```

Or check the main README: `README.md`
