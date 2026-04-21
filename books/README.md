# Books Directory

This directory contains translated novels in a structured format for the Reader App.

## Directory Structure

```
books/
├── book1/
│   ├── metadata.json          # Book metadata and chapter list
│   └── chapters/
│       ├── chapter1.md        # Translated chapter 1
│       ├── chapter2.md        # Translated chapter 2
│       └── ...
├── book2/
│   ├── metadata.json
│   └── chapters/
│       └── ...
```

## metadata.json Format

```json
{
  "id": "book1",
  "title": "Novel Title in Burmese",
  "author": "Author Name",
  "chapters": [
    {
      "number": 1,
      "title": "Chapter 1 Title",
      "file": "chapter1.md"
    },
    {
      "number": 2,
      "title": "Chapter 2 Title",
      "file": "chapter2.md"
    }
  ]
}
```

## Flow

```
[Chinese .md files]
        ↓
[AI Translation (Ollama / API)]
        ↓
[Myanmar .md files]
        ↓
[books/book_id/chapters/]
        ↓
[Reader App UI]
```

The translation pipeline automatically:
1. Reads from `input_novels/` (Chinese .md files)
2. Translates using configured AI model
3. Saves to `books/{book_id}/chapters/`
4. Updates `metadata.json` for the Reader App

## Usage

To read translated novels:

```bash
python reader_app.py
```

Then open http://localhost:5000 in your browser.
