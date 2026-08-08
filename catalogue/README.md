# catalogue

The rows live here, one file per case, and nothing else does.

A row is a single integrable case of rigid body dynamics: the Poisson structure
it lives on, the Hamiltonian, the additional integral, the parameter conditions
under which the case holds, the domain, what kind of validity it claims, and
where it was read from. `docs/decisions/0003-row-format.md` fixes the fields and
says why the source of truth is TOML and the JSON is generated from it.

The directory is empty of rows today. The schema and the loader that refuses a
malformed row are #20, and the first three rows, Euler, Lagrange and
Kovalevskaya, are #23.

What does not belong here: generated files of any kind, including the JSON
export, which is built from these rows rather than kept beside them; prose about
the mathematics, which belongs in the row it is about or in `docs/`; and scans
or copies of the source papers, which is an open question in #1 and not settled
by this file.
