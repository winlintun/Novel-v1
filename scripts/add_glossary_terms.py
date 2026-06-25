"""Add character name glossary entries for a-will-eternal1 via direct SQL."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from src.db.connection import DatabaseConnection

db = DatabaseConnection()
novel_id = 'novel_a_will_eternal1'

# Check if entries already exist
existing = db.fetchone(
    "SELECT id FROM glossary_terms WHERE novel_id=? AND source_term=? AND scope='novel'",
    (novel_id, 'Bai Xiaochun')
)
if existing:
    print(f"Bai Xiaochun already exists (id={existing['id']})")
else:
    db.execute(
        """INSERT INTO glossary_terms (novel_id, source_term, target_term, category, status, chapter_first_seen, confidence, scope)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (novel_id, 'Bai Xiaochun', 'ပိုင်ရှောင်ချေး', 'character', 'approved', 3, 1.0, 'novel')
    )
    print("Added Bai Xiaochun -> ပိုင်ရှောင်ချေး")

existing2 = db.fetchone(
    "SELECT id FROM glossary_terms WHERE novel_id=? AND source_term=? AND scope='novel'",
    (novel_id, 'Xu Baocai')
)
if existing2:
    print(f"Xu Baocai already exists (id={existing2['id']})")
else:
    db.execute(
        """INSERT INTO glossary_terms (novel_id, source_term, target_term, category, status, chapter_first_seen, confidence, scope)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (novel_id, 'Xu Baocai', 'ရှူ့ပေါ့ချိုင်', 'character', 'approved', 3, 1.0, 'novel')
    )
    print("Added Xu Baocai -> ရှူ့ပေါ့ချိုင်")

# Verify
print("\nVerification:")
for name in ['Bai Xiaochun', 'Xu Baocai']:
    row = db.fetchone(
        "SELECT * FROM glossary_terms WHERE novel_id=? AND source_term=?",
        (novel_id, name)
    )
    if row:
        print(f"  OK: {row['source_term']} -> {row['target_term']} ({row['category']}) [{row['status']}]")
    else:
        print(f"  MISSING: {name}")
