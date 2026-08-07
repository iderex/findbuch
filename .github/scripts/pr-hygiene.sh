#!/usr/bin/env bash
#
# Deterministic pull request hygiene rules (#49).
#
# Every rule here is decided by reading. None of them is a matter of taste, and
# none of them makes a judgement about whether the change is any good. What is
# NOT checked is listed in .github/workflows/pr-hygiene.yml beside what is.
#
# Each rule prints exactly one line, either "ok <id>" or "refuse <id> <detail>".
# The identifier is the assertion surface: pr-hygiene-selftest.sh compares sets
# of refusal identifiers, never the fact that this script exited non-zero.
# Asserting that something failed is not evidence that it failed for the stated
# reason, and a typo in a fixture fails too.
#
# Input is the environment, never an argument and never the event payload
# interpolated into a shell command:
#
#   PR_TITLE         the pull request title
#   PR_BODY          the pull request body
#   HEAD_REF         the head branch name, without refs/heads/
#   DEFAULT_BRANCH   the repository default branch name
#
# Exit status is 0 when nothing refused and 1 when something did.

set -euo pipefail

PR_TITLE="${PR_TITLE-}"
PR_BODY="${PR_BODY-}"
HEAD_REF="${HEAD_REF-}"
DEFAULT_BRANCH="${DEFAULT_BRANCH-}"

refused=0

refuse() {
  printf 'refuse %s %s\n' "$1" "$2"
  refused=1
}

pass() {
  printf 'ok %s\n' "$1"
}

# Lowercase, collapse every run of non-alphanumeric bytes to one space, trim.
# This is what makes the title comparison below insensitive to the difference
# between a branch name and the title GitHub proposes from it.
normalise() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/ /g; s/^ //; s/ $//'
}

# A change with no issue is a change nobody planned. The reference has to be a
# hash immediately followed by digits, and not part of a longer word, so that
# "issue # 20" and "closes issue 20" are both refused: they are what somebody
# writes when they meant to reference and did not.
#
# The bound worth knowing: a six-digit colour literal preceded by punctuation,
# for instance in a stylesheet quoted in the body, matches this pattern and
# passes the rule. Refusing that would need a judgement about what the author
# meant, which is what this check is not for.
if printf '%s' "$PR_BODY" | grep -qE '(^|[^A-Za-z0-9_])#[0-9]+'; then
  pass body-names-an-issue
else
  refuse body-names-no-issue 'the body carries no #<number> issue reference'
fi

# An empty title, and a title that is only the branch name in the spelling
# GitHub proposes when nobody typed one. The comparison is against the branch
# name alone. A single-commit pull request is titled from its commit subject by
# default, and that is usually a real title, so it is not caught here.
title_n=$(normalise "$PR_TITLE")
head_n=$(normalise "$HEAD_REF")
if [ -z "$title_n" ]; then
  refuse title-is-empty 'the title is empty'
elif [ -n "$head_n" ] && [ "$title_n" = "$head_n" ]; then
  refuse title-is-the-branch-name "the title is the branch name: ${HEAD_REF}"
else
  pass title-is-not-the-branch-name
fi

# A pull request opened from a branch named the same as the default branch. In
# this repository that is a fork's default branch, and it is refused because the
# branch is going to be force-moved by its owner under a review that is reading
# it.
if [ -n "$DEFAULT_BRANCH" ] && [ "$HEAD_REF" = "$DEFAULT_BRANCH" ]; then
  refuse head-is-the-default-branch "the head branch is the default branch: ${DEFAULT_BRANCH}"
else
  pass head-is-not-the-default-branch
fi

if [ "$refused" -ne 0 ]; then
  echo "::error::Pull request hygiene refused. Each line above names the rule that refused and why."
fi

exit "$refused"
