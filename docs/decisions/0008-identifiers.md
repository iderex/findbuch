# 0008. The case identifier, and how a correction does not break a consumer

Decided in #9.

## The problem

A catalogue that other software depends on has to be able to correct itself
without breaking the thing that depends on it.

Identifiers get used. A benchmark paper cites a case by its identifier, another
project pins a row, and then the row turns out to be wrong: a transcribed sign,
a missing parameter condition, a case that was really two cases. If identifiers
are reused for corrected content, everyone who cited one is now citing something
else and nobody can tell. If identifiers are never reusable, the catalogue
accumulates dead names.

Underneath that sits a second question. The same case appears in three surveys
under three names, in different variable conventions, and it is genuinely not
obvious whether two rows are the same case in different clothes or two different
cases.

## The identifier form

Identifiers are opaque, stable and never reused.

The form is a short slug derived from the conventional name, with a
discriminator where one is needed: `kovalevskaya`, `goryachev-chaplygin`,
`clebsch`.

The slug is not parsed by anything. It is a name. Any information a consumer
wants about a row comes from a field of that row, never from the shape of its
identifier. A consumer that splits an identifier on its hyphens to learn
something is relying on an accident, and the record says so here so that nobody
has to discover it.

## Correction, and when an identifier changes

A correction to a row keeps the identifier and bumps the row's revision, which
the export carries.

A correction that changes what the row is about, rather than fixing how it was
written, gets a new identifier. The old identifier is kept with a status of
superseded and a pointer to the new one.

The line between the two is a judgement, and the rule that decides it is
whether a consumer's results would change. If they would, it is a new
identifier.

## The three statuses

`active`. The row is a current statement about a case.

`superseded`. The row has been replaced by another identifier, which it points
at. The row stays, so that a citation of it still resolves.

`retracted`. The row turned out not to be a real case. It keeps its identifier
and it keeps its provenance, because the fact that a published table contains it
is exactly the kind of thing this catalogue should record rather than quietly
drop.

Nothing is deleted under any of the three.

## Aliases

Sameness across sources is not decided by the identifier.

Where two published names denote the same case, one row holds it and the other
names are recorded as aliases, each with the source that uses it. Where it is
unclear whether two published names denote one case, the row says that in a
field rather than pretending to know.

The alias list is what lets a reader who arrived from one particular book find
the row. Without it, a catalogue with correct contents is still unusable by
somebody holding the wrong survey.

## Consequences

The catalogue grows monotonically in identifiers. That is the cost, and it is
paid on purpose: a name that once resolved keeps resolving, and a reader
chasing a citation from an old paper lands on a row that tells them what
happened rather than on nothing.
