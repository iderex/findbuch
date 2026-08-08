# 0003. What a row holds, and what file format it is written in

Decided in #4.

## The problem

The row is the product. Everything else in this repository exists to load it,
check it or hand it to somebody, so what a row holds decides what every later
part can do.

The four things named at the start are the Hamiltonian, the additional integral,
the parameter conditions and the domain of validity. Three more are needed
before a row can be checked or trusted at all.

The Poisson structure it lives on, because a formula without its bracket is not
a statement about anything.

The provenance, because a row whose source cannot be found again is a claim
rather than a transcription, and because the whole reason this catalogue
verifies rather than copies is that the sources contain errors.

The kind of validity being claimed, because a case that holds only on one level
set of an integral is a different mathematical statement from one that holds
everywhere, and the two are collapsed in more than one published table.

## The decision on format

One file per case, TOML, under `catalogue/`, with a generated JSON export as the
machine interface. The file name is the case identifier.

TOML for the source of truth because a person writes these by hand and will get
them wrong in YAML. YAML's implicit typing turns a bare parameter name into a
boolean and a version-shaped string into a float, and the failure is silent.
TOML has one string type that does not reinterpret its contents, it has
multi-line literal strings which is what a formula wants, and it parses with the
standard library rather than a dependency.

JSON for the export because every consumer already reads it, because JSON Schema
is a real validator with real tooling, and because an export that is generated
rather than maintained cannot drift from the source. The export is a build
product and is not edited. 0010 is where the export is argued as the only
supported interface.

Formulas are strings. Not nested expression trees, and not code. A tree in TOML
is unreadable, so nobody would proofread it against the paper, and proofreading
against the paper is the one thing a human contributor is uniquely good at here.
Code in a data file is a remote execution surface in a project that intends to
accept rows from strangers, and 0004 is where that boundary is drawn.

## The fields, and what each one means

`id`. The case identifier, in the form 0008 sets out. It is the file name and it
is never reused.

`name`. The display name a reader recognises, which is not parsed by anything.

`structure`. The identifier of the Poisson structure the row lives on, resolved
against the structure files 0002 declares. Required, with no default, because
the default would be e(3) and e(3) is the wrong answer for the family most
likely to be transcribed carelessly.

`hamiltonian`. The Hamiltonian, as an expression string over the coordinates of
the named structure and the parameters this row declares.

`integrals`. One or more additional integrals, each an expression string over
the same symbols. A list rather than a single field, because several cases carry
more than one additional integral and forcing them into separate rows would
duplicate the Hamiltonian and let the copies drift.

`parameters`. The parameter symbols, each with what it means physically. This is
the list the symbol table is built from, so a parameter that is not declared
here is not a free variable anywhere.

`conditions`. The parameter conditions, as expressions rather than prose, so
that they can be evaluated and reduced against rather than read.

`validity`. The kind of validity claimed, in the vocabulary 0005 fixes.
Required, with no default.

`domain`. The domain of validity: where in the phase space and in the parameter
space the claim is made.

`provenance`. The list of provenance entries, in the shape 0009 fixes. At least
one, because a row with no source is not a transcription of anything.

`note`. Free text, for the things that do not fit a field. It is read by people
and by nothing else.

## What the format does not decide

Whether a row is correct. The file format refuses shape and the schema in #20
refuses more of it, but neither of them is evidence about the mathematics. That
is what the two checkers are for, and the split is stated here so that nobody
reads a well-formed file as a verified one.

## Consequences

A consumer never reads the TOML. It reads the generated JSON and the published
schema, so the source format can change without breaking anyone, and the export
is where compatibility is owed.

Adding a field is adding it to the schema, to the export and to this record. A
field that exists in the files and in neither of the other two is a field no
reader can find.
