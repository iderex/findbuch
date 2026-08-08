# 0011. Data stays on the host

Decided in #12.

## Why this is written before there is code

This is a research tool rather than an application with users, which is exactly
the situation in which privacy obligations get waved away. They are written down
here instead, before there is anything to retrofit them into.

## The position

Personal data never leaves the host. The tool makes no network connection of its
own during any operation an operator runs, and nothing about a run is reported
anywhere. There is no telemetry, no crash reporting, no usage counting, no
update check, and no analytics of any kind. This is not a setting that defaults
to off. There is no code to switch on.

The data that could plausibly be personal in a project like this is small but
real. The contributor names in the provenance and in the history. The file paths
and machine names that appear in a verification report. And whatever an operator
puts into a case file or a trajectory they generate. All of it stays where it
was produced.

## The three bounded exceptions

Three places where a network connection is legitimate, and each one is
deliberate rather than incidental.

Installing the software, which fetches dependencies from a package index. That
is the operator running a package manager, and it is outside the tool.

Fetching a source document, if the project ever adds a helper for that. It has
to be an explicit command that the operator runs, it names what it will contact
before it contacts it, and it is never triggered by loading a row.

Federation, meaning exchanging rows with another instance or submitting a row
upstream. If it is ever built, it is an explicit act by the operator, it states
what will be sent before sending it, and it sends only the row and not the
surroundings. It never carries a report, a path, a machine identifier, or
anything else the operator did not choose to send.

The distinction that matters is that none of these is a background behaviour. A
run that the operator did not describe as a network operation does not make one.

## How this is kept true rather than merely stated

By a check rather than by intent.

The test suite runs with outbound network access blocked, so a call that opens a
socket on any path the suite reaches fails rather than succeeding quietly on a
machine that happens to be online. That is #19.

And a test asserts that the modules on the loading and verification paths import
nothing that opens a socket, which catches the addition before it is ever
called. An import-level assertion is what covers the branch no fixture happens
to reach, and the blocked suite is what covers the call the import list did not
predict. Neither replaces the other, and #50 carries the invariant.

A change that adds a network call to a verification path therefore fails the
gate rather than being noticed in review.

## What the documentation has to say

The operator guide states, in the reader's own words rather than as a legal
notice, that nothing about a run leaves the machine, what the three deliberate
exceptions are, and what a federation act would send if the operator performed
one. It says this in the guide where an operator will read it, not only in a
policy file that nobody opens. #58 and #59 are where that is written, and #59
names the check above so that a reader can follow the claim to the test rather
than believe it.

## What this record does not claim

That the software cannot reach the network. It runs on an interpreter with a
standard library that can, and no sandbox is claimed here. What is claimed is
narrower and it is checkable: nothing on the paths named above opens a socket,
and the suite that proves it runs with outbound access blocked.

The contributor names in the repository history are public, because the
repository is public. That is a consequence of where this work is done rather
than something the tool sends anywhere, and the documentation says so plainly
rather than leaving a reader to infer that the history is private.
