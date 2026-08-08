# 0009. What a row records about where it came from

Decided in #10.

## The problem

This project is built on the position that a century of multilingual
transcription contains errors. That position obliges it to say, per row, exactly
where the row came from.

A citation like a book title and a page number is not enough for this purpose.
When the symbolic checker rejects a row, the next question is always the same:
is the paper wrong, is the transcription wrong, or is the checker wrong.
Answering it needs to know which edition, which page, which equation number, and
in which notation the source stated the thing, because the sources do not agree
on notation and a change of convention is the most common way a correct formula
becomes a wrong row.

## The decision

Provenance is a list rather than a single field, because a row usually has more
than one source and the relationship between them is the interesting part.

## The fields of a provenance entry

`reference`. The bibliographic reference, precise enough to identify one
edition: author, title, journal or publisher, year, and the edition where more
than one exists. A reference that resolves to two different printings resolves
to two different tables often enough to matter.

`language`. The language of that source, from the set 0012 works in. This is the
field the coverage report counts on, so it records the language of the text that
was actually read, not the language a translation of it exists in.

`location`. The precise location within the source: the page, and the equation
or theorem number where the source numbers them. A page alone sends the next
reader to a page.

`notation`. The notation convention the source used. Which frame, which sign
convention for the bracket, and what the source called the parameters. This
field matters more than it looks: a row that carries it can be re-derived from
the source by a reader, and a row that does not carries an unrecorded conversion
step that nobody can check.

`role`. What this source is to this row, from the three below.

`transformation`. Where the transcription required a change of variables, the
transformation is recorded here as an expression rather than described in prose,
so that it can be applied and inverted mechanically. Prose describing a change
of variables is the step a reader has to redo by hand, which is the step this
catalogue exists to remove.

`read`. Whether the source was read directly or the row was taken from something
that quotes it. A row transcribed from a survey rather than from the original
says so here, because a survey that copied an error propagates it, and the
catalogue should be able to report which of its rows have never been checked
against an original.

## The three roles

`original`. The paper that first stated the case.

`survey`. A table or a book that reproduces it. A survey entry is a real source
and is recorded as one, and it is also the thing the coverage report treats as
weaker evidence than an original.

`correction`. A later source that changed something: a sign, a condition, a
domain, or the claim that the case is what an earlier source said it was. A
correction entry carries what it changed in its notation field and its location,
so that the disagreement between two sources is visible in the row rather than
resolved silently by whoever entered it.

## What this enables

A report over the whole catalogue answering which rows rest only on a survey,
which rest on a source in a language nobody in the project reads, and which have
a recorded conversion that has never been checked.

That report is the point of the fields. It is a statement of what the catalogue
does not know, and it is what makes the catalogue honest rather than confident.
#42 is where it lands, and it leads with the gaps rather than with the count of
rows that passed.

## Consequences

At least one provenance entry is required per row, and the schema refuses a row
with none. A row with no source is not a transcription of anything, and the
verification legs would happily pass it.

The fields are required per entry rather than encouraged. An entry that omits
its notation is the case this record was written for, and an optional field is
the one that gets left out on the rows that were hardest to enter, which are the
rows most likely to be wrong.
