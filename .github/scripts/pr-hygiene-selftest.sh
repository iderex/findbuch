#!/usr/bin/env bash
#
# Proof that the rules in pr-hygiene.sh bite, for the reasons they name (#49).
#
# The workflow runs this before it runs the check itself, so a rule that has
# stopped refusing reds the job instead of passing every pull request in
# silence. A hygiene check that has quietly stopped refusing looks exactly like
# a repository whose pull requests are all well formed.
#
# Each case compares the SET of refusal identifiers, not the exit status. Every
# case that expects a refusal is paired with a neighbour one change away that
# must refuse nothing, because a rule that refuses everything passes a test that
# only ever feeds it bad input.
#
# Run it by hand the same way the workflow does:
#
#     bash .github/scripts/pr-hygiene-selftest.sh

set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script="$here/pr-hygiene.sh"

fails=0
cases=0

# run_case <name> <expected set, space separated and sorted> <title> <body> <head> <default>
run_case() {
  local name="$1" expected="$2" title="$3" body="$4" head="$5" default="$6"
  local out actual
  cases=$((cases + 1))
  set +e
  out=$(PR_TITLE="$title" PR_BODY="$body" HEAD_REF="$head" DEFAULT_BRANCH="$default" bash "$script")
  set -e
  actual=$(printf '%s\n' "$out" | sed -n 's/^refuse \([a-z-]*\).*/\1/p' | sort | tr '\n' ' ' | sed 's/ *$//')
  if [ "$actual" = "$expected" ]; then
    printf 'ok    %-34s refused {%s}\n' "$name" "$actual"
  else
    printf 'FAIL  %-34s refused {%s}, expected {%s}\n' "$name" "$actual" "$expected"
    fails=$((fails + 1))
  fi
}

# The shape everything else is one change away from.
run_case 'well formed' '' \
  'Add the loader' 'Closes #20' 'feat/loader' 'main'

# body-names-an-issue, and the three ways somebody writes a reference that is
# not one.
run_case 'body: no reference at all' 'body-names-no-issue' \
  'Add the loader' 'This adds the loader.' 'feat/loader' 'main'
run_case 'body: hash separated from number' 'body-names-no-issue' \
  'Add the loader' 'See issue # 20 for why.' 'feat/loader' 'main'
run_case 'body: number without a hash' 'body-names-no-issue' \
  'Add the loader' 'Closes issue 20.' 'feat/loader' 'main'
run_case 'body: reference inside a sentence' '' \
  'Add the loader' 'See issue #20 for why.' 'feat/loader' 'main'
run_case 'body: reference at the very start' '' \
  'Add the loader' '#20 is what this lands.' 'feat/loader' 'main'

# title-is-not-the-branch-name, in both spellings of the default GitHub
# proposes, with the neighbour that adds one word.
run_case 'title: empty' 'title-is-empty' \
  '' 'Closes #20' 'feat/loader' 'main'
run_case 'title: whitespace only' 'title-is-empty' \
  '   ' 'Closes #20' 'feat/loader' 'main'
run_case 'title: the branch name verbatim' 'title-is-the-branch-name' \
  'feat/loader' 'Closes #20' 'feat/loader' 'main'
run_case 'title: the branch name as proposed' 'title-is-the-branch-name' \
  'Feat/loader' 'Closes #20' 'feat/loader' 'main'
run_case 'title: one word more than the branch' '' \
  'Feat/loader rewrite' 'Closes #20' 'feat/loader' 'main'

# head-is-not-the-default-branch, with the neighbour one character away.
run_case 'head: is the default branch' 'head-is-the-default-branch' \
  'Add the loader' 'Closes #20' 'main' 'main'
run_case 'head: one character off the default' '' \
  'Add the loader' 'Closes #20' 'main-2' 'main'

# Two rules at once, so that a change collapsing the identifiers into one
# verdict is caught rather than absorbed.
run_case 'two rules: empty title, no reference' 'body-names-no-issue title-is-empty' \
  '' 'This adds the loader.' 'feat/loader' 'main'
run_case 'two rules: default head, branch title' 'head-is-the-default-branch title-is-the-branch-name' \
  'main' 'Closes #20' 'main' 'main'

echo
if [ "$fails" -ne 0 ]; then
  echo "::error::pr-hygiene self-test: ${fails} of ${cases} cases wrong. The rules do not do what they say."
  exit 1
fi
echo "pr-hygiene self-test: ${cases} cases, all as expected."
