# 0010. The interface consumers depend on

Decided in #11.

## The problem

This catalogue is meant to be used as a test corpus by other software, and as a
benchmark by machine learning work on physics. The natural thing for a consumer
to do is to import the loader and walk the source files.

That would make every field name and every implementation detail a public
interface, so that a refactor here breaks a build somewhere else. It would also
mean each consumer writes its own parser for the formula strings, which is the
transcription problem again, one layer up, in a place where nobody would notice
it going wrong.

## The decision

The supported interface is a single generated JSON document per release,
validated against a published schema, plus the schema itself.

Nothing else is a supported interface. The loader, the checkers, the internal
layout, the file format of a row and the names of its fields are all free to
change, and a consumer that reads them has taken on a risk this project does not
carry for them.

Alongside the catalogue document, a structures document holding the bracket
tables and the Casimirs, so that a consumer can compute on the same structures
without reimplementing them from a paper.

A small reference reader ships with the project and is what consumers are
pointed at, so that reading the export does not become five slightly different
implementations of the same thing.

## What the export carries per row

The identifier, the status and the revision. The structure identifier. The
formulas. The parameters and conditions. The validity kind and its constraints.
The domain. The aliases. The provenance.

And the result of the last verification of that row, with the commands and the
numbers behind it.

That last part is not decoration. It is what lets a consumer tell a verified row
from one that has never passed, without running anything. A catalogue that ships
rows without their verification state invites every consumer to assume the state
is green, and some of them will be right.

## The version policy

The schema is versioned separately from the catalogue content, and the schema
version is carried in the document.

Adding a field is a minor version. Consumers ignore what they do not know.

Removing a field, or reinterpreting an existing one, is a major version. Both
versions are published for at least one release, so that nothing breaks on the
day of the change.

The catalogue content has its own version, because a release that adds rows and
changes no field is not a change to the interface and should not read as one.

## Why not a service

A consumer that has to reach a server to get the catalogue cannot run offline,
cannot pin a version reliably, and has acquired a dependency on somebody keeping
a machine running.

A file in a release is a better contract than an endpoint, and it costs nothing
to host.

## Consequences

Every field a consumer needs has to be in the export, so a field that exists
only internally is a decision to keep it out of the interface rather than an
oversight. Where a consumer needs something the export does not carry, the
repair is to add it to the export and bump the schema, not to point them at the
internals.
