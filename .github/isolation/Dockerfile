# The image the suite runs in with no display, no privilege and no network (#19).
#
# The split between this file and the workflow is the point. Everything that
# needs the network happens here, at build time: the base image, the apt index,
# the locked sets. The suite itself runs from the built image with the network
# detached, so the run that decides whether the suite is clean has no route out
# and no name resolution, and nothing in it can quietly depend on one.
#
# The base is pinned by digest rather than by tag, for the same reason the
# actions in this repository's workflows are pinned by commit hash: a tag is a
# name somebody else can move, and a run that cannot say which bytes it ran is
# not evidence.
FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

# git, because two tests derive their subject from `git ls-files` rather than
# from a list somebody maintains: tests/test_type_check_coverage.py asks the
# tree which modules are tracked, and tests/test_coverage_bar.py asks it which
# modules this project ships. Without git in the image those two would fail for
# a reason that has nothing to do with what this container is proving.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# The unprivileged user the suite runs as. It is created here rather than passed
# to `docker run --user`, so that the image is unprivileged wherever it is run
# and not only where somebody remembered the flag.
RUN useradd --create-home --uid 1001 unprivileged

WORKDIR /app
COPY . /app
RUN chown --recursive unprivileged:unprivileged /app

# The same three commands the workflow jobs run, with the same hashes. A second
# spelling of the install would be a second thing to keep in step, so if these
# ever diverge from .github/workflows/gate.yml the divergence is visible here.
RUN python -m pip install --require-hashes --requirement requirements.lock \
    && python -m pip install --require-hashes --requirement requirements-dev.lock \
    && python -m pip install --no-deps --editable .

USER unprivileged
ENV HOME=/home/unprivileged

# The probe first, and the suite only if every condition held. A suite that ran
# under the wrong conditions and passed is worse than one that did not run,
# because it reports the conditions as met.
CMD ["sh", "-c", "python .github/isolation/probe.py && python tools/run_tests.py"]
