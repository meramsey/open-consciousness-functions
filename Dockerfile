FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg=7:5.1.9-0+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 ocf
WORKDIR /opt/ocf
COPY containers/requirements.txt /opt/ocf/requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --upgrade pip==26.2.0 \
    && python -m pip install --no-cache-dir -r requirements.txt
COPY scripts/ scripts/
COPY schemas/ schemas/
COPY functions/ functions/
COPY function-content/ function-content/
COPY locales/ locales/
COPY templates/ templates/
COPY audio/templates/stages/ audio/templates/stages/
COPY audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-PREP-LEARN-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-PREP-ROUTINE-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-FUNCTION-INSTALL-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-PILOT-RELAX-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-PILOT-HEARING-001.yaml audio/templates/sessions/
COPY audio/templates/sessions/OCF-TPL-SESSION-PILOT-SLEEP-EASY-001.yaml audio/templates/sessions/
COPY audio/cues/profiles/ audio/cues/profiles/
COPY audio/voices/profiles/ audio/voices/profiles/
COPY audio/voices/registry/ audio/voices/registry/
COPY audio/background/manifests/ audio/background/manifests/
COPY audio/background/presets/ audio/background/presets/
COPY audio/background/state-profiles/ audio/background/state-profiles/
ENV HOME=/home/ocf
ENV OCF_WORK_DIR=/home/ocf/.ocf/work
RUN chmod -R a+rX /opt/ocf && mkdir -p /home/ocf/.ocf && chown ocf:ocf /home/ocf/.ocf
USER ocf
VOLUME ["/out", "/home/ocf/.ocf"]
ENTRYPOINT ["python", "scripts/ocf.py"]
CMD ["doctor", "--json"]
