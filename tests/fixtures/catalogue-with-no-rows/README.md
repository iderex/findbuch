# A catalogue directory that holds no row

The one-change neighbour of `tests/fixtures/rows/`, which holds `euler.toml`.
`tests/test_verification_legs.py` points both fast verification legs at this
directory and at that one: over this directory the leg passes, over the other it
refuses, and the difference between the two is whether a `.toml` row is present.

Without this half of the pair a leg that refused every catalogue, including an
empty one, would satisfy the refusal test and nothing would notice.

This directory is not the real catalogue. `catalogue/` is, and rows land there
in milestone 6.
