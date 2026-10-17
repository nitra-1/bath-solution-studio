# Sample price lists

Put one PDF per brand layout here, named after the reader, e.g. `keuco.pdf`.
PDFs are not committed (see .gitignore); the matching `<name>.expected.json` is.

`pytest` reads every PDF that has an expected file and checks the product and
article-number counts, so a change to one reader can't silently break another.

Create the expected file with:

    python scripts/try_reader.py tests/samples/<name>.pdf --brand "<Brand>" --write-expected
