# 0004. The expression grammar and how a formula string becomes an object

Decided in #5.

## The problem

A formula arrives as a string in a file that a stranger may have written.
Turning that string into something the checkers can compute with is the single
most dangerous operation in this project, and it is the one most likely to be
done carelessly.

The obvious implementation hands the string to the computer algebra library's
own parser. That parser is, in its usual configuration, a path to arbitrary code
execution. It will construct and evaluate things that were never intended, and a
file that reads like mathematics can do something else entirely. A public
catalogue that invites contributions and then executes them is a supply chain
problem wearing a lab coat.

The second problem is quieter and will cost more. An unrestricted parser accepts
a symbol nobody declared. It treats a typo as a new free variable, and a bracket
computed against an extra free variable can vanish for a reason that has nothing
to do with the case being verified. A row with a mistyped parameter that passes
verification is worse than one that fails.

## The decision

A restricted grammar, parsed against a fixed symbol table, with no evaluation of
anything the file supplies.

The grammar admits exactly these:

- numeric literals, integer and rational
- symbols that are present in the symbol table
- addition, subtraction, multiplication and division
- powers with an integer exponent
- calls to functions on a named allowlist

Nothing else. Attribute access, calls to functions that are not on the
allowlist, indexing, comparison, assignment and anything else resembling a
statement are refused at parse time, with a message naming the offending token
and its position.

## The symbol table rule

The symbol table is built before the parse, from two sources and no others: the
coordinates and parameters of the structure the row names, and the parameters
the row itself declares.

An identifier that is not in that table is an error naming the identifier. It is
never a new free variable. This is the rule that turns a mistyped parameter into
a red row rather than a silent extra degree of freedom, and it is the reason the
table is built before the parse rather than grown during it.

## The library parser is not used

The library's convenience parser is not called from the loading path, in any of
its spellings. Parsing is a walk of a syntax tree against the grammar above, and
the symbolic object is constructed node by node from that walk.

There is no sandbox behind this boundary and none is claimed. The grammar is the
boundary.

The prohibition is proved rather than remembered. A test patches the library's
parser to raise, runs the full loader over the catalogue, and requires the load
to succeed, so a reintroduction of the convenience call fails the suite rather
than passing quietly.

## What proves it bites

A corpus of files that must be refused, each one a plausible mistake or a
plausible attack rather than an obviously invalid string. Refusal is asserted
per file against the expected refusal identifier, not against the fact that
something was raised. Asserting that a call raised is not evidence that it
raised for the stated reason.

Asserting the identifier is what stops a later widening of the grammar from
quietly making the corpus pass.

## Consequences

Some formulas in the literature cannot be entered as written and need a change
of variables or a rewriting first. That is a cost this record accepts. The
rewriting is recorded with the row, where a reader can see it, rather than
absorbed by a parser that guesses what was meant.
