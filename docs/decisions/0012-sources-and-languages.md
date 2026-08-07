# 0012. Which sources can be read directly, and what happens to the ones that cannot

Decided in #13.

## Why this is decided before the schema

The literature of this field is in four languages. Which of them can be read
directly by this project decides what a provenance entry has to record, and
discovering the gap after the schema has been built around an assumption is a
far more expensive way to find out.

## The four languages and the sources in each

German. Hess in Mathematische Annalen 1890, Staude in Crelle 1894, and a good
deal of the surrounding classical work. Readable directly. The volumes are
digitised and freely available, so the original can be put in front of a reader
rather than paraphrased. This is an advantage rather than an obstacle: the
German sources are the ones least often checked by the later English literature,
which makes them the likeliest place for an uncorrected error to be sitting.

English. Leimanis 1965, Yehia's 1999 paper in Journal of Physics A and his later
book, the English editions of the Russian surveys, and most of the recent work.
Readable directly.

Russian. Bobylev, Dokshevich, Gorr, and much of the primary literature that
Borisov and Mamaev's survey draws on. Not readable directly. Some of it exists
in translation and some does not, and the translated editions do not always
carry the same tables as the originals.

Ukrainian. Parts of the later Gorr and Maznev material. Some of the journals
that carried it no longer exist, which makes locating an article a separate
problem from reading it.

## The build order

Rows are built in the order the sources allow. The English and German sources
are worked first, because a row from one of them can be checked against the
original by a reader of this project.

Rows whose only source is Russian or Ukrainian are still entered. Leaving them
out would misrepresent the field, and a catalogue that quietly stops where its
reader's languages stop is a worse artefact than one that says where it stopped.

## An unread original is recorded, not hidden

A row resting on an original nobody here has read is marked as such, and the
coverage report counts those rows separately.

Such a row is not a lesser row in terms of verification. The two checkers do not
care what language the paper was in; they check the mathematics as entered. What
the marking records is a different risk, and the distinction is worth stating
exactly: a checker can prove that the entered formulas are consistent under the
declared structure and conditions. It cannot prove that they are what the paper
said.

Where a case is available only through a survey that reproduced a Russian or
Ukrainian original, the row records both, with the survey named as the source
actually read.

The provenance carries the language of every source, so that this is a field a
reader can count rather than an impression they form.

## A translation carries a record of how it was produced

Translation, where it happens, is a separate act with its own record: what was
translated, by what means, and by whom or by what.

A machine translation is recorded as a machine translation. A reader deciding
how much to trust a row deserves to know which kind of reading stands behind it,
and a translation whose origin is unrecorded reads as a human one.

Whether translated passages may be published in this repository at all is a
separate question about copyright, and it is not settled here. This record
governs how a translation is recorded once it exists.

## Consequences

The provenance schema needs a language field, a role field distinguishing an
original from a survey that reproduced it, and a field recording whether the
source has been read by anyone here. The coverage report needs to lead with the
counts those fields make possible, because the number of rows resting on an
unread original is one of the two numbers a reader deciding whether to depend on
this catalogue most needs.
