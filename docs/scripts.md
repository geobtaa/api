To reindex remote Elasticsearch
source .kamal/secrets
kamal app exec --roles web "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/verify_h3_index.py'"

To verify remote H3 hexagons
source .kamal/secrets
kamal app exec --roles web "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/verify_h3_index.py'"