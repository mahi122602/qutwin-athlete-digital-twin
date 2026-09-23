"""Strict Samsung CSV decoding without skipping records or shifting columns."""
import csv
import io
import pandas as pd


def has_samsung_metadata(data):
    first = data.decode('utf-8-sig', errors='replace').splitlines()[:1]
    if not first:
        return False
    row = next(csv.reader(first), [])
    return bool(row and row[0].strip().lower().startswith(
        ('com.samsung.health.', 'com.samsung.shealth.')))


def read_samsung_csv(data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('latin1')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    records = [(reader.line_num, row) for row in reader if row]
    if not records:
        return pd.DataFrame()
    if has_samsung_metadata(data):
        records = records[1:]
    if not records:
        return pd.DataFrame()
    header = records[0][1]
    # Some exports terminate the header as well as each record with a comma.
    while header and header[-1] == '':
        header = header[:-1]
    if not header or any(not name.strip() for name in header):
        raise ValueError('Samsung CSV has an empty column name in its header.')
    if len(set(header)) != len(header):
        raise ValueError('Samsung CSV contains duplicate column names.')
    rows = []
    for line, row in records[1:]:
        if len(row) > len(header) and all(value == '' for value in row[len(header):]):
            row = row[:len(header)]
        if len(row) != len(header):
            raise ValueError(f'Samsung CSV line {line}: expected {len(header)} fields, found {len(row)}. No records were skipped.')
        rows.append(row)
    # Let pandas retain its ordinary numeric/empty-value interpretation only
    # after validating every record and reconstructing a rectangular CSV.
    cleaned = io.StringIO()
    writer = csv.writer(cleaned)
    writer.writerow(header)
    writer.writerows(rows)
    cleaned.seek(0)
    return pd.read_csv(cleaned, low_memory=False)
