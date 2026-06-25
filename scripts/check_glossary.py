"""Check which novel IDs exist in the glossary DB."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from src.db.connection import DatabaseConnection, get_connection

db = DatabaseConnection()
from src.db.repositories import GlossaryRepository
repo = GlossaryRepository(db)

# Use raw query to get distinct novel IDs
conn = db._connection
cursor = conn.execute("SELECT DISTINCT novel_id FROM glossary_terms WHERE novel_id IS NOT NULL ORDER BY novel_id")
rows = cursor.fetchall()
print("Novel IDs in DB:")
for row in rows:
    print(f"  '{row[0]}'")

# Check specific names under each novel_id
for novel_id in [r[0] for r in rows]:
    for name in ['Bai Xiaochun', 'Xu Baocai']:
        t = repo.get_term_by_source(novel_id, name)
        if t:
            s = t.get('source_term', '?')
            tg = t.get('target_term', '?')
            c = t.get('category', '?')
            st = t.get('status', '?')
            print(f"  [{novel_id}] {s} -> {tg} ({c}) [{st}]")
