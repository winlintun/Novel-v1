"""Verify RAG DB after the bugfix."""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

rag = sqlite3.connect('data/novel_v1_dataset.db')
rag.row_factory = sqlite3.Row

total = rag.execute('SELECT COUNT(*) AS c FROM translation_pairs WHERE novel_slug="a-will-eternal1"').fetchone()['c']

# Myanmar ratio distribution
good = rag.execute('SELECT COUNT(*) AS c FROM translation_pairs WHERE novel_slug="a-will-eternal1" AND myanmar_ratio >= 0.5').fetchone()['c']
wrong = rag.execute('SELECT COUNT(*) AS c FROM translation_pairs WHERE novel_slug="a-will-eternal1" AND myanmar_ratio < 0.1').fetchone()['c']
partial = rag.execute('SELECT COUNT(*) AS c FROM translation_pairs WHERE novel_slug="a-will-eternal1" AND myanmar_ratio BETWEEN 0.1 AND 0.5').fetchone()['c']

print(f'=== RAG DB verification for a-will-eternal1 ===')
print(f'Total pairs: {total}')
print(f'Good (MM ratio >= 0.5): {good} ({good/total*100:.1f}%)')
print(f'Partial (0.1-0.5): {partial} ({partial/total*100:.1f}%)')
print(f'Wrong (MM ratio < 0.1): {wrong} ({wrong/total*100:.1f}%)')

print(f'\n--- Wrong pairs (should be ZERO after fix) ---')
if wrong > 0:
    rows = rag.execute('SELECT en_text, my_text, auto_score FROM translation_pairs WHERE novel_slug="a-will-eternal1" AND myanmar_ratio < 0.1 ORDER BY auto_score DESC LIMIT 5').fetchall()
    for r in rows:
        print(f'  Score={r["auto_score"]:.3f}')
        print(f'    EN: {r["en_text"][:80]}')
        print(f'    MM: {r["my_text"][:80]}')
        print()
else:
    print('  None! All pairs have valid Myanmar text.')

print(f'\n--- Sample good pairs ---')
rows = rag.execute('SELECT en_text, my_text, auto_score FROM translation_pairs WHERE novel_slug="a-will-eternal1" AND myanmar_ratio >= 0.5 ORDER BY auto_score DESC LIMIT 5').fetchall()
for r in rows:
    print(f'  Score={r["auto_score"]:.3f}')
    print(f'    EN: {r["en_text"][:100]}')
    print(f'    MM: {r["my_text"][:100]}')
    print()

rag.close()
