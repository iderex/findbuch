# Quality parity with the target gate

Written for #47. The rest of milestone 8 builds the pieces this document maps.

## The target

The target is https://github.com/Flowfin/jellyfin-plugin-sso. Its default branch
is protected by a repository ruleset named `Protect main and 5.0`, active, with
no bypass actors, and with thirteen required status checks.

Read back on 2026-08-07:

    gh api repos/Flowfin/jellyfin-plugin-sso/rulesets/18802863 \
      --jq '{name, enforcement, bypass_actors, refs: .conditions.ref_name.include}'
    {"bypass_actors":[],"enforcement":"active","name":"Protect main and 5.0",
     "refs":["refs/heads/main","refs/heads/5.0"]}

    gh api repos/Flowfin/jellyfin-plugin-sso/rules/branches/main \
      --jq '.[] | select(.type=="required_status_checks")
                | .parameters.required_status_checks[].context'
    build
    ABI floor build
    Package (JPRM) / Build package
    Package (JPRM) / Generate SBOM
    CodeQL
    Analyze (csharp)
    DCO sign-off
    Deterministic PR-hygiene checks
    Enforce greppable invariants
    Reject Trojan Source Unicode
    Audit workflows (zizmor)
    prettier
    dependency-review

The commands are here rather than only the list, because a list in a document
drifts against the ruleset that decides it. Re-run them before relying on this
section.

## The mapping, and a reason for every deviation

`build` becomes `build`, meaning the package builds from a clean checkout and
imports. Same question, no deviation. Built by #51.

`ABI floor build` becomes `dependency floor build`. There is no host application
to be loaded by here, so the compatibility floor is the lowest declared
interpreter and library version rather than a server interface, and the check
builds and tests against those rather than against the lockfile. Built by #52.

`Package (JPRM) / Build package` becomes `package`. The packaging tool differs
because the artefact is an installable package rather than a plugin bundle. The
question it answers, whether the thing actually packages, is unchanged. Built by
#51.

`Package (JPRM) / Generate SBOM` becomes `SBOM`. Same obligation, different
generator for a different ecosystem. Built by #51.

`CodeQL` stays `CodeQL`, and `Analyze (csharp)` becomes `Analyze (python)`. The
language differs, the analysis does not. The actions analysis is kept as well,
because this repository has workflows worth analysing. Built by #48.

`DCO sign-off` is unchanged and is already in this tree. See below.

`Deterministic PR-hygiene checks` is adopted with this repository's own rules.
The mechanism carries over unchanged; the rules it enforces are per repository,
which is why the name is the same and the contents are not. Built by #49.

`Enforce greppable invariants` is adopted, and the invariants themselves are
different because they are about this project's own hazards rather than about a
plugin's. What they are belongs to #50, which builds this row.

`Reject Trojan Source Unicode` is unchanged and is already in this tree. It
matters more here than on the target, because a bidirectional override inside a
formula string is exactly the kind of thing this catalogue would carry into a
consumer. See below.

`Audit workflows (zizmor)` is unchanged and is already in this tree. See below.

`prettier` is dropped and replaced by `lint and format`. There is no JavaScript
and no stylesheet in this repository, and the formatting obligation lands on the
source and on the catalogue files instead, where a consistent format is what
makes a diff between two rows readable. Built by #16, which is in milestone 2
rather than in this one, because the gate needs it long before parity is the
question.

`dependency-review` is unchanged and is already in this tree. See below. The
locked-mode install and the vulnerability scan of the resolved set are the same
obligation applied to the full dependency graph rather than to the diff, and
they are built by #53.

## What is already in this tree

Four of the thirteen are satisfied by workflows that already exist here, and
they are not rebuilt by this milestone. Three of the four carry a job name, and
the command below names those three files rather than reading the whole
directory. A directory-wide read also returns the rows this milestone is
building, so its output moves every time one of them lands and stops matching
the sentence it was pasted under, which is what happened between #47 and #73.

    git grep -nE '^    name: ' -- .github/workflows/dco.yml \
      .github/workflows/unicode-guard.yml .github/workflows/zizmor.yml
    .github/workflows/dco.yml:24:    name: DCO sign-off
    .github/workflows/unicode-guard.yml:23:    name: Reject Trojan Source Unicode
    .github/workflows/zizmor.yml:41:    name: Audit workflows (zizmor)

`dependency-review` is the fourth of them. It is absent from that output because
its job deliberately carries no `name:`, not because it is missing from the
tree. The check-run name then defaults to the job id, which is the literal
string a required status check would match, and the reason is written in the
workflow file beside the job:

    git grep -nE '^  dependency-review:' -- .github/workflows/dependency-review.yml
    .github/workflows/dependency-review.yml:20:  dependency-review:

`Scorecard analysis` is a fifth guard in this tree with no counterpart on the
target's required list. It is a self-audit that publishes a score rather than a
gate over a pull request, and it is not proposed as a required check here
either. It is outside the four above and outside the command that reads them:

    git grep -nE '^    name: ' -- .github/workflows/scorecard.yml
    .github/workflows/scorecard.yml:50:    name: Scorecard analysis

## What this gate adds that the target does not have

Seven names, each because this repository's product is different.

`catalogue schema`, `symbolic verification (fast)` and
`numeric verification (fast)`, because the product here is data and the target
has no equivalent surface. The names are created by #17 in milestone 2, over an
empty catalogue, so that the name exists from the beginning and the job grows
into it. The legs behind them are built by #24, #26 and #32.

`headless and unprivileged`, because every test here has to run without a
display, without elevation and without the network. That is a birth requirement
rather than something to be added once it has been broken, and it is #19.

`coverage bar` and `mutation sample`, aimed at the verdict path rather than at
the codebase as a whole. The target gates coverage on the modules that decide
authentication outcomes. The equivalent surface here is the code that decides
whether a row is verified, because a checker that quietly stops refusing is this
project's characteristic failure. Built by #54 and #55.

`parser fuzz seed replay`, because the untrusted input here is a contributed
case file rather than an authentication callback, and it is untrusted in the
same way. Built by #56.

Two further names that #17 creates, `unit tests` and `types`, are not placed
against anything on the target's list by this mapping. The target has no
separate check for either: its `build` job compiles and its analysis job covers
what a type checker would here. They are named in this paragraph rather than
left out silently, because a reader comparing this document against the check
names a pull request actually produces would otherwise find two with no entry
and no reason. Whether either becomes required is decided in #57 with the rest.

## What this gate deliberately does not take from the target

The target's release and publishing machinery, its compatibility metadata checks
and its end-to-end login test have no counterpart here. They are not deviations
to be justified. They are checks about a thing this repository is not.

## What is not gating, and is said rather than left implicit

The full verification sweep, the coverage-guided fuzzing and the full mutation
run are slow, and a gate a contributor cannot wait for is a gate that gets
worked around. They are run on demand and before a release rather than on a pull
request, and they belong to the release checklist in #61.

## The state of this repository's gate today

Nothing here is required yet. This repository's own ruleset carries no required
status checks at all:

    gh api repos/iderex/findbuch/rules/branches/main --jq '[.[].type]'
    ["deletion","non_fast_forward","pull_request"]

So a red run currently leaves the same trace as a green one. Making the mapped
checks required is #57, and it is deliberately last: a required check that is
flaky teaches everyone that the gate is an obstacle rather than a verdict, so
each name goes on the list only after it has run on real pull requests long
enough to be known stable. When that happens, #57 also records which checks are
required, which are not, and why for each one that is not.
