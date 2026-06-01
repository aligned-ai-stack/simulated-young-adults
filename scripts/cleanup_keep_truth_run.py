import json
import sqlite3

KEEP = [
    "session_d3fa0ecf77d44345b5c1b5b8ed8a47fe",
    "session_9845165976084217b82e2e02a7f4fb52",
    "session_1a41d1535cc14c749bf87a79b772c5e5",
    "session_c1014da15a494e7fab90e67a9620d419",
    "session_104e260b957b414fa90d4158058ba1ff",
    "session_dbdd2c954e27448c873bb3ad3429a2dd",
    "session_c542e6c1dcfd4b8d84430bacad53404e",
    "session_eb5cab1e213a414db6f8c03d3f911de1",
    "session_3ed93e8151b64b6d86d4b7f70a2f881a",
    "session_b8fad1c80a21428aa24b620eaa62a625",
]

con = sqlite3.connect("data/simulation.sqlite3")
cur = con.cursor()
delete = [
    row[0]
    for row in cur.execute("SELECT id FROM sessions").fetchall()
    if row[0] not in KEEP
]

if delete:
    placeholders = ",".join("?" for _ in delete)
    cur.execute(f"DELETE FROM trace_events WHERE session_id IN ({placeholders})", delete)
    cur.execute(f"DELETE FROM turns WHERE session_id IN ({placeholders})", delete)
    cur.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", delete)

con.commit()
counts = {
    table: cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    for table in ["sessions", "turns", "trace_events"]
}
con.close()
print(json.dumps({"deleted": len(delete), "counts": counts}, indent=2))
