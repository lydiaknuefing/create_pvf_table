# create_pvf_table

Populates a colour-coded phase volume fraction table in a LibreOffice Writer or Impress document from a CSV file.

## Usage

```
python main.py <csv_file> --format writer    # produces table_<name>.odt
python main.py <csv_file> --format impress   # produces table_<name>.odp
```

The output file is written to the current working directory.

## Input format

A two-row CSV with a header line and one data line:

```
File Name, Phase 0 Fraction, Phase 1 Fraction, ..., Phase N Fraction
<ignored>,  0.000022,         0.199944,         ..., 0.000011
```

- The first column (file name) is ignored.
- Fractions are multiplied by 100 to give Vol [%].
- Any number of phases is supported; the table is trimmed to match.

## Output

A three-column table with one row per phase:

| (colour) | Phase   | Vol [%]  |
|----------|---------|----------|
|          | Phase 0 | 0.0022   |
|          | Phase 1 | 19.9944  |
| …        | …       | …        |

Column widths, background colours, font, and alignment come from the template files.

## Dependencies

Python 3.12+, standard library only.
