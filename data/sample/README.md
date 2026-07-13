# Synthetic demo dataset

Everything in this directory is synthetic and exists only to demonstrate the
software without distributing real admission data. Institution names contain
“示例”, records do not describe real applicants or outcomes, and numeric values
must not be used for an actual application decision.

The files are dedicated under CC0-1.0 as described in `DATA_LICENSE.md`.

Initialize a local demo database with:

```bash
python scripts/seed_demo_data.py --database data/demo.db
```

The command is idempotent. It creates or updates the same marked records and
does not import any external data.
