# Security policy

## What this repository is, since the threat model follows from it

findbuch is a catalogue of the known integrable cases of rigid body dynamics,
together with the Python that reads one. A row is a TOML file carrying a
Hamiltonian, an additional integral, the parameter conditions the case holds
under and its domain, and the project exists so that each row is verified rather
than transcribed: symbolically that the Poisson bracket vanishes, numerically
that the integral stays constant along a trajectory.

In security terms that makes it a library plus a set of repository tools. There
is no server, no daemon, no hosted instance and no released service.
`pyproject.toml` declares no `[project.scripts]`, so installing the package puts
nothing on a PATH. There is no account, no session, no credential and no stored
secret in the tree. `docs/decisions/0011-data-stays-on-the-host.md` decided that
nothing about a run leaves the host, and that is enforced rather than promised:
`src/findbuch/invariants.py` refuses a socket-opening import on any shipped
path, and `.github/workflows/isolation.yml` runs the suite with outbound access
blocked.

Two more facts a reader should have before deciding whether a finding is
interesting. `catalogue/` holds no rows yet, only its README, and the package
version is 0.0.0. The code described below is real and runs; the data it is
built to carry has not been entered.

## Reporting a vulnerability

Private vulnerability reporting is the channel:

https://github.com/iderex/findbuch/security/advisories/new

I checked that it answers rather than assuming it:

    $ gh api repos/iderex/findbuch/private-vulnerability-reporting
    {"enabled":true}

If that ever stops being true, this section is wrong, and I would rather be told
about the shut door than have somebody give up quietly.

Tell me what you sent in, what happened, and what you expected instead. The
input itself is worth more than a description of it: `findbuch.validation` takes
a row file and `findbuch.expression.parse` takes a string, so a reproducer here
is usually one small TOML row or one formula string.

I promise no acknowledgement deadline and no fix deadline, and I am not going to
write one down in order to look responsive. A date I miss is worse than no date:
somebody told to expect an answer within a stated window, who hears nothing
after it, cannot tell a busy maintainer from a report that never arrived, and
has to guess which. Without a promised window there is nothing to misread. This
project is worked on in the open, so the issue tracker and the commit history
are a truer signal of whether anything is moving than a number in this file.

## Where the real boundary is

`src/findbuch/expression.py` is the one place in this project where input a
stranger wrote meets code that must do something with it. A row carries its
Hamiltonian and its integral as strings, and those strings are mathematics typed
in by whoever transcribed the paper.

That module never hands a formula to the computer algebra library's own parser,
which would be arbitrary code execution dressed as a Hamiltonian. The string is
parsed to a syntax tree by the standard library in `eval` mode, walked against
an allowlist of node kinds and an allowlist of nine functions, and only then
rebuilt as a symbolic object node by node. The symbol table is fixed before the
parse, from the structure's coordinates and the row's declared parameters, so an
identifier outside it is refused by name and never becomes a fresh free
variable. Three bounds sit around that: 512 characters checked before the string
is parsed at all, a nesting depth of 64 measured with an explicit stack, and an
expansion bound of 4096 terms applied afterwards. The module says outright that
there is no sandbox behind it and none is claimed. The grammar is the boundary,
so a hole in the grammar is the finding.

What I would act on, in rough order of how much it would matter:

- Any string reaching `findbuch.expression.parse` that causes something to be
  executed, a name outside the symbol table to be resolved, or an attribute to
  be reached inside SymPy.
- A string inside all three declared bounds that still makes the parser hang,
  exhaust memory, or take the interpreter down. Those bounds exist to make that
  unreachable, so such an input is a defect in a bound, not a big input.
- Anything leaving `findbuch.expression` that is neither a built object nor an
  `ExpressionRefused` carrying an identifier the module declares in `REFUSALS`.
  That is the property `src/findbuch/fuzz.py` exists to hold, and a way around
  it is a real finding even when the crash looks harmless.
- A row file or a structure file that makes `findbuch.validation` or
  `findbuch.structures` read or write outside the directory they were pointed
  at, or touch anything on the host beyond the files under it.
- An input to `findbuch.integrator` that escapes its iteration bound or drives
  unbounded memory. It is arbitrary precision arithmetic steered by numbers
  written as text in a file, so cost is an input there.
- Any path on which a shipped module opens a network connection. That
  contradicts 0011 directly and is worth reporting even if the connection goes
  somewhere harmless.
- Anything letting a pull request from outside reach a token, a release
  artefact, or the lockfiles. The workflows run with explicit `permissions`
  blocks, check out with `persist-credentials: false`, and none of them uses
  `pull_request_target`; a way around any of that is in scope.

## What is not a vulnerability here

A wrong row. A mistyped Hamiltonian, an integral that is not the one the source
stated, a missing parameter condition: those are correctness defects and belong
on the issue tracker in the open. That includes the worst case, a verification
that passes when it should fail. It is the most serious bug this project can
have and it is still a bug rather than an attack, and everybody reading the
catalogue is better served by that discussion being visible.

A refusal you disagree with. The grammar refuses decimal literals, comparisons,
attribute access, subscripts and every name outside the allowlist, and it treats
`pi` and `e` as undeclared. All of it is deliberate and argued in
`docs/decisions/0004-expression-grammar.md`. If a limit is too tight for a case
you are entering, open an issue with the formula that hit it. A good argument
there is welcome; it is not a security report.

Resource exhaustion from a file you handed the tool yourself. There is no
service to deny. An operator runs these tools on their own machine over their
own checkout, and a deliberately enormous input costing hours is that operator's
own decision. What is in scope, as above, is an input that stays inside the
declared bounds and costs more than those bounds promise.

A dependency advisory with no path shown through this code. `requirements.lock`
pins seven distributions with hashes: sympy, mpmath and jsonschema, which
`pyproject.toml` declares, and attrs, jsonschema-specifications, referencing and
rpds-py, which jsonschema brings with it. `tools/supply_chain.py` audits the
lockfiles against a register of exceptions that expires every entry. So I
already see the advisory. What I cannot see is whether it is reachable from
anything this project calls, and that reachability is the part worth writing to
me about.

A scanner report pasted without a reachable path. CodeQL, zizmor, Scorecard and
dependency review already run here. If a tool flagged something, send the input
that reaches it rather than the rule identifier.

Anything about a deployment or a running instance of findbuch. I run none. If
somebody has put this behind a network interface, they have built something this
repository does not ship, and its security is theirs.

## Versions and disclosure

Nothing has been released, the package version is 0.0.0, and `main` is the only
branch that receives fixes. When there is a release, this paragraph will be
replaced by one that says which versions I keep fixing.

Report privately first through the advisory link. Once a fix is on `main`, or
once we agree there is nothing to fix, publish whatever you like, and say so
publicly if I was slow. I will not ask anyone to sit on a finding indefinitely.
There is no bounty and no budget, and I would rather write that here than let
anyone spend an evening on this expecting otherwise.
